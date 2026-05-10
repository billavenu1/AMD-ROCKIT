# HF_Space_hipVS/seed_data.py
# =============================
# Auto-seed from a HF Dataset so the Space launches with content indexed.
# Called on first launch if AUTO_SEED=true and the default project is empty.

import logging
from config import SEED_DATASET, SEED_SPLIT, HF_TOKEN, DEFAULT_PROJECT

logger = logging.getLogger(__name__)


def run(project: str = DEFAULT_PROJECT, progress_callback=None) -> tuple[int, str]:
    """Seed a project with images from a HF dataset."""
    from datasets import load_dataset
    from ingest import ingest_image_from_pil
    from vector_store import get_store

    log = [f"Seeding project '{project}' from {SEED_DATASET} [{SEED_SPLIT}]\n"]

    try:
        ds = load_dataset(SEED_DATASET, split=SEED_SPLIT, token=HF_TOKEN or None)
        log.append(f"Loaded {len(ds)} items")
    except Exception as e:
        msg = f"Failed to load dataset: {e}"
        logger.error(msg)
        return 0, msg

    count = 0
    total = len(ds)

    for i, item in enumerate(ds):
        image = item.get("image")
        if image is None:
            continue

        filename = item.get("filename", f"seed_{i:05d}.jpg")
        extra = {"source": SEED_DATASET}

        # Grab any available caption as metadata (not used for embedding)
        for key in ("caption", "sentences", "text"):
            if key in item:
                val = item[key]
                extra["caption_hint"] = val[0] if isinstance(val, list) else str(val)
                break

        ok, _ = ingest_image_from_pil(image, filename, extra, project=project)
        if ok:
            count += 1
            if count <= 3 or count % 50 == 0:
                log.append(f"  [{count}/{total}] {filename}")

        if progress_callback:
            progress_callback((i + 1) / total, desc=f"Seeding {i+1}/{total}...")

    # Rebuild CAGRA once after all images
    store = get_store(project, "image_index")
    if store.has_data():
        store.rebuild_gpu_index()
        store._persist()

    log.append(f"\nSeeding complete: {count} images indexed")
    log.append(f"Store: {store}")
    return count, "\n".join(log)


def is_needed() -> bool:
    from config import AUTO_SEED
    from vector_store import get_store
    store = get_store(DEFAULT_PROJECT, "image_index")
    return AUTO_SEED and not store.has_data()
