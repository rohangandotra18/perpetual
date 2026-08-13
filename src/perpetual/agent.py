"""Agent A — the loop whose action space IS a $vectorSearch result.

Every run starts by asking Atlas "which tools are relevant to this task?" ($vectorSearch
over tools.purpose_embedding). Whatever comes back — primitives today, compiled macros
tomorrow — becomes the function schema list handed to the model. Nothing else is
hard-wired: growing the agent's abilities means inserting a document.

Run:
    PYTHONPATH=src python -m perpetual.agent "send my weekly update to dana"
    PYTHONPATH=src python -m perpetual.agent "send my weekly update to dana" --agent-id agent-b
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import uuid

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from . import llm, primitives
from .db import db
from .macro import MacroError, execute_macro

console = Console(highlight=False)

MAX_STEPS = 10
TRANSCRIPT_LIMIT = 800  # chars of tool output shown to the model
TERMINAL_TOOLS = {"send_message", "create_issue"}

SYSTEM_PROMPT = (
    "You are Perpetual, an autonomous work agent operating on behalf of Maya (user id U_MAYA).\n"
    "The tools you have been given were retrieved from a vector database for THIS task; "
    "they are your entire action space.\n"
    "Rules:\n"
    "- If a tool description starts with [macro], it is a skill this agent already compiled "
    "from its own past behavior. If it fits the task, CALL IT FIRST and call nothing else.\n"
    "- Otherwise gather ALL context before writing. For a weekly update / status report, the "
    "correct procedure is exactly, in this order, one call per turn, skipping nothing:\n"
    "    1. search_slack   (what did I work on this week)\n"
    "    2. list_my_issues (state=closed, since_days=7)\n"
    "    3. who_did_i_delegate\n"
    "    4. get_voice_profile\n"
    "    5. draft_message  (bullets drawn from steps 1-3)\n"
    "    6. send_message\n"
    "  Every step contributes material to the draft; never skip one to save time.\n"
    "- Call exactly one tool per turn. When the work is delivered, reply with one short "
    "sentence and no tool call.\n"
    "- Dana's user id is U_DANA."
)


# ---------------------------------------------------------------- tool search

def tool_search(task: str, limit: int = 8) -> list[dict]:
    """The action space is a query result. Vector search with a plain-find fallback."""
    docs: list[dict] = []
    try:
        docs = primitives._vector_query(
            "tools", "tools_vec", "purpose_embedding", task, limit, {"status": "active"}
        )
    except Exception as e:  # embeddings offline / index still building
        console.print(f"[yellow]  ! vector search unavailable ({e.__class__.__name__}), "
                      f"falling back to collection scan[/yellow]")
    if not docs:
        docs = list(db().tools.find({"status": "active"}).limit(limit))

    seen, out = set(), []
    for d in docs:
        if d.get("name") and d["name"] not in seen:
            seen.add(d["name"])
            out.append(d)
    return out


def to_openai_tools(docs: list[dict]) -> list[dict]:
    """Tool documents -> OpenAI-style function schemas."""
    schemas = []
    for d in docs:
        if d.get("kind") == "macro":
            params = dict(d.get("input_schema") or {})
            desc = "[macro] " + (d.get("purpose") or d["name"])
        else:
            params = dict(d.get("params_schema") or {})
            desc = d.get("purpose") or d["name"]
        params.setdefault("type", "object")
        params.setdefault("properties", {})
        schemas.append({"type": "function", "function": {
            "name": d["name"], "description": desc[:900], "parameters": params}})
    return schemas


# ---------------------------------------------------------------- formatting

def _fmt_args(args: dict, width: int = 88) -> str:
    parts = []
    for k, v in (args or {}).items():
        if isinstance(v, str):
            v = " ".join(v.split())
            s = v if len(v) <= 34 else v[:31] + "..."
            parts.append(f'{k}="{s}"')
        elif isinstance(v, (list, tuple)):
            parts.append(f"{k}=[{len(v)} items]")
        elif isinstance(v, dict):
            parts.append(f"{k}={{...}}")
        else:
            parts.append(f"{k}={v}")
    s = " ".join(parts)
    return s if len(s) <= width else s[: width - 3] + "..."


def _digest(tool: str, result) -> str:
    """Short human string for the trajectory log — this is what the miner reads."""
    if not isinstance(result, dict):
        return str(result)[:60]
    if "error" in result:
        return f"error: {str(result['error'])[:50]}"
    if "messages" in result:
        return f"{len(result['messages'])} messages"
    if "issues" in result:
        return f"{len(result['issues'])} issues"
    if "delegations" in result:
        ds = result["delegations"]
        who = ds[0]["to"].split()[0].lower() if ds else ""
        return f"{len(ds)} delegation{'s' if len(ds) != 1 else ''}" + (f", {who}" if who else "")
    if "profile" in result:
        prof = result.get("profile") or {}
        return f"{prof.get('user_id', 'profile')}, {len(prof.get('rules', []))} rules"
    if "text" in result:
        return f"draft, {len(str(result['text']).split())} words"
    if result.get("sent"):
        return f"sent to {result.get('to')}"
    if "key" in result:
        return f"issue {result['key']}"
    if "steps" in result and "result" in result:  # macro envelope
        inner = result["steps"]
        tail = _digest("", result["result"]) if isinstance(result["result"], dict) else ""
        return f"macro ok, {len(inner)} inner steps" + (f", {tail}" if tail else "")
    return ", ".join(list(result.keys()))[:60]


def _compact(result, limit: int = TRANSCRIPT_LIMIT):
    """Shrink a result for the model transcript; the real result still feeds the digest."""
    s = json.dumps(result, default=str)
    if len(s) <= limit:
        return result
    return {"_truncated": True, "preview": s[:limit]}


def _log_safe(value):
    """BSON-safe, compact version of tool args for the trajectory document."""
    if isinstance(value, dict):
        if any(isinstance(k, str) and k.startswith("$") for k in value):
            return "<ref from prior step>"
        return {k: _log_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_log_safe(v) for v in value]
    if isinstance(value, str) and len(value) > 400:
        return value[:400] + "..."
    return value


def _now() -> str:
    return dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- fitness

def _bump(doc: dict | None, ok: bool):
    if not doc:
        return
    try:
        inc = {"fitness.calls": 1}
        if ok:
            inc["fitness.successes"] = 1
        db().tools.update_one({"_id": doc["_id"]}, {"$inc": inc})
    except Exception:
        pass


# ---------------------------------------------------------------- the run

def run(task: str, agent_id: str = "agent-a", top_k: int = 12, max_steps: int = MAX_STEPS) -> dict:
    started = _now()
    t_run = time.time()

    console.rule(f"[bold white]PERPETUAL[/bold white] [dim]·[/dim] [bold]{agent_id}[/bold]")
    console.print(f'[bold]task[/bold]  [italic]"{task}"[/italic]')
    console.print(f"[dim]mode  {'MOCK policy' if llm.mock_mode() else 'gemini ' + __import__('os').environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}"
                  f"   db {db().name}[/dim]\n")

    # 1. the action space is a query result
    docs = tool_search(task, top_k)
    n_macro = sum(1 for d in docs if d.get("kind") == "macro")
    console.print(f"[bold cyan]tool_search[/bold cyan]: [bold]{len(docs)}[/bold] tools retrieved from Atlas "
                  f"[dim]($vectorSearch · tools_vec · purpose_embedding)[/dim]")
    for d in docs:
        nm = d["name"][:24].ljust(24)
        purpose = (d.get("purpose") or "").replace("\n", " ")
        if d.get("kind") == "macro":
            console.print(f"   [bold magenta]★ {nm}[/bold magenta]"
                          f"[magenta]macro · {len(d.get('steps', []))} steps · {purpose[:28]}[/magenta]")
        else:
            console.print(f"   [cyan]· {nm}[/cyan][dim]{purpose[:44]}[/dim]")
    if n_macro:
        console.print(f"[magenta]   {n_macro} compiled macro(s) in the action space[/magenta]")
    console.print()

    by_name = {d["name"]: d for d in docs}
    schemas = to_openai_tools(docs)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    steps: list[dict] = []
    any_failure = False
    terminal_done = False
    final_text = None

    for _ in range(max_steps):
        try:
            resp = llm.chat(messages, tools=schemas)
        except Exception as e:
            console.print(f"[red]  llm error: {e}[/red]")
            any_failure = True
            break

        call = resp.get("tool_call")
        if not call:
            final_text = resp.get("content")
            break

        name = call["name"]
        args = call.get("args") or {}
        doc = by_name.get(name)
        is_macro = bool(doc and doc.get("kind") == "macro")
        i = len(steps)

        label = f"[bold magenta]{name}[/bold magenta] [magenta](macro)[/magenta]" if is_macro \
            else f"[bold cyan]{name}[/bold cyan]"
        console.print(f"[dim]{i + 1:>2}[/dim] [white]▸[/white] {label}  [dim]{_fmt_args(args)}[/dim]")

        t0 = time.time()
        ok = True
        try:
            if is_macro:
                def on_step(idx, tool_name, params):
                    console.print(f"       [magenta]└─ {idx + 1}. {tool_name}[/magenta] "
                                  f"[dim]{_fmt_args(params, 46)}[/dim]")
                result = execute_macro(doc, primitives.REGISTRY, args, on_step=on_step)
            elif name in primitives.REGISTRY:
                result = primitives.REGISTRY[name](**args)
            else:
                raise KeyError(f"tool '{name}' is not in the retrieved action space")
        except (MacroError, Exception) as e:  # noqa: B014 - demo resilience
            ok = False
            any_failure = True
            result = {"error": f"{e.__class__.__name__}: {e}"}
        ms = int((time.time() - t0) * 1000)

        dg = _digest(name, result)
        if is_macro and ok:
            tail = _digest("", result.get("result")) if isinstance(result.get("result"), dict) else ""
            dg = f"macro ok, {len(doc.get('steps', []))} steps in 1 call" + (f", {tail}" if tail else "")
        console.print(f"     [green]→ {dg}[/green] [dim]{ms}ms[/dim]" if ok
                      else f"     [red]✗ {dg}[/red] [dim]{ms}ms[/dim]")

        steps.append({"i": i, "tool": name, "args": _log_safe(args),
                      "ok": ok, "ms": ms, "result_digest": dg})
        _bump(doc, ok)

        call_id = f"call_{i}_{uuid.uuid4().hex[:6]}"
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": name, "arguments": json.dumps(args, default=str)}}]})
        messages.append({"role": "tool", "tool_call_id": call_id, "name": name,
                         "content": json.dumps({"tool": name, "result": _compact(result)},
                                               default=str)})

        if ok and name in TERMINAL_TOOLS:
            terminal_done = True
        if is_macro and ok:
            # A compiled macro is the whole ritual; if it ends in a terminal action the run
            # is finished — this is the "warm run = 1 call" beat.
            inner_tools = {s.get("tool") for s in doc.get("steps", [])}
            if inner_tools & TERMINAL_TOOLS:
                terminal_done = True
                final_text = f"done — executed compiled skill {name} ({len(doc.get('steps', []))} steps in 1 call)."
                break

    duration = time.time() - t_run
    outcome = "success" if terminal_done and not any_failure else "failed"

    traj = {
        "_id": f"T-{dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
        "agent_id": agent_id,
        "task": task,
        "started_at": started,
        "ended_at": _now(),
        "outcome": outcome,
        "steps": steps,
    }
    try:
        db().trajectories.insert_one(traj)
        logged = True
    except Exception as e:
        logged = False
        console.print(f"[red]  ! trajectory not logged: {e}[/red]")

    if final_text:
        console.print(f"\n[italic dim]{str(final_text).strip()[:200]}[/italic dim]")

    tools_known = db().tools.count_documents({"status": "active"})
    n_traj = db().trajectories.count_documents({"agent_id": agent_id, "task": task,
                                                "outcome": "success"})

    banner = Text()
    banner.append(f"{len(steps)} tool call{'s' if len(steps) != 1 else ''}", style="bold white")
    banner.append("   ·   ", style="dim")
    banner.append(f"{duration:.1f}s", style="bold white")
    banner.append("   ·   ", style="dim")
    banner.append(f"outcome {outcome}", style="bold green" if outcome == "success" else "bold red")
    banner.append("   ·   ", style="dim")
    banner.append(f"TOOLS KNOWN: {tools_known}", style="bold magenta")
    console.print()
    console.print(Panel(banner, border_style="magenta" if outcome == "success" else "red",
                        title="[bold]run complete[/bold]", title_align="left",
                        subtitle=f"[dim]trajectory {traj['_id'] if logged else '(not logged)'} · "
                                 f"{n_traj} successful runs of this task[/dim]",
                        subtitle_align="left"))

    return {"trajectory": traj, "tools_known": tools_known, "duration_s": duration,
            "outcome": outcome, "support": n_traj}


def main():
    ap = argparse.ArgumentParser(prog="perpetual.agent", description="Run the Perpetual agent loop.")
    ap.add_argument("task", help="natural-language task, e.g. 'send my weekly update to dana'")
    ap.add_argument("--agent-id", default="agent-a")
    ap.add_argument("--top-k", type=int, default=12, help="tools retrieved from Atlas")
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    a = ap.parse_args()
    out = run(a.task, agent_id=a.agent_id, top_k=a.top_k, max_steps=a.max_steps)
    return 0 if out["outcome"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
