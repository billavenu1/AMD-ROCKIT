# vision/hip_vs/ingestion.py
#
# Smart 3-tier loader for HIPVectorStore instances
# ─────────────────────────────────────────────────
# Priority order when loading an index:
#
#   1. Already in VRAM         → return immediately (no I/O)
#   2. NVMe swap file exists   → restore() from file (fast, no SurrealDB call)
#   3. No swap file at all     → pull ALL embeddings from SurrealDB and build()
#
# "build()" is the ONLY path that talks to SurrealDB.
# "restore()" is the fast path used after every evict().

import logging
import numpy as np
from open_notebook.database.repository import repo_query
from .memory_manager import HIPVectorStore
from . import registry

logger = logging.getLogger(__name__)


async def load_image_hipVS() -> HIPVectorStore:
    """
    Return the image_index store, loading it into VRAM if needed.

    Tier 1 — already hot in VRAM: instant return.
    Tier 2 — NVMe swap file exists: deserialize into VRAM (fast).
    Tier 3 — no swap file: query SurrealDB → build index → save to NVMe.
    """
    # ── Tier 1: already hot ──────────────────────────────────────────────────
    store = registry.get("image_index")
    if store and store.in_vram:
        return store

    # ── Re-use existing store object if it was evicted ───────────────────────
    if store is None:
        store = HIPVectorStore("image_index")
        registry.register("image_index", store)

    # ── Tier 2: NVMe swap file exists → fast restore ─────────────────────────
    if store.has_swap_file:
        logger.info("[image_index] Swap file found — restoring from NVMe")
        store.restore()
        return store

    # ── Tier 3: cold start — pull from SurrealDB and build ───────────────────
    logger.info("[image_index] No swap file — querying SurrealDB to build index …")

    rows = await repo_query("SELECT id, embedding FROM image_index;")
    data = rows[0] if rows else []

    if not data:
        raise RuntimeError(
            "[image_index] SurrealDB returned no rows. "
            "Run ingest_sample_vision.py first to populate the image_index table."
        )

    vectors = np.array([r["embedding"] for r in data], dtype=np.float32)
    ids     = [str(r["id"]) for r in data]

    store.build(vectors, ids)
    return store


async def load_video_hipVS() -> HIPVectorStore:
    """
    Return the video_index store, loading it into VRAM if needed.

    Same 3-tier priority as load_image_hipVS().
    """
    # ── Tier 1: already hot ──────────────────────────────────────────────────
    store = registry.get("video_index")
    if store and store.in_vram:
        return store

    # ── Re-use existing store object if it was evicted ───────────────────────
    if store is None:
        store = HIPVectorStore("video_index")
        registry.register("video_index", store)

    # ── Tier 2: NVMe swap file exists → fast restore ─────────────────────────
    if store.has_swap_file:
        logger.info("[video_index] Swap file found — restoring from NVMe")
        store.restore()
        return store

    # ── Tier 3: cold start — pull from SurrealDB and build ───────────────────
    logger.info("[video_index] No swap file — querying SurrealDB to build index …")

    rows = await repo_query(
        "SELECT video_path, timestamp_sec, embedding FROM video_index;"
    )
    data = rows[0] if rows else []

    if not data:
        raise RuntimeError(
            "[video_index] SurrealDB returned no rows. "
            "Run ingest_sample_vision.py first to populate the video_index table."
        )

    vectors = np.array([r["embedding"] for r in data], dtype=np.float32)
    ids     = [f"{r['video_path']}@{r['timestamp_sec']}" for r in data]

    store.build(vectors, ids)
    return store


async def rebuild_image_hipVS() -> HIPVectorStore:
    """
    Force a full rebuild of the image index from SurrealDB.
    Use this ONLY when new images have been ingested and you want
    the CAGRA graph to include them.

    This will:
      1. Evict the current index from VRAM (if loaded).
      2. Delete the old NVMe swap file.
      3. Pull all embeddings from SurrealDB.
      4. Build a fresh index and save it to NVMe.
    """
    store = registry.get("image_index")
    if store is None:
        store = HIPVectorStore("image_index")
        registry.register("image_index", store)

    if store.in_vram:
        store.evict()

    # Remove stale swap files so build() writes fresh ones
    for f in (store._cagra_file, store._flat_file, store._ids_file):
        if f.exists():
            f.unlink()
            logger.info("Deleted stale file: %s", f)

    rows = await repo_query("SELECT id, embedding FROM image_index;")
    data = rows[0] if rows else []

    if not data:
        raise RuntimeError("[image_index] SurrealDB returned no rows — nothing to rebuild.")

    vectors = np.array([r["embedding"] for r in data], dtype=np.float32)
    ids     = [str(r["id"]) for r in data]

    store.build(vectors, ids)
    logger.info("[image_index] Rebuild complete (%d vectors)", len(ids))
    return store


async def rebuild_video_hipVS() -> HIPVectorStore:
    """
    Force a full rebuild of the video index from SurrealDB.
    Same semantics as rebuild_image_hipVS().
    """
    store = registry.get("video_index")
    if store is None:
        store = HIPVectorStore("video_index")
        registry.register("video_index", store)

    if store.in_vram:
        store.evict()

    for f in (store._cagra_file, store._flat_file, store._ids_file):
        if f.exists():
            f.unlink()
            logger.info("Deleted stale file: %s", f)

    rows = await repo_query(
        "SELECT video_path, timestamp_sec, embedding FROM video_index;"
    )
    data = rows[0] if rows else []

    if not data:
        raise RuntimeError("[video_index] SurrealDB returned no rows — nothing to rebuild.")

    vectors = np.array([r["embedding"] for r in data], dtype=np.float32)
    ids     = [f"{r['video_path']}@{r['timestamp_sec']}" for r in data]

    store.build(vectors, ids)
    logger.info("[video_index] Rebuild complete (%d vectors)", len(ids))
    return store
