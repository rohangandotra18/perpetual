"""The seven primitive tools. Each is a thin query over the seeded workplace in Atlas.

Retrieval strategy everywhere: try $vectorSearch, fall back to keyword/regex so the
system works before search indexes finish building (and offline in dev).
"""
from __future__ import annotations

import datetime as dt
import os

from . import embed, llm
from .db import db

ME = "U_MAYA"
LAST_DRAFT: dict = {"text": None}


def _vector_query(coll, index: str, path: str, query: str, limit: int, flt: dict | None = None):
    d = db()
    try:
        stage = {"$vectorSearch": {"index": index, "path": path, "queryVector": embed.embed([query])[0],
                                   "numCandidates": 200, "limit": limit}}
        if flt:
            stage["$vectorSearch"]["filter"] = flt
        return list(d[coll].aggregate([stage]))
    except Exception:
        docs = list(d[coll].find(flt or {}))
        qv = embed.embed([query])[0]
        scored = []
        for doc in docs:
            v = doc.get(path) or doc.get("embedding")
            if v:
                scored.append((embed.cosine(qv, v), doc))
            else:
                text = doc.get("text") or doc.get("purpose") or ""
                hits = sum(1 for w in query.lower().split() if w in text.lower())
                scored.append((hits * 0.01, doc))
        scored.sort(key=lambda x: -x[0])
        return [doc for _, doc in scored[:limit]]


def search_slack(query: str, channel: str | None = None, limit: int = 8) -> dict:
    flt = {"channel": channel} if channel else None
    docs = _vector_query("messages", "messages_vec", "embedding", query, limit, flt)
    return {"messages": [{"id": m["_id"], "ts": m["ts"], "channel": m["channel"],
                          "user": m["user_id"], "text": m["text"]} for m in docs]}


def list_my_issues(state: str = "closed", since_days: int = 7) -> dict:
    cutoff = (dt.datetime(2026, 8, 13) - dt.timedelta(days=since_days)).isoformat()
    q: dict = {"assignee_id": ME, "state": state}
    if state == "closed":
        q["closed_at"] = {"$gte": cutoff}
    docs = list(db().issues.find(q))
    return {"issues": [{"key": i["key"], "title": i["title"], "state": i["state"],
                        "closed_at": i.get("closed_at")} for i in docs]}


def who_did_i_delegate(topic: str | None = None) -> dict:
    """$graphLookup: start at me in `people`, walk `relations` src->dst up to 2 hops,
    so 'I delegated to John, John pulled in Priya' surfaces as a chain."""
    pipeline = [
        {"$match": {"_id": ME}},
        {"$graphLookup": {
            "from": "relations", "startWith": "$_id",
            "connectFromField": "dst", "connectToField": "src",
            "as": "chain", "maxDepth": 2, "depthField": "depth",
            "restrictSearchWithMatch": {"type": {"$in": ["delegated_to", "asked_help_of"]}},
        }},
        {"$unwind": "$chain"},
        {"$sort": {"chain.depth": 1}},
    ]
    rows = list(db().people.aggregate(pipeline))
    people = {p["_id"]: p["name"] for p in db().people.find()}
    out = []
    for r in rows:
        e = r["chain"]
        if topic and topic.lower() not in e.get("topic", "").lower():
            continue
        out.append({"from": people.get(e["src"], e["src"]), "to": people.get(e["dst"], e["dst"]),
                    "type": e["type"], "topic": e.get("topic"), "depth": e["depth"],
                    "evidence": e.get("evidence", [])})
    return {"delegations": out}


def get_voice_profile() -> dict:
    prof = db().style_profile.find_one({"user_id": ME}) or {}
    exemplars = list(db().sent_messages.find({"user_id": ME, "kind": "weekly_update"})
                     .sort("sent_at", -1).limit(2))
    return {"profile": {k: v for k, v in prof.items() if k != "_id"},
            "exemplars": [e["body"] for e in exemplars]}


def draft_message(purpose: str, bullets: list[str], voice: bool = True) -> dict:
    voice_data = get_voice_profile() if voice else {"profile": {}, "exemplars": []}
    if not llm.mock_mode():
        prompt = (f"Write a message. Purpose: {purpose}.\nContent to cover: {bullets}.\n"
                  f"Match this person's voice EXACTLY — style profile: {voice_data['profile']}\n"
                  f"Recent examples of their writing:\n---\n" + "\n---\n".join(voice_data["exemplars"]) +
                  "\nOutput only the message body.")
        text = llm.complete(prompt)
    else:
        s = voice_data["profile"].get("structure", {})
        headers = s.get("headers", ["shipped:", "in flight:", "risks:"])
        text = (f"{headers[0]}\n" + "\n".join(f"- {b}" for b in bullets[:2]) +
                f"\n\n{headers[1]}\n" + "\n".join(f"- {b}" for b in bullets[2:]) +
                f"\n\n{s.get('signoff', 'shout if you want detail.')}")
    LAST_DRAFT["text"] = text
    return {"text": text}


def send_message(to: str, subject: str, body=None) -> dict:
    text = body if isinstance(body, str) else LAST_DRAFT["text"] or ""
    db().sent_messages.insert_one({
        "user_id": ME, "kind": "weekly_update", "to": to, "subject": subject,
        "body": text, "sent_at": dt.datetime.utcnow().isoformat(), "authored_by": "perpetual"})
    return {"sent": True, "to": to, "chars": len(text)}


def create_issue(title: str, body: str = "", assignee: str | None = None) -> dict:
    top = db().issues.aggregate([
        {"$project": {"n": {"$toInt": {"$arrayElemAt": [{"$split": ["$key", "-"]}, 1]}}}},
        {"$sort": {"n": -1}}, {"$limit": 1}])
    n = next(iter(top), {"n": 100})["n"] + 1
    key = f"NW-{n}"
    db().issues.insert_one({"_id": key, "key": key, "repo": "northwind/payments",
                            "title": title, "body": body, "state": "open",
                            "assignee_id": assignee, "created_by": ME,
                            "created_at": dt.datetime.utcnow().isoformat(),
                            "closed_at": None, "source_message_id": None,
                            "authored_by": "perpetual"})
    return {"key": key, "url": f"local://issues/{key}"}


def save_to_memory(content: str, topic: str = "general") -> dict:
    """Persist a decision/spec/preference into long-term memory in Atlas."""
    vecs = embed.embed([f"{topic}: {content}"])
    doc = {"kind": "memory", "topic": topic, "content": content,
           "saved_at": dt.datetime.utcnow().isoformat()}
    if vecs is not None:
        doc["embedding"] = vecs[0]
    db().memories.insert_one(doc)
    return {"saved": True, "topic": topic, "chars": len(content)}


def recall_memory(query: str, limit: int = 3) -> dict:
    docs = _vector_query("memories", "memories_vec", "embedding", query, limit)
    return {"memories": [{"topic": m.get("topic"), "content": m.get("content"),
                          "saved_at": m.get("saved_at")} for m in docs]}


REGISTRY = {f.__name__: f for f in (
    search_slack, list_my_issues, who_did_i_delegate,
    get_voice_profile, draft_message, send_message, create_issue,
    save_to_memory, recall_memory)}

PRIMITIVE_DOCS = [
    {"name": "search_slack", "purpose": "Search the team Slack history for messages about a topic, a person, or recent work.",
     "params_schema": {"type": "object", "properties": {"query": {"type": "string"}, "channel": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "list_my_issues", "purpose": "List my GitHub issues, e.g. issues I closed recently or ones still open.",
     "params_schema": {"type": "object", "properties": {"state": {"type": "string"}, "since_days": {"type": "integer"}}}},
    {"name": "who_did_i_delegate", "purpose": "Traverse the workplace graph: who I delegated work to or asked for help, including second-hop chains.",
     "params_schema": {"type": "object", "properties": {"topic": {"type": "string"}}}},
    {"name": "get_voice_profile", "purpose": "Fetch my learned writing style profile and recent examples of messages I wrote.",
     "params_schema": {"type": "object", "properties": {}}},
    {"name": "draft_message", "purpose": "Draft a message or update covering given bullet points, written in my personal voice and style.",
     "params_schema": {"type": "object", "properties": {"purpose": {"type": "string"}, "bullets": {"type": "array", "items": {"type": "string"}}, "voice": {"type": "boolean"}}, "required": ["purpose", "bullets"]}},
    {"name": "send_message", "purpose": "Send a finished message to a person or channel (writes to the outbox).",
     "params_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject"]}},
    {"name": "create_issue", "purpose": "File a new issue in the tracker with a title, body, and optional assignee.",
     "params_schema": {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "assignee": {"type": "string"}}, "required": ["title"]}},
    {"name": "save_to_memory", "purpose": "Persist a decision, design spec, preference, or fact from this conversation into my permanent long-term memory (MongoDB Atlas), so future sessions start already knowing it. Use whenever the user says 'save this', 'remember this', or 'save to memory'. Pass a complete, specific summary as content — exact values, names, numbers.",
     "params_schema": {"type": "object", "properties": {"content": {"type": "string"}, "topic": {"type": "string"}}, "required": ["content"]}},
    {"name": "recall_memory", "purpose": "Semantic search over my permanent long-term memory from past sessions — decisions, specs, preferences, facts. ALWAYS check this FIRST when the user references anything previously discussed ('the button we designed', 'what we decided', 'like last time') — my conversation context does not survive between sessions, but this memory does.",
     "params_schema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
]
