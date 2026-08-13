"""MongoDB layer: client, collections, index bootstrap.

Collections:
  tools         — primitive + macro tool documents; the agent's action space IS this collection
  trajectories  — per-run step logs mined for repeated behavior
  runs          — run outcomes (feeds fitness counters)
  entities      — workplace knowledge graph nodes (people, projects, issues, channels)
  relations     — graph edges, traversed with $graphLookup
  checkpoints   — LangGraph MongoDBSaver state
"""
import os
import time

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

_client: MongoClient | None = None


def client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGODB_URI"])
    return _client


def db():
    return client()[os.environ.get("PERPETUAL_DB", "perpetual")]


VECTOR_DIMS = int(os.environ.get("EMBED_DIMS", "768"))


def ensure_indexes():
    d = db()
    for name in ("tools", "trajectories", "runs", "messages", "relations", "people", "events", "memories"):
        if name not in d.list_collection_names():
            d.create_collection(name)

    # TTL: macros unused past their horizon die (natural selection)
    d.tools.create_index("expires_at", expireAfterSeconds=0)
    d.trajectories.create_index([("run_id", 1), ("step", 1)])
    d.relations.create_index("src")
    d.relations.create_index("dst")

    _ensure_vector_index(d.tools, "tools_vec", path="purpose_embedding")
    _ensure_vector_index(d.messages, "messages_vec", path="embedding")
    _ensure_vector_index(d.memories, "memories_vec", path="embedding")


def _ensure_vector_index(coll, name: str, path: str):
    existing = {i["name"] for i in coll.list_search_indexes()}
    if name in existing:
        return
    coll.create_search_index(
        SearchIndexModel(
            name=name,
            type="vectorSearch",
            definition={
                "fields": [
                    {"type": "vector", "path": path, "numDimensions": VECTOR_DIMS, "similarity": "cosine"},
                    {"type": "filter", "path": "kind"},
                    {"type": "filter", "path": "status"},
                ]
            },
        )
    )


def wait_for_search_indexes(timeout_s: int = 300):
    """Atlas search indexes build asynchronously; block until queryable."""
    d = db()
    deadline = time.time() + timeout_s
    pending = {"tools": "tools_vec", "messages": "messages_vec", "memories": "memories_vec"}
    while pending and time.time() < deadline:
        for coll_name, idx_name in list(pending.items()):
            for info in d[coll_name].list_search_indexes():
                if info["name"] == idx_name and info.get("queryable"):
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
