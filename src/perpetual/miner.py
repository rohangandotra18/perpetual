"""The miner: find the ritual, compile it into a tool.

This is the part of Perpetual that turns *behavior* into *capability*.

  1. MINE  — a real MongoDB aggregation over `trajectories`:
             $match success -> $unwind steps -> $setWindowFields (sliding window of N
             consecutive tool names, partitioned per trajectory) -> keep full-length
             windows -> $group by the window array, counting DISTINCT trajectories
             ($addToSet + $size) -> require support >= MIN_SUPPORT.
             Tried at N = 6, then 5, then 4 — longest ritual wins.

  2. COMPILE — the winning n-gram becomes a declarative macro document that
             macro.execute_macro can run: exemplar args kept as literals, except
             observed dataflow (send_message.body <- draft_message.text) which is
             rewritten into a {"$ref": "sN.text"} binding.

  3. BIRTH — insert into `tools` (so the agent's $vectorSearch action space grows
             9 -> 10) and emit an `events` doc that the change stream delivers to
             Agent B.

Run:  PYTHONPATH=src python -m perpetual.miner [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

from . import embed, llm
from .db import db

console = Console()

MIN_SUPPORT = 3
NGRAM_SIZES = (6, 5, 4)
MACRO_TTL_DAYS = 7

# Observed dataflow: (consumer tool, arg name) <- (producer tool, output field).
# Derived from the trajectories, not hardcoded intent: send_message's body is always
# the text draft_message just produced ("<draft from step 4>" in the logs).
DATAFLOW = {
    ("send_message", "body"): ("draft_message", "text"),
}

_STOPWORDS = {"send", "do", "make", "write", "get", "create", "please", "run",
              "my", "me", "the", "a", "an", "for", "out", "up"}


# ---------------------------------------------------------------- mining ----

def ngram_hash(ngram: list[str]) -> str:
    return hashlib.sha1("→".join(ngram).encode()).hexdigest()[:16]


def mining_pipeline(n: int) -> list[dict]:
    """The pipeline that prints on stage. Genuine server-side sequence mining."""
    return [
        {"$match": {"outcome": "success"}},
        {"$unwind": "$steps"},
        {"$setWindowFields": {
            "partitionBy": "$_id",
            "sortBy": {"steps.i": 1},
            "output": {
                "window_tools": {
                    "$push": "$steps.tool",
                    "window": {"documents": [0, n - 1]},
                }
            },
        }},
        # tail windows are short — only full-length n-grams count
        {"$match": {"$expr": {"$eq": [{"$size": "$window_tools"}, n]}}},
        {"$group": {
            "_id": "$window_tools",
            "trajectory_ids": {"$addToSet": "$_id"},
            "occurrences": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0,
            "ngram": "$_id",
            "trajectory_ids": 1,
            "occurrences": 1,
            "support": {"$size": "$trajectory_ids"},   # DISTINCT trajectories
        }},
        {"$sort": {"support": -1, "occurrences": -1}},
    ]


def _is_subsequence(small: list[str], big: list[str]) -> bool:
    return any(big[i:i + len(small)] == small for i in range(len(big) - len(small) + 1))


def mine(min_support: int = MIN_SUPPORT) -> tuple[list[dict], list[dict]]:
    """Return (winners, all_candidates). Winners are sorted by (len desc, support desc)
    and exclude n-grams already compiled into a macro (or contained in one — a macro
    that already covers the sequence makes its sub-windows redundant)."""
    d = db()
    existing = list(d.tools.find({"kind": "macro"}, {"steps.tool": 1}))
    compiled = {ngram_hash([s["tool"] for s in t.get("steps", [])]) for t in existing}
    compiled_ngrams = [[s["tool"] for s in t.get("steps", [])] for t in existing]

    candidates: list[dict] = []
    winners: list[dict] = []
    for n in NGRAM_SIZES:
        rows = list(d.trajectories.aggregate(mining_pipeline(n)))
        for r in rows:
            r["n"] = n
            r["ngram_hash"] = ngram_hash(r["ngram"])
            r["already_compiled"] = (r["ngram_hash"] in compiled or
                                     any(_is_subsequence(r["ngram"], c) for c in compiled_ngrams))
            candidates.append(r)
            if r["support"] >= min_support and not r["already_compiled"]:
                winners.append(r)
        if winners:
            break  # longest n first: stop as soon as a size yields a winner

    winners.sort(key=lambda r: (-r["n"], -r["support"]))
    return winners, candidates


# -------------------------------------------------------------- compiling ----

def _exemplar(trajectory_ids: list[str], ngram: list[str]) -> tuple[dict, int]:
    """Most recent successful trajectory containing the sequence -> (doc, start index)."""
    docs = list(db().trajectories.find({"_id": {"$in": trajectory_ids}}))
    docs.sort(key=lambda t: t.get("started_at") or "", reverse=True)
    for t in docs:
        steps = sorted(t["steps"], key=lambda s: s["i"])
        tools = [s["tool"] for s in steps]
        for start in range(len(tools) - len(ngram) + 1):
            if tools[start:start + len(ngram)] == ngram:
                return t, start
    raise RuntimeError(f"no exemplar trajectory contains {ngram}")


def _bind_params(tool: str, args: dict, save_as_by_tool: dict[str, str]) -> dict:
    """Keep exemplar args as literals, except args whose value was observably produced
    by an earlier step in this same window — those become $ref bindings."""
    out: dict = {}
    for k, v in (args or {}).items():
        producer = DATAFLOW.get((tool, k))
        if producer:
            ptool, pfield = producer
            src = save_as_by_tool.get(ptool)
            if src:
                out[k] = {"$ref": f"{src}.{pfield}"}
                continue
        out[k] = v
    return out


def _fallback_name(task: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", (task or "compiled ritual").lower())
             if w not in _STOPWORDS]
    return "_".join(words[:5]) or "compiled_ritual"


def _name_and_purpose(ngram: list[str], task: str) -> tuple[str, str]:
    """ONE llm.complete() call; deterministic fallback in mock mode / on failure."""
    fallback = (_fallback_name(task),
                f'I handle the recurring request "{task}" end to end — I run '
                f"{', '.join(ngram)} in a single call.")
    prompt = (
        "I am an AI agent that noticed I repeat this exact tool sequence:\n"
        f"  {' -> '.join(ngram)}\n"
        f"The task I was given each time was: \"{task}\".\n"
        "Name this compiled skill and describe it.\n"
        'Reply with ONLY minified JSON: {"name":"snake_case_name","purpose":"one sentence"}\n'
        'The name must be snake_case like "weekly_update_to_boss". '
        "The purpose must be ONE sentence in the first person describing what ritual "
        "I automate, phrased so it can be matched by semantic search."
    )
    try:
        raw = (llm.complete(prompt) or "").strip()
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return fallback
        data = json.loads(m.group(0))
        name = re.sub(r"[^a-z0-9_]", "", str(data["name"]).strip().lower().replace(" ", "_"))
        purpose = str(data["purpose"]).strip()
        if not name or not purpose:
            return fallback
        return name, purpose
    except Exception as e:  # noqa: BLE001 — naming must never block a birth
        console.print(f"[dim]llm naming failed ({type(e).__name__}), using fallback[/dim]")
        return fallback


def compile_macro(winner: dict) -> dict:
    """Turn a mined n-gram into an executable macro document."""
    ngram = winner["ngram"]
    exemplar, start = _exemplar(winner["trajectory_ids"], ngram)
    steps_sorted = sorted(exemplar["steps"], key=lambda s: s["i"])
    window = steps_sorted[start:start + len(ngram)]

    save_as_by_tool = {s["tool"]: f"s{idx}" for idx, s in enumerate(window)}

    steps = []
    for idx, s in enumerate(window):
        steps.append({
            "tool": s["tool"],
            "params": _bind_params(s["tool"], s.get("args", {}), save_as_by_tool),
            "save_as": f"s{idx}",
        })

    name, purpose = _name_and_purpose(ngram, exemplar.get("task", ""))
    vec = embed.embed([purpose])
    now = dt.datetime.utcnow()

    doc = {
        "name": name,
        "kind": "macro",
        "purpose": purpose,
        "purpose_embedding": vec[0] if vec else None,
        "input_schema": {"type": "object",
                         "properties": {"note": {"type": "string"}},
                         "required": []},
        "steps": steps,
        "guard": None,
        "born_from": {"trajectory_ids": sorted(winner["trajectory_ids"]),
                      "ngram_hash": winner["ngram_hash"]},
        "born_at": now.isoformat(),
        "fitness": {"calls": 0, "successes": 0},
        "status": "active",
        # BSON Date — Atlas TTL indexes ignore ISO strings
        "expires_at": now + dt.timedelta(days=MACRO_TTL_DAYS),
    }
    if vec is None:  # EMBED_PROVIDER=auto: Atlas populates it server-side
        doc.pop("purpose_embedding")
    return doc


def birth(doc: dict, winner: dict) -> dict:
    """Insert the macro + emit the tool_born event the change stream is watching."""
    d = db()
    d.tools.insert_one(doc)
    d.events.insert_one({
        "type": "tool_born",
        "ts": dt.datetime.utcnow().isoformat(),
        "payload": {"name": doc["name"], "ngram": winner["ngram"], "support": winner["support"]},
    })
    return doc


# ------------------------------------------------------------------- cli ----

def _print_candidates(candidates: list[dict], winners: list[dict]):
    table = Table(title="MINING  ·  $setWindowFields sequence mining over trajectories",
                  header_style="bold magenta", border_style="magenta")
    table.add_column("N", justify="right")
    table.add_column("n-gram")
    table.add_column("support", justify="right")
    table.add_column("occurrences", justify="right")
    table.add_column("status")
    win_hashes = {w["ngram_hash"] for w in winners}
    for r in sorted(candidates, key=lambda r: (-r["n"], -r["support"]))[:20]:
        if r["already_compiled"]:
            status = "[yellow]already compiled[/yellow]"
        elif r["ngram_hash"] in win_hashes:
            status = "[bold green]RITUAL DETECTED[/bold green]"
        elif r["support"] < MIN_SUPPORT:
            status = f"[dim]below threshold (<{MIN_SUPPORT})[/dim]"
        else:
            status = "[dim]—[/dim]"
        table.add_row(str(r["n"]), " → ".join(r["ngram"]), str(r["support"]),
                      str(r["occurrences"]), status)
    console.print(table)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="perpetual.miner")
    ap.add_argument("--dry-run", action="store_true",
                    help="mine and print candidates without compiling or inserting")
    ap.add_argument("--min-support", type=int, default=MIN_SUPPORT)
    args = ap.parse_args(argv)

    d = db()
    before = d.tools.count_documents({})

    console.rule("[bold cyan]PERPETUAL MINER[/bold cyan]")
    console.print(f"[dim]db={d.name}  trajectories={d.trajectories.count_documents({})}  "
                  f"tools={before}  min_support={args.min_support}[/dim]\n")

    winners, candidates = mine(min_support=args.min_support)
    _print_candidates(candidates, winners)

    if not winners:
        best = max((r["support"] for r in candidates), default=0)
        console.print(Panel(
            f"No ritual reached support ≥ {args.min_support} (best support = {best}).\n"
            "Nothing compiled — the agent keeps doing it the slow way.",
            title="[yellow]NO BIRTH[/yellow]", border_style="yellow"))
        return 0

    w = winners[0]
    console.print(f"\n[bold]winner:[/bold] {' → '.join(w['ngram'])}  "
                  f"[green]support={w['support']}[/green]  hash={w['ngram_hash']}\n")

    if args.dry_run:
        console.print(Panel("[dim]--dry-run: candidate found, nothing written.[/dim]",
                            title="[cyan]DRY RUN[/cyan]", border_style="cyan"))
        return 0

    doc = compile_macro(w)
    birth(doc, w)

    pretty = {k: v for k, v in doc.items() if k != "purpose_embedding"}
    if "purpose_embedding" in doc and doc["purpose_embedding"]:
        v = doc["purpose_embedding"]
        pretty["purpose_embedding"] = f"<{len(v)}-dim vector: [{v[0]:.4f}, {v[1]:.4f}, ...]>"
    console.print(Panel(JSON(json.dumps(pretty, default=str, indent=2)),
                        title=f"[bold green]✦ NEW TOOL BORN: {doc['name']} ✦[/bold green]",
                        subtitle=f"[dim]compiled from {w['support']} observed runs[/dim]",
                        border_style="green", expand=False))

    after = d.tools.count_documents({})
    console.print(f"\n[bold white on green] TOOLS KNOWN: {before} -> {after} [/bold white on green]\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def mine_and_compile(min_support: int = MIN_SUPPORT) -> dict | None:
    """One-call API for the MCP server: mine, compile, and birth the top ritual.
    Returns the born macro doc, or None if no ritual has enough support."""
    winners, _ = mine(min_support)
    if not winners:
        return None
    doc = compile_macro(winners[0])
    return birth(doc, winners[0])
