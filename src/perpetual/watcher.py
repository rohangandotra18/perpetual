"""AGENT B — the cold process that inherits a skill it never learned.

Agent B boots with only the tools it can see in the `tools` collection. It then
watches that collection. When Agent A's miner compiles a ritual into a macro and
inserts it, Agent B learns it *instantly* — no retraining, no prompt edit — and
proves it by executing the macro on the very first try.

Transport:
  primary  — MongoDB change stream (db.tools.watch, insert ops only)
  fallback — 2s poll on a born_at watermark (auto-engaged if watch() can't open,
             e.g. a non-replica-set tier)

Run:
    PYTHONPATH=src python -m perpetual.watcher [--agent-id agent-b]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import threading
import time
from typing import Any

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from . import macro as macro_mod
from . import primitives
from .db import db

console = Console()

# ── color language ────────────────────────────────────────────────────────────
INFO = "cyan"
OK = "green"
BIRTH = "magenta"
DIM = "grey58"

WATCH_OPEN_TIMEOUT_S = 3.0
POLL_INTERVAL_S = 2.0


# ── tiny block-letter banner (no external font deps) ──────────────────────────
_GLYPHS = {
    "A": ["█████", "█   █", "█████", "█   █", "█   █"],
    "B": ["████ ", "█   █", "████ ", "█   █", "████ "],
    "C": ["█████", "█    ", "█    ", "█    ", "█████"],
    "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "G": ["█████", "█    ", "█  ██", "█   █", "█████"],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
    "K": ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "O": ["█████", "█   █", "█   █", "█   █", "█████"],
    "Q": ["█████", "█   █", "█ █ █", "█  ██", "█████"],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "S": ["█████", "█    ", "█████", "    █", "█████"],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "U": ["█   █", "█   █", "█   █", "█   █", "█████"],
    "F": ["█████", "█    ", "████ ", "█    ", "█    "],
    "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
    "V": ["█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "Y": ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "],
    " ": ["  ", "  ", "  ", "  ", "  "],
}


def bigtext(word: str) -> str:
    rows = ["", "", "", "", ""]
    for ch in word.upper():
        g = _GLYPHS.get(ch)
        if g is None:
            g = _GLYPHS[" "]
        for r in range(5):
            rows[r] += g[r] + " "
    return "\n".join(rows)


# ── helpers ───────────────────────────────────────────────────────────────────
def _utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


def _parse_ts(v: Any) -> dt.datetime | None:
    """born_at may be an ISO string (seed.py writes utcnow().isoformat()) or a datetime."""
    if isinstance(v, dt.datetime):
        return v.astimezone(dt.timezone.utc).replace(tzinfo=None) if v.tzinfo else v
    if isinstance(v, str):
        s = v.strip().replace("Z", "+00:00")
        try:
            p = dt.datetime.fromisoformat(s)
        except ValueError:
            return None
        return p.astimezone(dt.timezone.utc).replace(tzinfo=None) if p.tzinfo else p
    return None


def _age_seconds(born_at: Any) -> int | None:
    p = _parse_ts(born_at)
    if p is None:
        return None
    return max(0, int((_utcnow() - p).total_seconds()))


def _is_macro(doc: dict) -> bool:
    return doc.get("kind") == "macro" or (doc.get("kind") != "primitive" and "steps" in doc)


def _sortable(born_at: Any) -> str:
    p = _parse_ts(born_at)
    return p.isoformat() if p else ""


def _brief(value: Any, width: int = 88) -> str:
    try:
        s = json.dumps(value, default=str)
    except Exception:
        s = str(value)
    return s if len(s) <= width else s[: width - 1] + "…"


def _load_tools() -> list[dict]:
    return list(db().tools.find({"status": {"$ne": "retired"}}))


def _default_inputs(m: dict) -> dict:
    """Macros are meant to run with {} — but honor declared defaults if the author gave any."""
    props = ((m.get("input_schema") or {}).get("properties") or {})
    return {k: v["default"] for k, v in props.items() if isinstance(v, dict) and "default" in v}


# ── boot banner ───────────────────────────────────────────────────────────────
def print_boot(agent_id: str, tools: list[dict], dbname: str):
    console.print()
    console.print(Panel(
        Align.center(Text(bigtext("AGENT B"), style=f"bold {INFO}")),
        border_style=INFO, padding=(1, 2),
        title=f"[bold {INFO}]cold process[/]",
        subtitle=f"[{DIM}]db={dbname}  agent_id={agent_id}[/]",
    ))
    console.print()
    console.print(f"[bold {INFO}]AGENT B — cold process. TOOLS KNOWN: {len(tools)}[/]")

    t = Table(show_header=True, header_style=f"bold {DIM}", box=None, padding=(0, 2))
    t.add_column("#", style=DIM, width=3, justify="right")
    t.add_column("tool", style="bold")
    t.add_column("kind")
    t.add_column("purpose", style=DIM, overflow="ellipsis", max_width=64)
    for i, doc in enumerate(sorted(tools, key=lambda d: (d.get("kind") != "primitive", d.get("name", ""))), 1):
        kind = doc.get("kind", "?")
        t.add_row(str(i), doc.get("name", str(doc.get("_id"))),
                  f"[{BIRTH}]{kind}[/]" if kind == "macro" else f"[{DIM}]{kind}[/]",
                  (doc.get("purpose") or "").replace("\n", " "))
    console.print(t)
    console.print()
    console.print(f"[{DIM}]It has never performed the weekly-update ritual. "
                  f"It has no macro for it. It is only watching.[/]")
    console.print()


# ── the money shot ────────────────────────────────────────────────────────────
def announce_and_inherit(m: dict, total_tools: int, transport: str):
    name = m.get("name", "unnamed_macro")
    age = _age_seconds(m.get("born_at"))
    age_txt = f"{age}s ago" if age is not None else "moments ago"
    author = m.get("born_from_agent") or m.get("agent_id") or "another agent"

    console.print()
    console.print(Rule(style=BIRTH))
    console.print(Panel(
        Group(
            Align.center(Text(bigtext("SKILL"), style=f"bold {BIRTH}")),
            Align.center(Text(bigtext("ACQUIRED"), style=f"bold {BIRTH}")),
            Text(""),
            Align.center(Text(f"⚡ SKILL ACQUIRED: {name}", style=f"bold {BIRTH}")),
            Align.center(Text(f"compiled by {author} {age_txt}", style=DIM)),
        ),
        border_style=BIRTH, padding=(1, 2),
        title=f"[bold {BIRTH}]⚡ inherited via {transport}[/]",
    ))
    console.print(Rule(style=BIRTH))
    console.print()
    console.print(f"[bold {BIRTH}]⚡ SKILL ACQUIRED: {name} — compiled by {author} {age_txt}[/]")
    console.print(f"[bold {INFO}]TOOLS KNOWN: {total_tools - 1} → {total_tools}[/]")
    if m.get("purpose"):
        console.print(f"[{DIM}]purpose: {m['purpose']}[/]")
    console.print()

    # show the inherited artifact — it is just readable JSON
    body = {k: m[k] for k in ("name", "kind", "purpose", "input_schema", "steps", "guard") if k in m}
    console.print(Panel(Syntax(json.dumps(body, indent=2, default=str), "json",
                               theme="ansi_dark", word_wrap=True),
                        title=f"[{BIRTH}]the inherited tool document[/]",
                        border_style=BIRTH, padding=(0, 1)))
    console.print()

    # ── demonstrate inheritance immediately ──────────────────────────────────
    console.print(f"[bold {INFO}]▶ executing it on the first try…[/]")
    console.print()
    t0 = time.time()

    def on_step(i: int, tool: str, params: dict):
        console.print(f"     [{INFO}]step {i + 1}[/] [bold]{tool}[/]"
                      f"  [{DIM}]{_brief(params)}[/]")

    try:
        out = macro_mod.execute_macro(m, primitives.REGISTRY, _default_inputs(m), on_step=on_step)
    except Exception as e:
        console.print()
        console.print(Panel(f"[red]macro execution failed: {type(e).__name__}: {e}[/]",
                            border_style="red", title="[red]inheritance stumbled[/]"))
        console.print()
        return

    ms = int((time.time() - t0) * 1000)
    n_steps = len(m.get("steps", []))
    console.print()
    console.print(f"     [{DIM}]result:[/] [{OK}]{_brief(out.get('result'))}[/]")
    console.print()
    console.print(Panel(
        Group(
            Text(f"Agent B executed {name} on first try — it never performed the ritual.",
                 style=f"bold {OK}"),
            Text(f"{n_steps} primitive calls, 1 tool call, {ms} ms — zero trial and error.",
                 style=DIM),
        ),
        border_style=OK, padding=(1, 2), title=f"[bold {OK}]✓ INHERITED[/]"))
    console.print()
    console.print(f"[{DIM}]still watching for new skills… (ctrl-c to exit)[/]")
    console.print()


# ── transports ────────────────────────────────────────────────────────────────
def _open_change_stream(coll, timeout_s: float = WATCH_OPEN_TIMEOUT_S):
    """Open db.tools.watch() in a side thread so a hung/failing open can't wedge the demo."""
    box: dict = {}

    def run():
        try:
            box["cs"] = coll.watch(
                pipeline=[{"$match": {"operationType": {"$in": ["insert", "replace"]}}}],
                full_document="updateLookup",
            )
        except Exception as e:  # non-replica-set tier, auth scope, driver mismatch…
            box["err"] = e

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(timeout_s)
    if "cs" in box:
        return box["cs"], None
    return None, box.get("err") or TimeoutError(f"watch() did not open in {timeout_s:g}s")


class Watcher:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.coll = db().tools
        self.seen: set = set()
        self.watermark: str = ""
        self.n_tools = 0

    def bootstrap(self) -> list[dict]:
        tools = _load_tools()
        self.seen = {d["_id"] for d in tools}
        self.watermark = max([_sortable(d.get("born_at")) for d in tools] or [""])
        self.n_tools = len(tools)
        return tools

    def _accept(self, doc: dict) -> bool:
        if doc is None or doc.get("_id") in self.seen:
            return False
        self.seen.add(doc["_id"])
        self.watermark = max(self.watermark, _sortable(doc.get("born_at")))
        if doc.get("status") == "retired":
            return False
        self.n_tools = self.coll.count_documents({"status": {"$ne": "retired"}})
        if not _is_macro(doc):
            console.print(f"[{DIM}]· new tool appeared: {doc.get('name')} "
                          f"(kind={doc.get('kind')}) — not a macro, ignoring[/]")
            return False
        return True

    def poll_new(self) -> list[dict]:
        q = {"$or": [{"born_at": {"$gt": self.watermark}}, {"born_at": {"$exists": False}},
                     {"born_at": None}]}
        fresh = [d for d in self.coll.find(q) if d["_id"] not in self.seen]
        # safety net: anything at all we have not seen (clock skew / odd born_at types)
        if not fresh:
            fresh = [d for d in self.coll.find({"_id": {"$nin": list(self.seen)}})]
        return sorted(fresh, key=lambda d: _sortable(d.get("born_at")))

    def run(self):
        tools = self.bootstrap()
        print_boot(self.agent_id, tools, os.environ.get("PERPETUAL_DB", "perpetual"))

        cs, err = _open_change_stream(self.coll)
        if cs is not None:
            transport = "change stream"
            console.print(f"[{OK}]● transport: MongoDB change stream on `tools` "
                          f"(insert ops)[/]  [{DIM}]— live push[/]")
        else:
            transport = "poll"
            console.print(f"[yellow]● change stream unavailable "
                          f"({type(err).__name__}: {str(err)[:90]})[/]")
            console.print(f"[{OK}]● transport: 2s poll on max(born_at)[/]  [{DIM}]— fallback[/]")
        console.print(f"[{INFO}]watching for compiled skills… (ctrl-c to exit)[/]")
        console.print()

        last_poll = 0.0
        while True:
            if cs is not None:
                try:
                    change = cs.try_next()
                except Exception as e:
                    console.print(f"[yellow]! change stream dropped ({type(e).__name__}: {e}); "
                                  f"switching to 2s poll[/]")
                    try:
                        cs.close()
                    except Exception:
                        pass
                    cs, transport = None, "poll"
                    continue
                if change:
                    doc = change.get("fullDocument")
                    if doc and self._accept(doc):
                        announce_and_inherit(doc, self.n_tools, transport)
                    continue
                time.sleep(0.25)
            else:
                now = time.time()
                if now - last_poll < POLL_INTERVAL_S:
                    time.sleep(0.2)
                    continue
                last_poll = now
                for doc in self.poll_new():
                    if self._accept(doc):
                        announce_and_inherit(doc, self.n_tools, transport)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="perpetual.watcher", description="Agent B — skill inheritance watcher")
    ap.add_argument("--agent-id", default="agent-b")
    ap.add_argument("--poll", action="store_true", help="force the poll transport (skip change stream)")
    args = ap.parse_args(argv)

    w = Watcher(args.agent_id)
    if args.poll:
        globals()["_open_change_stream"] = lambda *a, **k: (None, RuntimeError("--poll forced by flag"))
    try:
        w.run()
    except KeyboardInterrupt:
        console.print()
        console.print(f"[{DIM}]agent B stopped.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
