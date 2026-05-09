# vision/hip_vs/memory_manager.py
#
# HIPVectorStore — two-tier GPU vector store
# ─────────────────────────────────────────
# Tier 1 (preferred): CAGRA graph index via hipVS
#   hipVS (AMD ROCm-DS) ships its Python package under the `cuvs` namespace
#   because it is a direct port of NVIDIA cuVS and maintains full API compat.
#   So `from cuvs.neighbors import cagra` IS the correct hipVS import.
#
#   • build()     → pulled from SurrealDB, CAGRA graph constructed on GPU
#   • evict()     → graph serialized to NVMe (.cagra file), VRAM freed
#   • restore()   → graph deserialized from NVMe back to VRAM (FAST, no rebuild)
#
# Tier 2 (fallback): Flat float16 tensor (brute-force hipBLAS matmul)
#   Used automatically when hipVS / cuvs is not installed.
#   Same public API — transparent to all callers.

import logging
import numpy as np
import torch
import torch.nn.functional as F
from pathlib import Path
from vision.config import SWAP_PATH

logger = logging.getLogger(__name__)

_swap = Path(SWAP_PATH)
_swap.mkdir(parents=True, exist_ok=True)

# ── Detect hipVS (imported under the `cuvs` namespace per AMD's design) ───────
#
# hipVS is AMD's port of NVIDIA cuVS. AMD deliberately keeps the Python
# package namespace as `cuvs` for drop-in API compatibility.
# Install: pip install hipvs  →  import cuvs  ✓
#
try:
    from cuvs.neighbors import cagra as _cagra          # hipVS on ROCm
    _HIPVS_AVAILABLE = True
    logger.info("hipVS detected (cuvs namespace) — CAGRA index will be used")
except ImportError:
    _HIPVS_AVAILABLE = False
    logger.warning(
        "hipVS (cuvs) not found — falling back to flat float16 tensor search. "
        "Install AMD ROCm-DS hipVS (`pip install hipvs`) to enable CAGRA."
    )


class HIPVectorStore:
    """
    GPU-backed vector store backed by hipVS CAGRA (or flat-tensor fallback).

    Lifecycle
    ---------
    1. build(vectors, ids)    — first-ever load: constructs index from raw
                                numpy arrays and immediately saves to NVMe.
    2. evict()                — frees VRAM; the serialized file stays on NVMe.
    3. restore()              — reloads from NVMe; NO rebuild, NO SurrealDB.
    4. search(query, top_k)   — runs similarity search on the active index.

    Rules
    -----
    • Only build() ever reads from SurrealDB (via the ingestion layer).
    • restore() only reads from the NVMe swap file → millisecond latency.
    • Re-run build() only when new data is added to SurrealDB.
    """

    def __init__(self, name: str):
        self.name = name
        # Swap file paths — separate extensions so modes never collide
        self._cagra_file = _swap / f"{name}.cagra"   # CAGRA serialized graph
        self._flat_file  = _swap / f"{name}.npy"     # flat float16 matrix
        self._ids_file   = _swap / f"{name}_ids.npy" # ID array (shared)

        # Runtime state
        self._index    = None   # cuvs/hipVS CAGRA index object
        self._gpu_vecs = None   # torch.Tensor (N, D) float16  (fallback)
        self.ids       = None   # np.ndarray of str
        self._in_vram  = False
        self._mode     = "cagra" if _HIPVS_AVAILABLE else "flat"

    # ── Build ─────────────────────────────────────────────────────────────────
    # Call this ONLY when:
    #   (a) the index has never been built, OR
    #   (b) new data was added to SurrealDB and you want to refresh the index.
    # Do NOT call this just to reload after an evict — use restore() instead.

    def build(self, vectors: np.ndarray, ids: list[str]):
        """
        Construct the GPU index from raw embeddings and persist to NVMe.

        Parameters
        ----------
        vectors : np.ndarray, shape (N, D), dtype float32
        ids     : list[str], length N — SurrealDB record IDs
        """
        if len(vectors) == 0:
            raise ValueError(f"[{self.name}] Cannot build index from empty vector list")

        self.ids = np.array(ids, dtype=object)

        if self._mode == "cagra":
            self._build_cagra(vectors)
        else:
            self._build_flat(vectors)

        # IDs file is common to both modes
        np.save(self._ids_file, self.ids)
        self._in_vram = True
        logger.info(
            "[%s] Index built — %d vectors, mode=%s", self.name, len(ids), self._mode
        )

    def _build_cagra(self, vectors: np.ndarray):
        """Build CAGRA graph index using hipVS (cuvs namespace)."""
        import cupy as cp

        # Move vectors to GPU via CuPy (hipVS requires CuPy device arrays)
        d_vecs = cp.asarray(vectors.astype(np.float32))

        # IndexParams — these are the correct hipVS/cuVS CAGRA parameter names
        params = _cagra.IndexParams()
        params.metric = "sqeuclidean"       # L2; search returns L2 distances
        params.graph_degree = 64            # graph connectivity: higher = better recall
        params.intermediate_graph_degree = 128  # only used during build
        params.build_algo = "IVF_PQ"       # faster build; alt: "NN_DESCENT"

        logger.info(
            "[%s] Building CAGRA graph (N=%d, D=%d) …",
            self.name, vectors.shape[0], vectors.shape[1],
        )
        self._index = _cagra.build(params, d_vecs)

        # Serialize immediately so evict() just drops the Python object
        _cagra.serialize(str(self._cagra_file), self._index)
        mb = self._cagra_file.stat().st_size / 1e6
        logger.info(
            "[%s] CAGRA graph serialized to NVMe (%.1f MB)", self.name, mb
        )

    def _build_flat(self, vectors: np.ndarray):
        """Build flat float16 tensor index (fallback when hipVS not available)."""
        t = torch.from_numpy(vectors.astype(np.float32)).cuda()
        # Normalize once → dot product == cosine similarity at search time
        self._gpu_vecs = F.normalize(t, dim=1).half()
        np.save(self._flat_file, self._gpu_vecs.cpu().numpy())
        mb = self._flat_file.stat().st_size / 1e6
        logger.info("[%s] Flat index saved to NVMe (%.1f MB)", self.name, mb)

    # ── Evict ─────────────────────────────────────────────────────────────────

    def evict(self):
        """Free VRAM. The NVMe file stays intact for a fast restore()."""
        if not self._in_vram:
            return

        if self._mode == "cagra":
            # Graph already serialized in build() / restore() — just drop obj
            self._index = None
        else:
            # Re-save flat tensor in case it was mutated, then drop
            if self._gpu_vecs is not None:
                np.save(self._flat_file, self._gpu_vecs.cpu().numpy())
            self._gpu_vecs = None

        torch.cuda.empty_cache()   # hipFree on ROCm
        self._in_vram = False
        logger.info("[%s] Evicted from VRAM", self.name)

    # ── Restore ───────────────────────────────────────────────────────────────

    def restore(self):
        """
        Reload the index from the NVMe swap file into VRAM.

        This is the FAST path used after every evict().
        It never touches SurrealDB — the file was written by build().
        """
        if self._in_vram:
            return

        if self._mode == "cagra":
            if not self._cagra_file.exists():
                raise FileNotFoundError(
                    f"[{self.name}] No CAGRA file at '{self._cagra_file}'. "
                    "Call build() first (queries SurrealDB and constructs the graph)."
                )
            logger.info("[%s] Deserializing CAGRA index from NVMe …", self.name)
            self._index = _cagra.deserialize(str(self._cagra_file))
        else:
            if not self._flat_file.exists():
                raise FileNotFoundError(
                    f"[{self.name}] No flat index file at '{self._flat_file}'. "
                    "Call build() first."
                )
            logger.info("[%s] Loading flat index from NVMe …", self.name)
            cpu = np.load(self._flat_file, mmap_mode='r')
            pinned = torch.from_numpy(np.array(cpu)).pin_memory()
            self._gpu_vecs = pinned.to('cuda', non_blocking=True)

        if not self._ids_file.exists():
            raise FileNotFoundError(
                f"[{self.name}] IDs file missing at '{self._ids_file}'. "
                "Re-run build() to regenerate both the index and IDs."
            )
        self.ids = np.load(self._ids_file, allow_pickle=True)
        self._in_vram = True
        logger.info("[%s] Restored to VRAM (mode=%s)", self.name, self._mode)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]:
        """
        Run similarity search against the active index.

        Parameters
        ----------
        query  : np.ndarray, shape (D,), float32
        top_k  : int

        Returns
        -------
        list of (id_str, score) sorted best-first.
        For CAGRA: score = negative L2 distance (higher = closer).
        For flat:  score = cosine similarity (higher = closer).
        """
        if not self._in_vram:
            raise RuntimeError(
                f"[{self.name}] Index not in VRAM. "
                "Call restore() (fast, from NVMe) or build() (full rebuild from SurrealDB)."
            )

        if self._mode == "cagra":
            return self._search_cagra(query, top_k)
        return self._search_flat(query, top_k)

    def _search_cagra(self, query: np.ndarray, top_k: int) -> list[tuple[str, float]]:
        import cupy as cp

        # hipVS CAGRA search expects a 2-D query array: (n_queries, D)
        q = cp.asarray(query.astype(np.float32)).reshape(1, -1)

        search_params = _cagra.SearchParams()
        # distances are squared L2 by default (matches IndexParams.metric)
        distances, indices = _cagra.search(search_params, self._index, q, top_k)

        ids_arr   = indices[0].get().tolist()    # CuPy → NumPy → list
        dist_arr  = distances[0].get().tolist()

        results = []
        for idx, dist in zip(ids_arr, dist_arr):
            if idx < 0 or idx >= len(self.ids):  # CAGRA pads with -1 if k > N
                continue
            # Negate distance so callers treat score as "higher = better"
            results.append((str(self.ids[idx]), -float(dist)))
        return results

    def _search_flat(self, query: np.ndarray, top_k: int) -> list[tuple[str, float]]:
        q = torch.from_numpy(query.astype(np.float32)).cuda().half()
        q = F.normalize(q.unsqueeze(0), dim=1)
        scores = (q @ self._gpu_vecs.T).squeeze(0)      # hipBLAS SGEMM
        k = min(top_k, len(self.ids))
        top_scores, top_idx = torch.topk(scores, k=k)
        return [
            (str(self.ids[i]), float(s))
            for i, s in zip(top_idx.cpu().tolist(), top_scores.cpu().tolist())
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def in_vram(self) -> bool:
        return self._in_vram

    @property
    def has_swap_file(self) -> bool:
        """True if a serialized index file already exists on NVMe."""
        if self._mode == "cagra":
            return self._cagra_file.exists() and self._ids_file.exists()
        return self._flat_file.exists() and self._ids_file.exists()

    def free_vram_mb(self) -> float:
        free, _ = torch.cuda.mem_get_info()
        return free / 1e6
