"""Macro spec + executor — the heart of Perpetual.

A macro is a DECLARATIVE tool the agent compiled from its own repeated behavior:
a linear DAG of primitive calls with $ref parameter bindings. No codegen, no exec():
the tool document is readable JSON you can put on a projector.

Macro document shape (lives in the `tools` collection, kind="macro"):
{
  "name": "weekly_update_to_dana",
  "kind": "macro",
  "purpose": "Assemble and send my weekly update ...",   # vector-indexed
  "input_schema": {"type": "object", "properties": {}},
  "steps": [
    {"tool": "search_slack",  "params": {"query": "maya work this week"}, "save_as": "s0"},
    {"tool": "list_my_issues","params": {"state": "closed"},              "save_as": "s1"},
    {"tool": "draft_message", "params": {"purpose": "weekly update",
                                        "bullets": ["..."]},             "save_as": "s4"},
    {"tool": "send_message",  "params": {"to": "U_DANA",
                                        "body": {"$ref": "s4.text"}}}
  ],
  "guard": null,                    # optional {"$ref": ..., "equals": ...}
  "fitness": {"calls": 0, "successes": 0},
  "born_at": ..., "born_from": {"trajectory_ids": [...], "ngram_hash": "..."},
  "expires_at": ...                 # BSON Date so Atlas TTL can delete it
}
"""
from __future__ import annotations

import inspect
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


def _filter_kwargs(fn, params: dict) -> dict:
    sig = inspect.signature(fn)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return dict(params)
    allowed = {
        k for k, p in sig.parameters.items()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return {k: v for k, v in (params or {}).items() if k in allowed}


def _eval_guard(guard: dict, ctx: dict) -> None:
    actual = _resolve({"$ref": guard["$ref"]}, ctx)
    if actual != guard.get("equals"):
        raise MacroError(
            f"guard failed: {guard['$ref']} == {actual!r}, wanted {guard.get('equals')!r}"
        )


def execute_macro(macro: dict, registry: dict[str, Primitive], inputs: dict,
                  on_step: Callable[[int, str, dict], None] | None = None) -> dict:
    """Run a macro doc against the primitive registry.

    Returns {"steps": {save_as: result, ...}, "result": last_step_result}.
    on_step(i, tool_name, resolved_params) lets the TUI narrate each step.

    A guard is checked as soon as its $ref is resolvable — so an `input.*` guard
    is a precondition, and an `s4.*` guard runs after that step is saved (in time
    to stop a later send_message) rather than failing immediately at start.
    """
    ctx: dict[str, Any] = {"input": inputs}

    guard = macro.get("guard")
    guard_done = False

    def maybe_guard() -> None:
        nonlocal guard_done
        if not guard or guard_done:
            return
        root = str(guard.get("$ref") or "").split(".")[0]
        if root not in ctx:
            return
        _eval_guard(guard, ctx)
        guard_done = True

    maybe_guard()

    last: Any = None
    for i, step in enumerate(macro["steps"]):
        tool_name = step["tool"]
        fn = registry.get(tool_name)
        if fn is None:
            raise MacroError(f"unknown primitive in macro: {tool_name}")
        params = _resolve(step.get("params", {}), ctx)
        params = _filter_kwargs(fn, params if isinstance(params, dict) else {})
        if on_step:
            on_step(i, tool_name, params)
        last = fn(**params)
        if step.get("save_as"):
            ctx[step["save_as"]] = last
        maybe_guard()

    if guard and not guard_done:
        raise MacroError(f"guard $ref never resolved: {guard.get('$ref')}")
    return {"steps": {k: v for k, v in ctx.items() if k != "input"}, "result": last}
