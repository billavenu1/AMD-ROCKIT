# HF_Space_hipVS/vector_store.py
# ================================
# Multi-project vector store with 3-tier GPU acceleration.
#
# Key design:
#   - Each project gets its own VectorStore instances (image_index, video_index)
#   - CAGRA is rebuilt on every insert (optimized for query, not ingestion)
#   - Indexes swap between NVMe and VRAM via async pinned-memory DMA
#   - Multiple projects coexist by LRU-evicting cold indexes from VRAM
#
# Tiers:
#   1. CAGRA graph (hipVS / cuVS) — ANN search in ~50us
#   2. PyTorch flat tensor (hipBLAS matmul) — brute-force GPU
#   3. NumPy CPU cosine similarity — works everywhere

import json
import logging
import threading
import numpy as np
from pathlib import Path

from config import USE_GPU, HF_TOKEN, HF_DATASET_REPO, SWAP_PATH, get_project_dir

logger = logging.getLogger(__name__)

# ── GPU Backend Detection ────────────────────────────────────────────────────

_HIPVS_AVAILABLE = False
_TORCH_CUDA_AVAILABLE = False
_cagra = None

if USE_GPU:
    try:
        from cuvs.neighbors import cagra as _cagra_mod
        _cagra = _cagra_mod
        _HIPVS_AVAILABLE = True
        logger.info("Tier 1: hipVS (cuvs) -- CAGRA index enabled")
    except ImportError:
        pass

    if not _HIPVS_AVAILABLE:
        try:
            import torch
            if torch.cuda.is_available():
                _TORCH_CUDA_AVAILABLE = True
                props = torch.cuda.get_device_properties(0)
                name = props.name.lower()
                backend = "ROCm" if ("amd" in name or "radeon" in name) else "CUDA"
                logger.info(f"Tier 2: PyTorch {backend} -- flat GPU search ({props.name})")
        except ImportError:
            pass

if not _HIPVS_AVAILABLE and not _TORCH_CUDA_AVAILABLE:
    logger.info("Tier 3: NumPy CPU vector search")


# ── HF Dataset Persistence ──────────────────────────────────────────────────

def _hf_save(name: str, ids: list[str], vectors: np.ndarray, metadata: list[dict]):
    if not HF_DATASET_REPO or not HF_TOKEN:
        return
    try:
        from datasets import Dataset
        records = [
            {"id": ids[i], "vector": vectors[i].tolist(), "metadata": json.dumps(metadata[i])}
            for i in range(len(ids))
        ]
        ds = Dataset.from_list(records)
        repo = f"{HF_DATASET_REPO}-{name}"
        ds.push_to_hub(repo, token=HF_TOKEN, private=True)
        logger.info(f"[{name}] Pushed {len(records)} vectors to HF Dataset")
    except Exception as e:
        logger.warning(f"[{name}] HF push failed: {e}")


def _hf_load(name: str):
    if not HF_DATASET_REPO or not HF_TOKEN:
        return None
    try:
        from datasets import load_dataset
        repo = f"{HF_DATASET_REPO}-{name}"
        ds = load_dataset(repo, token=HF_TOKEN, split="train")
        logger.info(f"[{name}] Loaded {len(ds)} vectors from HF Dataset")
        return ds
    except Exception:
        return None


# ── VectorStore ──────────────────────────────────────────────────────────────

class VectorStore:
    """
    GPU-backed vector store with NVMe swap and CAGRA rebuild-on-insert.

    Lifecycle:
      1. add(vectors, ids, meta)         — bulk add + CAGRA rebuild + persist
      2. append(vector, id, meta)        — single add, NO rebuild (caller decides)
      3. append_and_rebuild(v, id, meta) — single add + CAGRA rebuild + persist
      4. search(query, top_k)            — search (auto-loads from NVMe if needed)
      5. evict()                         — free VRAM, keep NVMe
      6. restore()                       — NVMe -> VRAM (async, pinned DMA)
    """

    def __init__(self, name: str, index_dir: Path | None = None):
        self.name = name
        self._index_dir = index_dir or SWAP_PATH
        self._index_dir.mkdir(parents=True, exist_ok=True)

        self._vectors: np.ndarray | None = None
        self._ids: list[str] = []
        self._metadata: list[dict] = []

        # GPU state
        self._gpu_index = None    # CAGRA index object
        self._gpu_vecs = None     # torch tensor (flat fallback)
        self._in_vram = False

        # File paths
        self._npz_file = self._index_dir / f"{name}.npz"
        self._meta_file = self._index_dir / f"{name}_meta.json"
        self._cagra_file = self._index_dir / f"{name}.cagra"

        # Load from disk on init
        if self._npz_file.exists():
            self._load_from_disk()
        else:
            self._load_from_hf()

    # ── Add / Append ─────────────────────────────────────────────────────────

    def add(self, vectors: np.ndarray, ids: list[str], metadata: list[dict] | None = None):
        """Bulk add vectors + rebuild CAGRA + persist."""
        if len(vectors) == 0:
            return
        self._vectors = vectors.astype(np.float32)
        self._ids = list(ids)
        self._metadata = metadata or [{} for _ in ids]
        self._normalize()
        self.rebuild_gpu_index()
        self._persist()
        logger.info(f"[{self.name}] Indexed {len(ids)} vectors (mode={self.mode})")

    def append(self, vector: np.ndarray, vid: str, meta: dict | None = None):
        """Append one vector. NO CAGRA rebuild (batch callers rebuild at end)."""
        vector = vector.astype(np.float32).reshape(1, -1)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        if self._vectors is not None and len(self._vectors) > 0:
            self._vectors = np.vstack([self._vectors, vector])
        else:
            self._vectors = vector

        self._ids.append(vid)
        self._metadata.append(meta or {})
        self._in_vram = False  # invalidate GPU index

    def append_and_rebuild(self, vector: np.ndarray, vid: str, meta: dict | None = None):
        """Append one vector + rebuild CAGRA + persist."""
        self.append(vector, vid, meta)
        self.rebuild_gpu_index()
        self._persist()

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: np.ndarray, top_k: int = 10) -> list[dict]:
        """
        Cosine similarity search. Auto-restores from NVMe if not in VRAM.
        Returns list of dicts: {id, score, ...metadata}
        """
        if self._vectors is None or len(self._vectors) == 0:
            return []

        query = query.astype(np.float32)
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        # Auto-load GPU index if needed
        if ((_HIPVS_AVAILABLE or _TORCH_CUDA_AVAILABLE) and not self._in_vram):
            self.rebuild_gpu_index()

        if _HIPVS_AVAILABLE and self._gpu_index is not None:
            return self._search_cagra(query, top_k)
        elif _TORCH_CUDA_AVAILABLE and self._in_vram:
            return self._search_torch(query, top_k)
        return self._search_numpy(query, top_k)

    def _search_numpy(self, query: np.ndarray, top_k: int) -> list[dict]:
        scores = self._vectors @ query
        k = min(top_k, len(self._ids))
        if len(scores) > top_k:
            idx = np.argpartition(scores, -k)[-k:]
            idx = idx[np.argsort(scores[idx])[::-1]]
        else:
            idx = np.argsort(scores)[::-1][:k]
        return [{"id": self._ids[i], "score": float(scores[i]), **self._metadata[i]} for i in idx]

    def _search_cagra(self, query: np.ndarray, top_k: int) -> list[dict]:
        import cupy as cp
        q = cp.asarray(query.reshape(1, -1))
        search_params = _cagra.SearchParams()
        distances, indices = _cagra.search(search_params, self._gpu_index, q, top_k)
        results = []
        for idx, dist in zip(indices[0].get().tolist(), distances[0].get().tolist()):
            if 0 <= idx < len(self._ids):
                results.append({"id": self._ids[idx], "score": -float(dist), **self._metadata[idx]})
        return results

    def _search_torch(self, query: np.ndarray, top_k: int) -> list[dict]:
        import torch
        q = torch.from_numpy(query).to(self._gpu_vecs.device, dtype=self._gpu_vecs.dtype).unsqueeze(0)
        scores = (q @ self._gpu_vecs.T).squeeze(0)
        k = min(top_k, len(self._ids))
        top_scores, top_idx = torch.topk(scores, k=k)
        return [
            {"id": self._ids[i], "score": float(s), **self._metadata[i]}
            for i, s in zip(top_idx.cpu().tolist(), top_scores.cpu().tolist())
        ]

    # ── GPU Index Build (CAGRA rebuilt on every insert) ──────────────────────

    def rebuild_gpu_index(self):
        """Build/rebuild the GPU index from current vectors."""
        if self._vectors is None or len(self._vectors) == 0:
            return
        if _HIPVS_AVAILABLE:
            self._build_cagra()
        elif _TORCH_CUDA_AVAILABLE:
            self._build_torch()

    def _build_cagra(self):
        import cupy as cp
        d_vecs = cp.asarray(self._vectors)
        params = _cagra.IndexParams()
        params.metric = "sqeuclidean"
        params.graph_degree = 64
        params.intermediate_graph_degree = 128
        params.build_algo = "IVF_PQ"
        logger.info(f"[{self.name}] Building CAGRA ({self._vectors.shape}) ...")
        self._gpu_index = _cagra.build(params, d_vecs)
        # Serialize to NVMe for fast restore after eviction
        _cagra.serialize(str(self._cagra_file), self._gpu_index)
        self._in_vram = True
        logger.info(f"[{self.name}] CAGRA built + serialized")

    def _build_torch(self):
        import torch
        self._gpu_vecs = torch.from_numpy(self._vectors).cuda().half()
        self._in_vram = True

    # ── NVMe <-> VRAM Swap ───────────────────────────────────────────────────

    def evict(self):
        """Free VRAM. NVMe files stay intact for fast restore()."""
        if not self._in_vram:
            return
        self._gpu_index = None
        self._gpu_vecs = None
        if _HIPVS_AVAILABLE or _TORCH_CUDA_AVAILABLE:
            import torch
            torch.cuda.empty_cache()
        self._in_vram = False
        logger.info(f"[{self.name}] Evicted from VRAM")

    def restore(self):
        """
        Restore index from NVMe to VRAM via async pinned-memory copy.
        Does NOT re-embed or re-read source files.
        """
        if self._in_vram:
            return

        if _HIPVS_AVAILABLE and self._cagra_file.exists():
            logger.info(f"[{self.name}] Restoring CAGRA from NVMe (async) ...")
            self._gpu_index = _cagra.deserialize(str(self._cagra_file))
            self._in_vram = True
            logger.info(f"[{self.name}] CAGRA restored to VRAM")
        elif _TORCH_CUDA_AVAILABLE and self._vectors is not None:
            import torch
            # Pinned memory -> VRAM (async DMA copy)
            pinned = torch.from_numpy(self._vectors).pin_memory()
            self._gpu_vecs = pinned.to("cuda", non_blocking=True, dtype=torch.float16)
            self._in_vram = True
            logger.info(f"[{self.name}] Flat tensor restored to VRAM (async)")

        # Load IDs if needed
        if not self._ids and self._npz_file.exists():
            data = np.load(self._npz_file, allow_pickle=True)
            self._ids = data["ids"].tolist()
            if self._meta_file.exists():
                with open(self._meta_file, "r") as f:
                    self._metadata = json.load(f)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _persist(self):
        self._save_to_disk()
        if HF_DATASET_REPO and HF_TOKEN:
            _hf_save(self.name, self._ids, self._vectors, self._metadata)

    def _save_to_disk(self):
        if self._vectors is None:
            return
        np.savez_compressed(self._npz_file, vectors=self._vectors, ids=np.array(self._ids, dtype=object))
        with open(self._meta_file, "w") as f:
            json.dump(self._metadata, f)

    def _load_from_disk(self):
        try:
            data = np.load(self._npz_file, allow_pickle=True)
            self._vectors = data["vectors"].astype(np.float32)
            self._ids = data["ids"].tolist()
            if self._meta_file.exists():
                with open(self._meta_file, "r") as f:
                    self._metadata = json.load(f)
            else:
                self._metadata = [{} for _ in self._ids]
            logger.info(f"[{self.name}] Loaded {len(self._ids)} vectors from disk")
        except Exception as e:
            logger.error(f"[{self.name}] Disk load failed: {e}")

    def _load_from_hf(self):
        ds = _hf_load(self.name)
        if ds is None or len(ds) == 0:
            return
        try:
            self._ids = ds["id"]
            self._vectors = np.array(ds["vector"], dtype=np.float32)
            self._metadata = [json.loads(m) for m in ds["metadata"]]
            self._save_to_disk()
        except Exception as e:
            logger.error(f"[{self.name}] HF load failed: {e}")

    def _normalize(self):
        if self._vectors is None:
            return
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        self._vectors = self._vectors / norms

    # ── Utilities ────────────────────────────────────────────────────────────

    def clear(self):
        self._vectors = None
        self._ids = []
        self._metadata = []
        self._gpu_index = None
        self._gpu_vecs = None
        self._in_vram = False
        for f in (self._npz_file, self._meta_file, self._cagra_file):
            if f.exists():
                f.unlink()

    def has_data(self) -> bool:
        return self._vectors is not None and len(self._ids) > 0

    @property
    def count(self) -> int:
        return len(self._ids) if self._ids else 0

    @property
    def in_vram(self) -> bool:
        return self._in_vram

    @property
    def mode(self) -> str:
        if _HIPVS_AVAILABLE:
            return "CAGRA (hipVS GPU)"
        elif _TORCH_CUDA_AVAILABLE:
            return "Flat Tensor (GPU)"
        return "NumPy (CPU)"

    def __len__(self):
        return self.count

    def __repr__(self):
        vram = "VRAM" if self._in_vram else "NVMe"
        return f"VectorStore('{self.name}', n={self.count}, {self.mode}, {vram})"


# ── Multi-Project Store Registry ────────────────────────────────────────────

_stores: dict[str, VectorStore] = {}
_lock = threading.Lock()


def get_store(project: str, index_name: str) -> VectorStore:
    """
    Get or create a VectorStore for a specific project + index.
    Stores are cached globally and share the same GPU memory pool.
    """
    key = f"{project}/{index_name}"
    with _lock:
        if key not in _stores:
            proj_dir = get_project_dir(project)
            idx_dir = proj_dir / "indexes"
            _stores[key] = VectorStore(index_name, index_dir=idx_dir)
            logger.info(f"Store created: {_stores[key]}")
        return _stores[key]


def list_projects() -> list[str]:
    """List all projects that have at least one index file."""
    from config import PROJECTS_DIR
    projects = []
    if PROJECTS_DIR.exists():
        for p in sorted(PROJECTS_DIR.iterdir()):
            if p.is_dir():
                projects.append(p.name)
    return projects


def evict_all():
    """Evict all stores from VRAM."""
    with _lock:
        for store in _stores.values():
            if store.in_vram:
                store.evict()
