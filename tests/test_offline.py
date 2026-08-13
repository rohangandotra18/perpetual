"""Offline unit tests — no Atlas required.

Covers the bugs that used to live on main: guard evaluated before any step,
hook render KeyError on missing score, extra Gemini kwargs TypeErroring a
primitive, mock policy skipping ritual steps, and the compiler's only $ref.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PERPETUAL_MOCK", "1")

from perpetual import embed, llm, macro  # noqa: E402
from perpetual.demo import _contains_ritual  # noqa: E402
from perpetual.llm import RITUAL  # noqa: E402
from perpetual.miner import DATAFLOW, _bind_params, _fallback_name, _is_subsequence, ngram_hash  # noqa: E402
from perpetual.primitives import _filter_kwargs  # noqa: E402


def _load_hook():
    path = ROOT / "hooks" / "perpetual_retrieve.py"
    spec = importlib.util.spec_from_file_location("perpetual_retrieve", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class MacroTests(unittest.TestCase):
    def test_resolve_dotted_and_index(self):
        ctx = {"s1": {"messages": [{"text": "hi"}]}}
        self.assertEqual(macro._resolve({"$ref": "s1.messages.0.text"}, ctx), "hi")

    def test_resolve_missing_path_raises(self):
        with self.assertRaises(macro.MacroError):
            macro._resolve({"$ref": "s1.highlights"}, {"s1": {"messages": []}})

    def test_guard_waits_for_referenced_step(self):
        calls = []

        def a(**_):
            calls.append("a")
            return {"ready": True}

        def b(**_):
            calls.append("b")
            return {"sent": True}

        out = macro.execute_macro(
            {
                "steps": [
                    {"tool": "a", "params": {}, "save_as": "s0"},
                    {"tool": "b", "params": {}, "save_as": "s1"},
                ],
                "guard": {"$ref": "s0.ready", "equals": True},
            },
            {"a": a, "b": b},
            {},
        )
        self.assertEqual(calls, ["a", "b"])
        self.assertTrue(out["result"]["sent"])

    def test_guard_blocks_later_step_when_it_fails(self):
        calls = []

        def a(**_):
            calls.append("a")
            return {"ready": False}

        def b(**_):
            calls.append("b")
            return {"sent": True}

        with self.assertRaises(macro.MacroError):
            macro.execute_macro(
                {
                    "steps": [
                        {"tool": "a", "params": {}, "save_as": "s0"},
                        {"tool": "b", "params": {}, "save_as": "s1"},
                    ],
                    "guard": {"$ref": "s0.ready", "equals": True},
                },
                {"a": a, "b": b},
                {},
            )
        self.assertEqual(calls, ["a"])

    def test_input_guard_is_a_precondition(self):
        calls = []

        def a(**_):
            calls.append("a")
            return {}

        with self.assertRaises(macro.MacroError):
            macro.execute_macro(
                {
                    "steps": [{"tool": "a", "params": {}, "save_as": "s0"}],
                    "guard": {"$ref": "input.go", "equals": True},
                },
                {"a": a},
                {"go": False},
            )
        self.assertEqual(calls, [])

    def test_drops_extra_kwargs(self):
        def only_x(x=1):
            return {"x": x}

        out = macro.execute_macro(
            {"steps": [{"tool": "only_x", "params": {"x": 2, "y": 99, "extra": True}}]},
            {"only_x": only_x},
            {},
        )
        self.assertEqual(out["result"], {"x": 2})

    def test_ref_body_from_prior_step(self):
        def draft(purpose, bullets):
            return {"text": f"{purpose}: {len(bullets)}"}

        def send(to, subject, body=None):
            return {"sent": True, "to": to, "body": body}

        out = macro.execute_macro(
            {
                "steps": [
                    {"tool": "draft", "params": {"purpose": "weekly", "bullets": ["a"]},
                     "save_as": "s4"},
                    {"tool": "send", "params": {"to": "U_DANA", "subject": "weekly update",
                                                "body": {"$ref": "s4.text"}}},
                ]
            },
            {"draft": draft, "send": send},
            {},
        )
        self.assertEqual(out["result"]["body"], "weekly: 1")


class MinerTests(unittest.TestCase):
    def test_fallback_name_is_the_demo_name(self):
        self.assertEqual(_fallback_name("send my weekly update to dana"),
                         "weekly_update_to_dana")

    def test_bind_params_rewrites_send_body(self):
        save = {"draft_message": "s4"}
        out = _bind_params("send_message",
                           {"to": "U_DANA", "subject": "weekly update", "body": "<draft>"},
                           save)
        self.assertEqual(out["body"], {"$ref": "s4.text"})
        self.assertEqual(out["to"], "U_DANA")
        self.assertEqual(DATAFLOW[("send_message", "body")], ("draft_message", "text"))

    def test_subsequence_and_hash(self):
        ritual = list(RITUAL)
        self.assertTrue(_is_subsequence(ritual, ["noise", *ritual, "tail"]))
        self.assertFalse(_is_subsequence(ritual, ritual[:-1]))
        self.assertEqual(ngram_hash(ritual), ngram_hash(list(RITUAL)))


class DemoRitualTests(unittest.TestCase):
    def test_seed_trajectories_contain_the_ritual(self):
        data = json.loads((ROOT / "seed" / "trajectories_seed.json").read_text())
        self.assertEqual(len(data), 2)
        for traj in data:
            tools = [s["tool"] for s in traj["steps"]]
            self.assertTrue(_contains_ritual(tools, RITUAL), tools)
            self.assertEqual(traj["outcome"], "success")


class LlmMockTests(unittest.TestCase):
    def setUp(self):
        os.environ["PERPETUAL_MOCK"] = "1"

    def test_mock_walks_the_six_step_ritual(self):
        tools = [{"type": "function", "function": {"name": n, "description": n,
                                                   "parameters": {"type": "object", "properties": {}}}}
                 for n in RITUAL]
        messages = [{"role": "user", "content": "send my weekly update to dana"}]
        called = []
        for _ in range(10):
            resp = llm.chat(messages, tools)
            if not resp["tool_call"]:
                self.assertIn("done", (resp.get("content") or "").lower())
                break
            name = resp["tool_call"]["name"]
            called.append(name)
            messages.append({"role": "tool",
                             "content": json.dumps({"tool": name, "result": {}})})
        self.assertEqual(called, list(RITUAL))

    def test_mock_prefers_compiled_macro(self):
        tools = [
            {"type": "function", "function": {
                "name": "weekly_update_to_dana",
                "description": "[macro] send the weekly update",
                "parameters": {"type": "object", "properties": {}},
            }},
            *[
                {"type": "function", "function": {"name": n, "description": n,
                                                 "parameters": {"type": "object", "properties": {}}}}
                for n in RITUAL
            ],
        ]
        resp = llm.chat([{"role": "user", "content": "send my weekly update to dana"}], tools)
        self.assertEqual(resp["tool_call"]["name"], "weekly_update_to_dana")

    def test_malformed_tool_args_become_empty_dict(self):
        self.assertEqual(llm._parse_tool_args("{not json"), {})
        self.assertEqual(llm._parse_tool_args(None), {})
        self.assertEqual(llm._parse_tool_args('{"to":"U_DANA"}'), {"to": "U_DANA"})
        self.assertEqual(llm._parse_tool_args(["nope"]), {})


class HookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = _load_hook()

    def test_render_survives_missing_score_and_title(self):
        context, banner = self.hook.render({
            "skills": [{"name": "button-design", "body": "44pt", "score": 0.9}],
            "memories": [{"content": "coral pill", "topic": "button"}],  # no score
            "macros": [{"name": "weekly_update_to_dana", "purpose": "send it"}],
        })
        self.assertIn("button-design", context)
        self.assertIn("perpetual", banner)
        # memories/macros without score default to 0 and stay below MIN_SCORE
        self.assertNotIn("coral pill", context)

    def test_trigger_unigram_and_phrase(self):
        self.assertEqual(self.hook._trigger_hits("help me with the button", ["button"]), 1)
        self.assertEqual(self.hook._trigger_hits("add a call to action", ["call to action"]), 1)
        self.assertEqual(self.hook._trigger_hits("tell my manager what shipped", ["update"]), 0)

    def test_filter_kwargs_drops_unknown(self):
        def f(query: str, limit: int = 8):
            return query, limit
        self.assertEqual(_filter_kwargs(f, {"query": "x", "limit": 3, "bogus": 1}),
                         {"query": "x", "limit": 3})


class EmbedTests(unittest.TestCase):
    def test_fake_embeddings_are_stable_and_related(self):
        os.environ["EMBED_PROVIDER"] = "fake"
        a = embed.embed(["weekly update to dana"])[0]
        b = embed.embed(["weekly update to dana"])[0]
        c = embed.embed(["unrelated pineapple recipes"])[0]
        self.assertEqual(a, b)
        self.assertGreater(embed.cosine(a, b), embed.cosine(a, c))


if __name__ == "__main__":
    unittest.main()
