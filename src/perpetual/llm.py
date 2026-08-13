"""LLM client: Gemini (OpenAI-compatible endpoint) with a deterministic mock mode.

Mock mode (PERPETUAL_MOCK=1 or no key) lets the entire pipeline — retrieval, trajectory
logging, mining, macro birth, skill transfer — run end-to-end offline. The mock policy
performs the weekly-update ritual the same way the real model does.
"""
import json
import os

import httpx

RITUAL = ["search_slack", "list_my_issues", "who_did_i_delegate",
          "get_voice_profile", "draft_message", "send_message"]


GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def mock_mode() -> bool:
    return os.environ.get("PERPETUAL_MOCK") == "1" or not os.environ.get("GEMINI_API_KEY")


def chat(messages: list[dict], tools: list[dict] | None = None,
         model: str | None = None, temperature: float = 0.0) -> dict:
    """Returns {"content": str|None, "tool_call": {"name":..., "args": {...}}|None}."""
    if mock_mode():
        return _mock(messages, tools or [])
    body = {
        "model": model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
    r = httpx.post(
        f"{GEMINI_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['GEMINI_API_KEY']}"},
        json=body, timeout=90,
    )
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    tc = None
    if msg.get("tool_calls"):
        c = msg["tool_calls"][0]
        tc = {"name": c["function"]["name"], "args": json.loads(c["function"]["arguments"] or "{}")}
    return {"content": msg.get("content"), "tool_call": tc}


def _mock(messages: list[dict], tools: list[dict]) -> dict:
    available = {t["function"]["name"] for t in tools}
    done = [json.loads(m["content"])["tool"] for m in messages
            if m["role"] == "tool" and m.get("content", "").startswith("{")]
    task = next((m["content"] for m in messages if m["role"] == "user"), "").lower()

    # Prefer a compiled macro if its meaningful name tokens appear in the task.
    # Require 2+ content tokens (skip "to"/"my"/short bits) so "to" alone cannot match.
    _skip = {"send", "do", "make", "write", "get", "create", "please", "run",
             "my", "me", "the", "a", "an", "for", "out", "up", "to", "of", "in"}
    for t in tools:
        name = t["function"]["name"]
        if t["function"].get("description", "").startswith("[macro]") and not done:
            tokens = [w for w in name.split("_") if w not in _skip and len(w) > 2]
            need = min(2, len(tokens)) or 1
            if tokens and sum(1 for w in tokens if w in task) >= need:
                return {"content": None, "tool_call": {"name": name, "args": {}}}

    mock_args = {
        "search_slack": {"query": "maya work this week", "limit": 8},
        "list_my_issues": {"state": "closed", "since_days": 7},
        "who_did_i_delegate": {},
        "get_voice_profile": {},
        "draft_message": {"purpose": "weekly update to dana",
                          "bullets": ["ledger migration phase 2", "webhook hardening",
                                      "delegations status", "closed issues"]},
        "send_message": {"to": "U_DANA", "subject": "weekly update", "body": {"$last_draft": True}},
    }
    for step in RITUAL:
        if step not in done and step in available:
            return {"content": None, "tool_call": {"name": step, "args": mock_args[step]}}
    return {"content": "done: weekly update sent.", "tool_call": None}


def complete(prompt: str, model: str | None = None) -> str:
    """Plain completion helper (macro naming, drafting)."""
    if mock_mode():
        return ""
    return chat([{"role": "user", "content": prompt}], model=model)["content"] or ""
