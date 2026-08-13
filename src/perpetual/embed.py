"""Embedding providers.

fake   — deterministic hash-based vectors (offline dev; pipeline mechanics identical)
gemini — Gemini embeddings via OpenAI-compatible endpoint (real semantic vectors)
auto   — no-op: Atlas Automated Embeddings populates the field in-database
"""
import hashlib
import math
import os

import httpx

DIMS = int(os.environ.get("EMBED_DIMS", "768"))


def provider() -> str:
    return os.environ.get("EMBED_PROVIDER", "fake")


def embed(texts: list[str]) -> list[list[float]] | None:
    p = provider()
    if p == "auto":
        return None  # Atlas does it server-side
    if p == "gemini":
        out: list[list[float]] = []
        for i in range(0, len(texts), 100):  # API batch cap
            r = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/embeddings",
                headers={"Authorization": f"Bearer {os.environ['GEMINI_API_KEY']}"},
                json={"model": "gemini-embedding-001", "input": texts[i:i + 100],
                      "dimensions": DIMS},
                timeout=60,
            )
            r.raise_for_status()
            out.extend(d["embedding"] for d in r.json()["data"])
        return out
    return [_fake(t) for t in texts]


def _fake(text: str) -> list[float]:
    """Stable pseudo-embedding: token hashes scattered into DIMS buckets, L2-normalized.
    Shares buckets across shared tokens, so related texts genuinely score closer."""
    vec = [0.0] * DIMS
    for tok in text.lower().split():
        h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:8], "big")
        vec[h % DIMS] += 1.0
        vec[(h >> 16) % DIMS] += 0.5
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
