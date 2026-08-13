"""MongoDB layer: client, collections, index bootstrap.

Collections:
  tools         — primitive + macro tool documents; the agent's action space IS this collection
  trajectories  — per-run step logs mined for repeated behavior
  memories      — saved decisions/specs; retrieved by the prompt hook
  skills        — human-authored conventions; retrieved by the prompt hook
  relations     — graph edges, traversed with $graphLookup
"""
import os
import time

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

_client: MongoClient | None = None


def client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"], tlsCAFile=certifi.where())
    return _client


def db():
    return client()[os.environ.get("PERPETUAL_DB", "perpetual")]


VECTOR_DIMS = int(os.environ.get("EMBED_DIMS", "768"))


def ensure_indexes():
    d = db()
    for name in ("tools", "trajectories", "messages", "relations", "people", "events",
                 "memories", "skills", "issues", "sent_messages", "style_profile"):
        if name not in d.list_collection_names():
            d.create_collection(name)

    # TTL: macros unused past their horizon die (natural selection)
    d.tools.create_index("expires_at", expireAfterSeconds=0)
    d.trajectories.create_index([("outcome", 1), ("started_at", 1)])
    d.relations.create_index("src")
    d.relations.create_index("dst")

    # kind/status filters are only meaningful on `tools` (tool_search pre-filter).
    _ensure_vector_index(d.tools, "tools_vec", path="purpose_embedding",
                         filters=("kind", "status"))
    _ensure_vector_index(d.messages, "messages_vec", path="embedding")
    _ensure_vector_index(d.memories, "memories_vec", path="embedding")
    _ensure_vector_index(d.skills, "skills_vec", path="embedding")


def index_queryable(coll, idx_name: str) -> bool:
    """True only if Atlas reports this search index as ready to query — not a collection scan."""
    for info in coll.list_search_indexes():
        if info.get("name") != idx_name:
            continue
        if info.get("queryable") is True:
            return True
        status = info.get("status")
        if status == "READY":
            return True
        if isinstance(status, dict) and str(status.get("state", "")).upper() in {"READY", "STEADY"}:
            return True
        return False
    return False


def _ensure_vector_index(coll, name: str, path: str, filters: tuple[str, ...] = ()):
    existing = {i["name"] for i in coll.list_search_indexes()}
    if name in existing:
        return
    fields = [
        {"type": "vector", "path": path, "numDimensions": VECTOR_DIMS, "similarity": "cosine"},
    ]
    fields.extend({"type": "filter", "path": f} for f in filters)
    coll.create_search_index(
        SearchIndexModel(name=name, type="vectorSearch", definition={"fields": fields})
    )


def wait_for_search_indexes(timeout_s: int = 300):
    """Atlas search indexes build asynchronously; block until queryable."""
    d = db()
    deadline = time.time() + timeout_s
    pending = {"tools": "tools_vec", "messages": "messages_vec",
               "memories": "memories_vec", "skills": "skills_vec"}
    while pending and time.time() < deadline:
        for coll_name, idx_name in list(pending.items()):
            if index_queryable(d[coll_name], idx_name):
                pending.pop(coll_name, None)
        if pending:
            time.sleep(3)
    if pending:
        raise TimeoutError(f"search indexes not queryable: {pending}")


if __name__ == "__main__":
    ensure_indexes()
    print("indexes ensured; waiting for queryable...")
    wait_for_search_indexes()
    print("ready")
