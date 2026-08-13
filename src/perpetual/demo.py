"""PERPETUAL demo conductor — the operator's console for the three demo beats.

    PYTHONPATH=src python -m perpetual.demo reset        # known-good --warm state
    PYTHONPATH=src python -m perpetual.demo status       # tools known / trajectories / events
    PYTHONPATH=src python -m perpetual.demo birth-check  # is the ritual at support 2 or 3?

Color language: cyan = info, green = success, magenta = birth / skill.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from . import seed as seed_mod
from .db import db, ensure_indexes, index_queryable
from .llm import RITUAL

console = Console()

INFO = "cyan"
OK = "green"
BIRTH = "magenta"
DIM = "grey58"

SUPPORT_THRESHOLD = 3


# ── shared chrome ─────────────────────────────────────────────────────────────
def header(title: str, subtitle: str = "", style: str = INFO):
    console.print()
    console.print(Panel(
        Group(
            Text(title, style=f"bold {style}", justify="center"),
            *([Text(subtitle, style=DIM, justify="center")] if subtitle else []),
        ),
        border_style=style, padding=(1, 2),
        subtitle=f"[{DIM}]db={os.environ.get('PERPETUAL_DB', 'perpetual')}[/]",
    ))
    console.print()


def _fmt(v: Any, width: int = 70) -> str:
    if isinstance(v, (dict, list)):
        try:
            v = json.dumps(v, default=str)
        except Exception:
            v = str(v)
    s = str(v).replace("\n", " ")
    return s if len(s) <= width else s[: width - 1] + "…"


def _step_tools(traj: dict) -> list[str]:
    return [s.get("tool") for s in traj.get("steps", []) if isinstance(s, dict)]


def _contains_ritual(tools: list[str], ritual: list[str] = RITUAL) -> bool:
    """Contiguous, in-order occurrence of the 6-step ritual inside a trajectory."""
    n, m = len(tools), len(ritual)
    return any(tools[i:i + m] == ritual for i in range(n - m + 1))


def ritual_support() -> tuple[int, list[dict]]:
    hits = [t for t in db().trajectories.find({"outcome": "success"})
            if _contains_ritual(_step_tools(t))]
    hits.sort(key=lambda t: str(t.get("started_at", "")))
    return len(hits), hits


def tool_docs() -> list[dict]:
    return list(db().tools.find({"status": {"$ne": "retired"}}))


# ── subcommands ───────────────────────────────────────────────────────────────
def cmd_reset(_args) -> int:
    header("PERPETUAL — RESET", "rebuilding the known-good --warm state", INFO)
    console.print(f"[{INFO}]ensuring collections + indexes (tools_vec, messages_vec, memories_vec, skills_vec)…[/]")
    ensure_indexes()
    console.print(f"[{OK}]✓ indexes ensured[/]")
    console.print()
    console.print(f"[{INFO}]seeding corpus + primitive tool docs…[/]")
    seed_mod.reset()
    console.print()

    d = db()
    tools = tool_docs()
    prims = [t for t in tools if t.get("kind") == "primitive"]
    macros = [t for t in tools if t.get("kind") == "macro"]

    t = Table(show_header=True, header_style=f"bold {DIM}", box=None, padding=(0, 3))
    t.add_column("collection", style="bold")
    t.add_column("docs", justify="right", style=INFO)
    for name in ("people", "messages", "issues", "sent_messages", "style_profile",
                 "relations", "trajectories", "tools", "skills", "memories", "events"):
        t.add_row(name, str(d[name].count_documents({})))
    console.print(t)
    console.print()

    support, _ = ritual_support()
    console.print(Panel(
        Group(
            Text(f"TOOLS KNOWN: {len(tools)}   ({len(prims)} primitive, {len(macros)} macro)",
                 style=f"bold {OK}"),
            Text(f"ritual support: {support} / {SUPPORT_THRESHOLD}"
                 f"  — {'one live run needed' if support == SUPPORT_THRESHOLD - 1 else 'see birth-check'}",
                 style=DIM),
        ),
        border_style=OK, padding=(1, 2), title=f"[bold {OK}]✓ COLD STATE READY[/]"))
    console.print()
    return 0


def cmd_status(_args) -> int:
    header("PERPETUAL — STATUS", "the agent's action space is a collection", INFO)
    d = db()
    tools = tool_docs()
    prims = [t for t in tools if t.get("kind") == "primitive"]
    macros = [t for t in tools if t.get("kind") == "macro"]

    console.print(f"[bold {INFO}]TOOLS KNOWN: {len(tools)}[/]"
                  f"  [{DIM}]({len(prims)} primitive, [/][{BIRTH}]{len(macros)} macro[/][{DIM}])[/]")
    tt = Table(show_header=True, header_style=f"bold {DIM}", box=None, padding=(0, 2))
    tt.add_column("#", style=DIM, width=3, justify="right")
    tt.add_column("tool", style="bold")
    tt.add_column("kind")
    tt.add_column("born_at", style=DIM)
    for i, doc in enumerate(sorted(tools, key=lambda x: (x.get("kind") != "primitive",
                                                         str(x.get("born_at")))), 1):
        kind = doc.get("kind", "?")
        tt.add_row(str(i), doc.get("name", str(doc.get("_id"))),
                   f"[{BIRTH}]macro[/]" if kind == "macro" else f"[{DIM}]{kind}[/]",
                   _fmt(doc.get("born_at"), 32))
    console.print(tt)
    console.print()

    n_traj = d.trajectories.count_documents({})
    n_ok = d.trajectories.count_documents({"outcome": "success"})
    support, _ = ritual_support()
    console.print(f"[bold {INFO}]TRAJECTORIES: {n_traj}[/]"
                  f"  [{DIM}]({n_ok} successful, {support} containing the 6-step ritual)[/]")
    rows = list(d.trajectories.find().sort("started_at", -1).limit(3))
    if rows:
        rt = Table(show_header=True, header_style=f"bold {DIM}", box=None, padding=(0, 2))
        rt.add_column("_id", style=DIM)
        rt.add_column("agent", style=DIM)
        rt.add_column("task", style="bold")
        rt.add_column("steps", justify="right")
        rt.add_column("outcome")
        for r in rows:
            outcome = r.get("outcome", "?")
            rt.add_row(_fmt(r.get("_id"), 18), _fmt(r.get("agent_id"), 10),
                       _fmt(r.get("task"), 34), str(len(r.get("steps", []))),
                       f"[{OK}]{outcome}[/]" if outcome == "success" else f"[yellow]{outcome}[/]")
        console.print(rt)
    console.print()

    console.print(f"[bold {INFO}]LAST 3 EVENTS[/]")
    try:
        events = list(d.events.find().sort([("_id", -1)]).limit(3))
    except Exception as e:
        events = []
        console.print(f"[yellow]  ! could not read events: {e}[/]")
    if not events:
        console.print(f"[{DIM}]  (no events logged yet)[/]")
    else:
        et = Table(show_header=True, header_style=f"bold {DIM}", box=None, padding=(0, 2))
        et.add_column("when", style=DIM)
        et.add_column("type", style=INFO)
        et.add_column("detail", overflow="ellipsis", max_width=72)
        for e in reversed(events):
            when = e.get("ts") or e.get("at") or e.get("created_at") or ""
            typ = e.get("type") or e.get("kind") or e.get("event") or "?"
            detail = (e.get("message") or e.get("detail") or e.get("text")
                      or {k: v for k, v in e.items()
                          if k not in {"_id", "ts", "at", "created_at", "type", "kind", "event"}})
            style = BIRTH if "macro" in str(typ) or "birth" in str(typ) else DIM
            et.add_row(_fmt(when, 26), f"[{style}]{_fmt(typ, 24)}[/]", _fmt(detail, 72))
        console.print(et)
    console.print()
    return 0


def cmd_birth_check(_args) -> int:
    header("PERPETUAL — BIRTH CHECK", "is the ritual ripe for compilation?", BIRTH)
    support, hits = ritual_support()

    rt = Table(show_header=True, header_style=f"bold {DIM}", box=None, padding=(0, 2))
    rt.add_column("step", style=DIM, width=4, justify="right")
    rt.add_column("tool", style="bold")
    for i, name in enumerate(RITUAL, 1):
        rt.add_row(str(i), name)
    console.print(Panel(rt, title=f"[{INFO}]the 6-step ritual[/]", border_style=INFO,
                        padding=(0, 2), expand=False))
    console.print()

    if hits:
        ht = Table(show_header=True, header_style=f"bold {DIM}", box=None, padding=(0, 2))
        ht.add_column("#", style=DIM, width=3, justify="right")
        ht.add_column("trajectory", style="bold")
        ht.add_column("agent", style=DIM)
        ht.add_column("started_at", style=DIM)
        ht.add_column("task", overflow="ellipsis", max_width=40)
        for i, h in enumerate(hits, 1):
            ht.add_row(str(i), _fmt(h.get("_id"), 20), _fmt(h.get("agent_id"), 10),
                       _fmt(h.get("started_at"), 24), _fmt(h.get("task"), 40))
        console.print(ht)
        console.print()

    bar = "".join("█" if i < support else "░" for i in range(SUPPORT_THRESHOLD))
    if support >= SUPPORT_THRESHOLD:
        console.print(Panel(
            Group(
                Text(f"SUPPORT = {support} / {SUPPORT_THRESHOLD}   {bar}", style=f"bold {BIRTH}"),
                Text("THRESHOLD MET — the miner can compile this ritual into a macro now.",
                     style=f"bold {BIRTH}"),
                Text("run the miner, then watch Agent B light up.", style=DIM),
            ),
            border_style=BIRTH, padding=(1, 2), title=f"[bold {BIRTH}]⚡ READY TO BE BORN[/]"))
    elif support == SUPPORT_THRESHOLD - 1:
        console.print(Panel(
            Group(
                Text(f"SUPPORT = {support} / {SUPPORT_THRESHOLD}   {bar}", style=f"bold {INFO}"),
                Text("ONE LIVE RUN NEEDED — the next successful cold run makes support 3.",
                     style=f"bold {INFO}"),
                Text("this is the correct --warm state for the demo.", style=DIM),
            ),
            border_style=INFO, padding=(1, 2), title=f"[bold {INFO}]● PRIMED[/]"))
    else:
        console.print(Panel(
            Group(
                Text(f"SUPPORT = {support} / {SUPPORT_THRESHOLD}   {bar}", style="bold yellow"),
                Text(f"{SUPPORT_THRESHOLD - support} more successful runs needed. "
                     f"Did you forget `demo reset`?", style="bold yellow"),
            ),
            border_style="yellow", padding=(1, 2), title="[bold yellow]! NOT PRIMED[/]"))
    console.print()
    console.print(Rule(style=DIM))
    return 0


def cmd_warmup(_args) -> int:
    header("PERPETUAL — WARMUP", "ping Atlas + vector indexes", INFO)
    from . import primitives
    d = db()
    n = d.tools.count_documents({"status": "active"})
    console.print(f"[{OK}]✓ connected  db={d.name}  tools={n}[/]")
    probes = [
        ("tools_vec", "tools", "purpose_embedding", "weekly update", {"status": "active"}),
        ("skills_vec", "skills", "embedding", "button", None),
        ("memories_vec", "memories", "embedding", "button spec", None),
        ("messages_vec", "messages", "embedding", "ledger", None),
    ]
    # Empty memories is normal after reset; the others must retrieve.
    must_hit = {"tools", "skills", "messages"}
    failed = 0
    for idx, coll, path, q, flt in probes:
        try:
            if not index_queryable(d[coll], idx):
                console.print(f"[yellow]! {idx} not queryable yet[/]")
                failed += 1
                continue
        except Exception as e:
            console.print(f"[yellow]! {idx}: cannot list indexes ({type(e).__name__}: {e})[/]")
            failed += 1
            continue
        try:
            qv = primitives._query_vector(q)
        except Exception as e:
            console.print(f"[yellow]! {idx} queryable but embed failed ({type(e).__name__}: {e})[/]")
            failed += 1
            continue
        if qv is None:
            console.print(f"[{OK}]✓ {idx} queryable[/] [{DIM}](no client vector — EMBED_PROVIDER=auto)[/]")
            continue
        try:
            stage = {"$vectorSearch": {"index": idx, "path": path, "queryVector": qv,
                                       "numCandidates": 8, "limit": 3}}
            if flt:
                stage["$vectorSearch"]["filter"] = flt
            hits = list(d[coll].aggregate([stage]))
            if coll in must_hit and len(hits) == 0:
                console.print(f"[yellow]! {idx} queryable but 0 hits — Act 1 retrieval will miss[/]")
                failed += 1
                continue
            console.print(f"[{OK}]✓ {idx} queryable ({len(hits)} hits)[/]")
        except Exception as e:
            console.print(f"[yellow]! {idx} flag is queryable but $vectorSearch failed: "
                          f"{type(e).__name__}: {e}[/]")
            failed += 1
    console.print()
    if failed:
        console.print(f"[yellow]! {failed} index(es) not ready — Act 1 will hang or miss. "
                      f"Wait and rerun `make warmup`.[/]")
        console.print()
        return 1
    return 0


def cmd_agent_a(args) -> int:
    from .agent import run
    out = run(args.task, agent_id="agent-a")
    return 0 if out["outcome"] == "success" else 1


def cmd_agent_b(_args) -> int:
    from .watcher import Watcher
    Watcher("agent-b").run()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="perpetual.demo", description="PERPETUAL demo conductor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reset", help="seed.reset() + ensure_indexes(); print counts (--warm state)")
    sub.add_parser("status", help="TOOLS KNOWN, trajectory count, last 3 events")
    sub.add_parser("birth-check", help="is ritual support at 2 (one live run needed) or 3?")
    sub.add_parser("warmup", help="ping Atlas and run a cheap $vectorSearch on each index")
    a = sub.add_parser("agent-a", help="run Agent A (same as python -m perpetual.agent)")
    a.add_argument("task", nargs="?", default="send my weekly update to dana")
    sub.add_parser("agent-b", help="run Agent B (same as python -m perpetual.watcher)")
    args = ap.parse_args(argv)
    return {
        "reset": cmd_reset, "status": cmd_status, "birth-check": cmd_birth_check,
        "warmup": cmd_warmup, "agent-a": cmd_agent_a, "agent-b": cmd_agent_b,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
