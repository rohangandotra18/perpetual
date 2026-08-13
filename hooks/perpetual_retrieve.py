#!/usr/bin/env python3
"""UserPromptSubmit hook — automatic semantic retrieval from Atlas.

This is what makes skills *pull themselves in*. Every prompt the user types is
embedded and $vectorSearch'd against three collections before the model ever sees it:

  skills    — reusable know-how (human-authored conventions)
  memories  — decisions/specs saved from past sessions
  tools     — including macros the agent COMPILED ITSELF, so an invented skill is
              retrieved by the same mechanism as a written one

Whatever clears the similarity threshold is injected as context. The user never calls
a "load skill" tool; typing "help me with the button" is itself the query.

Fails open: any error or slowness prints nothing and exits 0, so a bad network never
blocks a prompt.
"""
import json
import os
import pathlib
import re
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MIN_SCORE = float(os.environ.get("PERPETUAL_MIN_SCORE", "0.70"))
MARGIN = 0.04  # a 2nd skill rides along only if nearly as relevant as the 1st
BUDGET_S = float(os.environ.get("PERPETUAL_HOOK_BUDGET", "6"))
# One trigger hit must clear MIN_SCORE even if $vectorSearch is cold.
LEXICAL_FLOOR = 0.82


def _trigger_hits(prompt: str, triggers: list) -> int:
    """Unigram ∈ prompt tokens, or multi-word trigger as a substring."""
    prompt_l = prompt.lower()
    words = set(re.findall(r"[a-z]+", prompt_l))
    hits = 0
    for trig in triggers or []:
        t = str(trig).lower().strip()
        if not t:
            continue
        if " " in t:
            if t in prompt_l:
                hits += 1
        elif t in words:
            hits += 1
    return hits


def retrieve(prompt: str) -> dict:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from perpetual import embed
    from perpetual.db import db

    vecs = embed.embed([prompt])
    qv = vecs[0] if vecs else None
    d = db()

    def search(coll: str, index: str, path: str, limit: int, project: dict) -> list[dict]:
        if qv is None:
            return []
        try:
            return list(d[coll].aggregate([
                {"$vectorSearch": {"index": index, "path": path, "queryVector": qv,
                                   "numCandidates": 100, "limit": limit}},
                {"$project": {**project, "score": {"$meta": "vectorSearchScore"}}},
            ]))
        except Exception:
            return []

    # HYBRID: $vectorSearch fused with trigger matching (unigrams + phrases).
    # Collection is tiny — scan triggers in Python so "call to action" works.
    sk = search("skills", "skills_vec", "embedding", 4,
                {"name": 1, "title": 1, "body": 1, "triggers": 1})
    by_name = {x["name"]: {**x, "score": float(x.get("score") or 0.0)}
               for x in sk if x.get("name")}
    for s in d.skills.find({}, {"name": 1, "title": 1, "body": 1, "triggers": 1}):
        name = s.get("name")
        if not name:
            continue
        hits = _trigger_hits(prompt, s.get("triggers") or [])
        if name not in by_name:
            if not hits:
                continue
            by_name[name] = {**s, "score": 0.0}
        by_name[name]["lexical"] = hits
        score = float(by_name[name].get("score") or 0.0)
        if hits:
            score = max(score, LEXICAL_FLOOR) + 0.08 * min(hits, 2)
        by_name[name]["score"] = score
    fused = sorted(by_name.values(), key=lambda x: -x["score"])

    return {
        "skills": fused[:4],  # render() applies MIN_SCORE + MARGIN
        "memories": search("memories", "memories_vec", "embedding", 3,
                           {"topic": 1, "content": 1, "saved_at": 1}),
        "macros": [t for t in search("tools", "tools_vec", "purpose_embedding", 3,
                                     {"name": 1, "purpose": 1, "kind": 1, "born_at": 1})
                   if t.get("kind") == "macro"],
    }


def render(hits: dict) -> tuple[str, str]:
    """-> (context injected into the model, one-line banner shown to the user)"""
    blocks, badges = [], []

    skills = [s for s in hits["skills"] if s.get("score", 0) >= MIN_SCORE]
    if len(skills) > 1:  # avoid dragging in a loosely-related second convention
        skills = [s for s in skills if s.get("score", 0) >= skills[0].get("score", 0) - MARGIN]
    if skills:
        badges.append(f"{len(skills)} skill" + ("s" if len(skills) > 1 else ""))
        for s in skills:
            how = "vector + trigger match" if s.get("lexical") else "vector"
            blocks.append(f"### Team convention — {s['title']} (relevance {s['score']:.2f}, {how})\n{s['body']}")

    mems = [m for m in hits["memories"] if m.get("score", 0) >= MIN_SCORE]
    if mems:
        badges.append(f"{len(mems)} memor" + ("ies" if len(mems) > 1 else "y"))
        lines = [f"- [{m.get('topic', 'general')}, saved {str(m.get('saved_at', ''))[:10]}] {m['content']}"
                 for m in mems]
        blocks.append("### Decisions already made in past sessions\n" + "\n".join(lines))

    macros = [t for t in hits["macros"] if t.get("score", 0) >= MIN_SCORE]
    if macros:
        badges.append(f"{len(macros)} compiled skill" + ("s" if len(macros) > 1 else ""))
        lines = [f"- `{t['name']}` — {t['purpose']} (compiled by an agent from repeated behavior)"
                 for t in macros]
        blocks.append("### Skills this agent compiled itself — prefer these over doing the steps manually\n"
                      + "\n".join(lines))

    if not blocks:
        return "", ""
    context = ("<perpetual-memory source=\"MongoDB Atlas · $vectorSearch\">\n"
               "Retrieved automatically by semantic similarity to what the user just typed. "
               "Treat as established context — do not re-ask for it.\n\n"
               + "\n\n".join(blocks) + "\n</perpetual-memory>")
    return context, "⚡ perpetual: recalled " + ", ".join(badges) + " from Atlas"


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    prompt = (payload.get("prompt") or "").strip()
    if len(prompt) < 4:
        sys.exit(0)

    result: dict = {}

    def work():
        try:
            result["hits"] = retrieve(prompt)
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout=BUDGET_S)
    if "hits" not in result:
        sys.exit(0)  # slow or failed — never block the prompt

    context, banner = render(result["hits"])
    if not context:
        sys.exit(0)
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context},
        "systemMessage": banner,
    }))


if __name__ == "__main__":
    main()
