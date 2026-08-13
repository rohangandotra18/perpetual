"""Macro spec + executor — the heart of Myelin.

A macro is a DECLARATIVE tool the agent compiled from its own repeated behavior:
a linear DAG of primitive calls with $ref parameter bindings. No codegen, no exec():
the tool document is readable JSON you can put on a projector.

Macro document shape (lives in the `tools` collection, kind="macro"):
{
  "name": "weekly_update_to_boss",
  "kind": "macro",
  "purpose": "Assemble and send my weekly update ...",   # vector-indexed
  "input_schema": {"type": "object", "properties": {"week": {"type": "string"}}},
  "steps": [
    {"tool": "search_slack",  "params": {"query": {"$ref": "input.week"}}, "save_as": "s1"},
    {"tool": "list_my_issues","params": {"state": "closed"},               "save_as": "s2"},
    {"tool": "draft_message", "params": {"context": {"$ref": "s1.messages"},
                                          "extra":   {"$ref": "s2.issues"}}, "save_as": "s3"},
    {"tool": "send_message",  "params": {"to": "boss", "body": {"$ref": "s3.text"}}}
  ],
  "guard": null,                    # optional {"$ref": ..., "equals": ...} precondition
  "stats": {"invocations": 0, "successes": 0},
  "born_at": ..., "born_from_run": ..., "expires_at": ...
}
"""
from __future__ import annotations

from typing import Any, Callable

Primitive = Callable[..., Any]


class MacroError(Exception):
    pass


def _resolve(value: Any, ctx: dict) -> Any:
    """Resolve {"$ref": "s1.messages.0.text"} against the step context; recurse into containers."""
    if isinstance(value, dict):
        if set(value.keys()) == {"$ref"}:
            cur: Any = ctx
            for part in value["$ref"].split("."):
                if isinstance(cur, dict):
                    if part not in cur:
                        raise MacroError(f"$ref path not found: {value['$ref']} (missing '{part}')")
                    cur = cur[part]
                elif isinstance(cur, list):
                    try:
                        cur = cur[int(part)]
                    except (ValueError, IndexError) as e:
                        raise MacroError(f"$ref bad list index in {value['$ref']}: {part}") from e
                else:
                    raise MacroError(f"$ref cannot descend into {type(cur).__name__}: {value['$ref']}")
            return cur
        return {k: _resolve(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, ctx) for v in value]
    return value


def execute_macro(macro: dict, registry: dict[str, Primitive], inputs: dict,
                  on_step: Callable[[int, str, dict], None] | None = None) -> dict:
    """Run a macro doc against the primitive registry.

    Returns {"steps": {save_as: result, ...}, "result": last_step_result}.
    on_step(i, tool_name, resolved_params) lets the TUI narrate each step.
    """
    ctx: dict[str, Any] = {"input": inputs}

    guard = macro.get("guard")
    if guard:
        actual = _resolve({"$ref": guard["$ref"]}, ctx)
        if actual != guard.get("equals"):
            raise MacroError(f"guard failed: {guard['$ref']} == {actual!r}, wanted {guard.get('equals')!r}")

    last: Any = None
    for i, step in enumerate(macro["steps"]):
        tool_name = step["tool"]
        fn = registry.get(tool_name)
        if fn is None:
            raise MacroError(f"unknown primitive in macro: {tool_name}")
        params = _resolve(step.get("params", {}), ctx)
        if on_step:
            on_step(i, tool_name, params)
        last = fn(**params)
        if step.get("save_as"):
            ctx[step["save_as"]] = last
    return {"steps": {k: v for k, v in ctx.items() if k != "input"}, "result": last}
