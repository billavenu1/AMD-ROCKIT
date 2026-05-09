# vision/hip_vs/hipvs_query.py

import numpy as np
from . import registry
from .ingestion import (
    load_image_hipVS,
    load_video_hipVS,
    rebuild_image_hipVS,
    rebuild_video_hipVS,
)
from api.llm_provider import embed_text


def _embed_text(text: str) -> np.ndarray:
    """Embed a text string using the centralized llm_provider (no duplicate clients)."""
    vector = embed_text(text=text, model="gemini-embedding-2", output_dimensionality=2048)
    return np.array(vector, dtype=np.float32)


# ── Query functions ───────────────────────────────────────────────────────────

async def query_image_hipVS(text: str, top_k: int = 5):
    """
    Search image_index.
    Auto-loads the index if not in VRAM (NVMe restore → SurrealDB build).
    """
    store = await load_image_hipVS()
    q = _embed_text(text)
    return store.search(q, top_k)


async def query_video_hipVS(text: str, top_k: int = 5):
    """
    Search video_index.
    Auto-loads the index if not in VRAM (NVMe restore → SurrealDB build).
    """
    store = await load_video_hipVS()
    q = _embed_text(text)
    results = store.search(q, top_k)

    # parse "video_path@timestamp_sec" compound ID back into structured output
    parsed = []
    for id_str, score in results:
        path, ts = id_str.rsplit("@", 1)
        parsed.append({"video": path, "timestamp_sec": float(ts), "score": score})
    return parsed


# ── Rebuild functions (call after new data is ingested into SurrealDB) ────────

async def rebuild_image_index():
    """
    Force a full CAGRA graph rebuild for image_index from SurrealDB.
    Call this after new images have been ingested.
    """
    return await rebuild_image_hipVS()


async def rebuild_video_index():
    """
    Force a full CAGRA graph rebuild for video_index from SurrealDB.
    Call this after new videos have been ingested.
    """
    return await rebuild_video_hipVS()
