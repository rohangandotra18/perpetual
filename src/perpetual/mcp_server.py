"""Perpetual MCP server — raw JSON-RPC over stdio, zero SDK dependencies.

Serves the live `tools` collection into a Claude Code session. The tool list a model
sees is literally a Mongo query result; when a macro is born (here via compile_ritual,
or externally by the miner in another terminal), we emit notifications/tools/list_changed
and the newborn tool becomes callable mid-session with no restart.

Race-condition note (verified against Claude Code 2.1.220): the client defers the
tools/list refresh while a call from this server is in flight — so compile_ritual emits
list_changed BEFORE returning its result.
"""
import json
import pathlib
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from perpetual import macro, primitives  # noqa: E402
from perpetual.db import db  # noqa: E402

PROTOCOL = "2024-11-05"
_write_lock = threading.Lock()


def send(msg: dict):
    with _write_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def log(s: str):
    print(f"[perpetual-mcp] {s}", file=sys.stderr, flush=True)


def notify_tools_changed():
    send({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
    log("emitted tools/list_changed")


def mongo_tools() -> list[dict]:
    out = []
    for t in db().tools.find({"status": "active"}):
        schema = t.get("params_schema") or t.get("input_schema") or {"type": "object", "properties": {}}
        desc = t["purpose"]
        if t.get("kind") == "macro":
            desc = f"[compiled macro — born {t.get('born_at', '?')}] {desc}"
        out.append({"name": t["name"], "description": desc, "inputSchema": schema})
    out.append({"name": "compile_ritual",
                "description": "Mine my trajectories for a repeated action sequence and, if one has "
                               "occurred 3+ times, compile it into a brand-new tool. The new tool "
                               "appears in this session immediately.",
                "inputSchema": {"type": "object", "properties": {}}})
    return out


def call_tool(name: str, args: dict) -> str:
    if name == "compile_ritual":
        from perpetual import miner
        born = miner.mine_and_compile()          # returns macro doc or None
        notify_tools_changed()                   # BEFORE returning — the race fix
        if born is not None:
            n = db().tools.count_documents({"status": "active"})
            return (f"⚡ Compiled new tool '{born['name']}' from a ritual repeated "
                    f"{len(born['born_from']['trajectory_ids'])}x. TOOLS KNOWN: {n - 1} → {n}. "
                    f"It is available in this session right now.")
        return "No ritual has reached 3 repetitions yet."
    doc = db().tools.find_one({"name": name, "status": "active"})
    if doc and doc.get("kind") == "macro":
        result = macro.execute_macro(doc, primitives.REGISTRY, args or {})
        db().tools.update_one({"name": name}, {"$inc": {"fitness.calls": 1, "fitness.successes": 1}})
        return json.dumps(result["result"], default=str)[:4000]
    fn = primitives.REGISTRY.get(name)
    if fn is None:
        raise ValueError(f"unknown tool {name}")
    return json.dumps(fn(**(args or {})), default=str)[:4000]


def watch_external_births():
    """A macro born in another terminal (the stage demo) appears here too."""
    known = {t["name"] for t in db().tools.find({}, {"name": 1})}
    while True:
        try:
            with db().tools.watch([{"$match": {"operationType": "insert"}}]) as stream:
                for ch in stream:
                    name = ch["fullDocument"].get("name")
                    if name not in known:
                        known.add(name)
                        log(f"external tool birth observed: {name}")
                        notify_tools_changed()
        except Exception as e:
            log(f"change stream unavailable ({e}); polling")
            while True:
                time.sleep(2)
                cur = {t["name"] for t in db().tools.find({}, {"name": 1})}
                if cur - known:
                    log(f"external tool birth observed (poll): {cur - known}")
                    known |= cur
                    notify_tools_changed()


def main():
    threading.Thread(target=watch_external_births, daemon=True).start()
    log("perpetual MCP server up")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": params.get("protocolVersion", PROTOCOL),
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": "perpetual", "version": "0.1.0"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": mongo_tools()}})
        elif method == "tools/call":
            try:
                text = call_tool(params["name"], params.get("arguments") or {})
                send({"jsonrpc": "2.0", "id": rid,
                      "result": {"content": [{"type": "text", "text": text}]}})
            except Exception as e:
                send({"jsonrpc": "2.0", "id": rid,
                      "result": {"content": [{"type": "text", "text": f"error: {e}"}],
                                 "isError": True}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif rid is not None:  # unknown request — answer, don't hang the client
            send({"jsonrpc": "2.0", "id": rid,
                  "error": {"code": -32601, "message": f"method not found: {method}"}})


if __name__ == "__main__":
    main()
