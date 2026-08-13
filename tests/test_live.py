"""Live Atlas smoke tests. Skipped when MONGODB_URI is unset.

Does not reset the demo database. Destructive end-to-end (reset / agent / miner)
runs against PERPETUAL_DB=perpetual_ci from the operator shell, not here.
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def _have_atlas() -> bool:
    return bool(os.environ.get("MONGODB_URI"))


@unittest.skipUnless(_have_atlas(), "MONGODB_URI not set — copy .env.example to .env")
class LiveAtlasSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from perpetual.db import db, index_queryable
        cls.db = db()
        cls._index_queryable = staticmethod(index_queryable)

    def test_ping_and_seeded_counts(self):
        d = self.db
        self.assertGreaterEqual(d.tools.count_documents({"kind": "primitive", "status": "active"}), 9)
        self.assertGreaterEqual(d.people.count_documents({}), 5)
        self.assertGreaterEqual(d.messages.count_documents({}), 10)
        self.assertGreaterEqual(d.skills.count_documents({}), 1)

    def test_vector_indexes_queryable(self):
        d = self.db
        for coll, name in (("tools", "tools_vec"), ("messages", "messages_vec"),
                           ("skills", "skills_vec"), ("memories", "memories_vec")):
            self.assertTrue(self._index_queryable(d[coll], name), f"{name} not queryable")

    def test_primitives_return_workplace_data(self):
        os.environ.setdefault("PERPETUAL_MOCK", "1")
        from perpetual import primitives
        slack = primitives.search_slack("ledger", limit=3)
        self.assertIn("messages", slack)
        issues = primitives.list_my_issues("closed", 7)
        self.assertGreaterEqual(len(issues["issues"]), 1)
        deleg = primitives.who_did_i_delegate()
        tos = {row["to"] for row in deleg["delegations"]}
        self.assertTrue(any("John" in t for t in tos), tos)
        voice = primitives.get_voice_profile()
        self.assertEqual(voice["profile"].get("user_id"), "U_MAYA")

    def test_ritual_support_is_at_least_seeded(self):
        from perpetual.demo import ritual_support
        support, hits = ritual_support()
        self.assertGreaterEqual(support, 2, "reset seeds two successful ritual trajectories")
        self.assertEqual(len(hits), support)

    def test_tool_search_returns_named_primitives(self):
        from perpetual.agent import tool_search
        docs = tool_search("send my weekly update to dana", limit=12)
        names = {d["name"] for d in docs}
        self.assertTrue({"search_slack", "send_message"} & names, names)


if __name__ == "__main__":
    unittest.main()
