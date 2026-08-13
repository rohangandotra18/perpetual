"""Load the seed corpus into Atlas and register the primitive tools."""
import datetime as dt
import json
import pathlib
import sys

from . import embed
from .db import db, ensure_indexes
from .primitives import PRIMITIVE_DOCS


def _repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "seed").is_dir() and (p / "pyproject.toml").exists():
            return p
    return here.parents[2]


SEED_DIR = _repo_root() / "seed"


def _load(name: str):
    p = SEED_DIR / f"{name}.json"
    if not p.exists():
        print(f"  ! missing seed file {p.name}, skipping")
        return []
    data = json.loads(p.read_text())
    return data if isinstance(data, list) else [data]


def _embed_field(docs: list[dict], text_key: str, out_key: str = "embedding"):
    texts = [d.get(text_key, "") for d in docs]
    vecs = embed.embed(texts)
    if vecs is None:  # Atlas Automated Embeddings handles it
        return docs
    for d, v in zip(docs, vecs):
        d[out_key] = v
    return docs


def reset(full: bool = True):
    d = db()
    names = ["people", "messages", "issues", "sent_messages", "style_profile",
             "relations", "trajectories", "events", "memories", "skills"]
    if full:
        names.append("tools")
    for n in names:
        d[n].delete_many({})
    print("collections cleared" + ("" if full else " (kept tools)"))

    def _insert(coll, docs):
        if docs:
            coll.insert_many(docs)

    _insert(d.people, _load("people"))
    _insert(d.messages, _embed_field(_load("messages"), "text"))
    _insert(d.issues, _load("issues"))
    _insert(d.sent_messages, _load("sent_messages"))
    _insert(d.style_profile, _load("style_profile"))
    _insert(d.relations, _load("relations"))
    _insert(d.trajectories, _load("trajectories_seed"))

    skills = _load("skills")
    for sk in skills:  # embed the natural-language description, not the body
        sk["_embed_text"] = f"{sk.get('title', '')}. {sk.get('description', '')} {' '.join(sk.get('triggers', []))}"
    skills = _embed_field(skills, "_embed_text")
    for sk in skills:
        sk.pop("_embed_text", None)
    _insert(d.skills, skills)

    if full:
        tools = []
        for p in PRIMITIVE_DOCS:
            tools.append({**p, "kind": "primitive", "status": "active",
                          "fitness": {"calls": 0, "successes": 0},
                          "born_at": dt.datetime.utcnow().isoformat(), "expires_at": None})
        tools = _embed_field(tools, "purpose", "purpose_embedding")
        d.tools.insert_many(tools)

    print(f"seeded: {d.skills.count_documents({})} skills, "
          f"{d.messages.count_documents({})} messages, "
          f"{d.issues.count_documents({})} issues, "
          f"{d.sent_messages.count_documents({})} sent, "
          f"{d.relations.count_documents({})} edges, "
          f"{d.trajectories.count_documents({})} prior trajectories, "
          f"{d.tools.count_documents({})} tools")


if __name__ == "__main__":
    ensure_indexes()
    reset(full="--keep-tools" not in sys.argv)
