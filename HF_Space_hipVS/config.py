# HF_Space_hipVS/config.py
# ========================
# Environment-aware configuration.
# Auto-scales model selection by hardware tier.

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Core Flags ──────────────────────────────────────────────────────────────

USE_GPU = os.environ.get("USE_GPU", "false").lower() in ("true", "1", "yes")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_DATASET_REPO = os.environ.get("HF_DATASET_REPO", "")

# ── Device ──────────────────────────────────────────────────────────────────

DEVICE = "cuda" if USE_GPU else "cpu"
TORCH_DTYPE = "float16" if USE_GPU else "float32"

# ── Embedding Model (multimodal — images + text, NO captioning) ─────────────
#
# GPU:  Qwen3-VL-Embedding-2B  (2048d) or Qwen3-VL-Embedding-8B (4096d)
# CPU:  CLIP ViT-L/14 (768d) — lightweight, runs on free HF Spaces
#
if USE_GPU:
    EMBED_MODEL = os.environ.get("EMBED_MODEL", "Qwen/Qwen3-VL-Embedding-2B")
    EMBED_DIM = int(os.environ.get("EMBED_DIM", "2048"))
else:
    EMBED_MODEL = os.environ.get("EMBED_MODEL", "openai/clip-vit-large-patch14")
    EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))

# ── LLM (search result interpretation) ─────────────────────────────────────
#
# Primary:  Qwen3-35B-A3B  (MoE: 35B total, 3B active — fast + smart)
# Fallback: Qwen3-1.7B     (dense, runs on anything)
#
LLM_MODEL = os.environ.get("LLM_MODEL", "Qwen/Qwen3-35B-A3B")
LLM_FALLBACK = os.environ.get("LLM_FALLBACK", "Qwen/Qwen3-1.7B")

# ── Video Frame Extraction ─────────────────────────────────────────────────

FRAME_EVERY_SEC = int(os.environ.get("FRAME_EVERY_SEC", "5"))

# ── Data Directories ────────────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent / "data")))
PROJECTS_DIR = DATA_DIR / "projects"
DEFAULT_PROJECT = os.environ.get("DEFAULT_PROJECT", "default")
SWAP_PATH = Path(os.environ.get("SWAP_PATH", str(DATA_DIR / "indexes")))

# Ensure base directories
for d in (PROJECTS_DIR, SWAP_PATH):
    d.mkdir(parents=True, exist_ok=True)

# ── Per-project directories ─────────────────────────────────────────────────

def get_project_dir(project: str = DEFAULT_PROJECT) -> Path:
    """Return the root directory for a project, creating it if needed."""
    p = PROJECTS_DIR / project
    for sub in ("images", "videos", "indexes"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p

# Ensure default project exists
get_project_dir(DEFAULT_PROJECT)

# ── Seeding ─────────────────────────────────────────────────────────────────

SEED_DATASET = os.environ.get("SEED_DATASET", "nlphuji/flickr30k")
SEED_SPLIT = os.environ.get("SEED_SPLIT", "test[:200]")
AUTO_SEED = os.environ.get("AUTO_SEED", "true").lower() in ("true", "1", "yes")

# ── File Extensions ─────────────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# ── Startup Log ─────────────────────────────────────────────────────────────

logger.info("=" * 55)
logger.info("  ARIA Vision Intelligence")
logger.info("=" * 55)
logger.info(f"  USE_GPU       : {USE_GPU}")
logger.info(f"  DEVICE        : {DEVICE}")
logger.info(f"  EMBED_MODEL   : {EMBED_MODEL}")
logger.info(f"  EMBED_DIM     : {EMBED_DIM}")
logger.info(f"  LLM_MODEL     : {LLM_MODEL}")
logger.info(f"  LLM_FALLBACK  : {LLM_FALLBACK}")
logger.info(f"  SWAP_PATH     : {SWAP_PATH}")
logger.info(f"  HF_TOKEN      : {'set' if HF_TOKEN else 'NOT SET'}")
logger.info(f"  HF_DATASET    : {HF_DATASET_REPO or 'local only'}")
logger.info(f"  AUTO_SEED     : {AUTO_SEED}")
logger.info("=" * 55)
