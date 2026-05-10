# HF_Space_hipVS/ingest.py
# =========================
# Ingestion pipeline — embeds images/frames DIRECTLY with Qwen3-VL or CLIP.
# No captioning step. The vision-language model encodes images and text
# into the same vector space natively.
#
# CAGRA is rebuilt on every insert (optimized for query, not ingestion).

import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image as PILImage

from config import (
    EMBED_DIM,
    FRAME_EVERY_SEC,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    get_project_dir,
    DEFAULT_PROJECT,
)
from embedding import embed_image, embed_image_bytes
from vector_store import get_store

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


HAS_FFMPEG = check_ffmpeg()


def get_duration(video_path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             video_path],
            capture_output=True, text=True, timeout=30,
        )
        return float(r.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe error: {e}")
        return 0.0


def extract_frame(video_path: str, timestamp_sec: float, out_path: str) -> bool:
    result = subprocess.run(
        ["ffmpeg", "-y",
         "-ss", f"{timestamp_sec:.3f}",
         "-i", video_path,
         "-frames:v", "1",
         "-q:v", "2",
         "-vf", "scale=640:-1",
         out_path],
        capture_output=True, timeout=30,
    )
    return result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0


def get_image_meta(path: Path) -> dict:
    stat = path.stat()
    size = f"{round(stat.st_size / 1024, 1)}KB"
    try:
        with PILImage.open(path) as img:
            res = f"{img.width}x{img.height}"
    except Exception:
        res = "unknown"
    return {
        "file_path": str(path.resolve()),
        "file_name": path.name,
        "file_size": size,
        "resolution": res,
    }


# ── Image Ingestion ─────────────────────────────────────────────────────────

def ingest_images(project: str = DEFAULT_PROJECT, progress_callback=None) -> tuple[int, str]:
    """Ingest all images from a project's images/ directory."""
    proj_dir = get_project_dir(project)
    image_dir = proj_dir / "images"
    store = get_store(project, "image_index")

    files = sorted(
        f for f in image_dir.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS
    )[:200]

    if not files:
        return 0, f"No images found in {image_dir}"

    store.clear()
    log = [f"[{project}] Found {len(files)} images\n"]

    import numpy as np
    all_vectors = []
    all_ids = []
    all_meta = []

    for i, p in enumerate(files):
        meta = get_image_meta(p)
        try:
            img = PILImage.open(p)
            vec = embed_image(img)  # direct multimodal embed, no captioning
            all_vectors.append(vec)
            all_ids.append(meta["file_name"])
            all_meta.append(meta)
            log.append(f"  [{i+1}/{len(files)}] {p.name} ({meta['resolution']})")
        except Exception as e:
            log.append(f"  [{i+1}/{len(files)}] {p.name}: FAILED ({e})")

        if progress_callback:
            progress_callback((i + 1) / len(files), desc=f"Embedding {p.name}...")

    if all_vectors:
        vectors = np.stack(all_vectors)
        store.add(vectors, all_ids, all_meta)  # CAGRA rebuilt inside add()

    log.append(f"\n{len(all_vectors)} images indexed ({store.mode})")
    return len(all_vectors), "\n".join(log)


def ingest_single_image(file_path: str, project: str = DEFAULT_PROJECT) -> tuple[bool, str]:
    """Ingest a single uploaded image. CAGRA is rebuilt."""
    path = Path(file_path)
    proj_dir = get_project_dir(project)
    dest = proj_dir / "images" / path.name
    shutil.copy2(str(path), str(dest))

    store = get_store(project, "image_index")
    meta = get_image_meta(dest)

    try:
        img = PILImage.open(dest)
        vec = embed_image(img)
        store.append_and_rebuild(vec, meta["file_name"], meta)
        return True, f"Indexed: {path.name} ({meta['resolution']})"
    except Exception as e:
        return False, f"Failed: {path.name} -- {e}"


def ingest_image_from_pil(
    image: PILImage.Image,
    file_name: str,
    extra_meta: dict | None = None,
    project: str = DEFAULT_PROJECT,
) -> tuple[bool, str]:
    """Ingest a PIL Image directly (used by seed_data). No CAGRA rebuild per-image."""
    store = get_store(project, "image_index")
    try:
        vec = embed_image(image)
        meta = {"file_name": file_name, **(extra_meta or {})}
        store.append(vec, file_name, meta)  # no rebuild — seed_data calls rebuild at end
        return True, file_name
    except Exception as e:
        return False, str(e)


# ── Video Ingestion ─────────────────────────────────────────────────────────

def ingest_videos(project: str = DEFAULT_PROJECT, progress_callback=None) -> tuple[int, str]:
    """Ingest all videos from a project's videos/ directory."""
    if not HAS_FFMPEG:
        return 0, "ffmpeg not found -- install ffmpeg for video ingestion."

    proj_dir = get_project_dir(project)
    video_dir = proj_dir / "videos"
    store = get_store(project, "video_index")

    files = sorted(
        f for f in video_dir.iterdir()
        if f.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not files:
        return 0, f"No videos found in {video_dir}"

    store.clear()
    log = [f"[{project}] Found {len(files)} video(s) -- frame interval: {FRAME_EVERY_SEC}s\n"]
    total = 0

    for video_path in files:
        video_str = str(video_path.resolve())
        duration = get_duration(video_str)
        if duration <= 0:
            log.append(f"  Skipping {video_path.name} (duration unreadable)")
            continue

        timestamps = [0.5]
        t = float(FRAME_EVERY_SEC)
        while t < duration:
            timestamps.append(round(t, 2))
            t += FRAME_EVERY_SEC
        if (duration - 1.0) not in timestamps:
            timestamps.append(round(max(0, duration - 1.0), 2))
        timestamps = sorted(set(timestamps))

        log.append(f"  {video_path.name} ({duration:.1f}s -> {len(timestamps)} frames)")

        with tempfile.TemporaryDirectory() as tmp_dir:
            for idx, ts in enumerate(timestamps):
                frame_path = os.path.join(tmp_dir, f"frame_{idx:05d}.jpg")
                if not extract_frame(video_str, ts, frame_path):
                    continue

                try:
                    with open(frame_path, "rb") as f:
                        frame_data = f.read()
                    vec = embed_image_bytes(frame_data)
                    frame_meta = {
                        "video_path": video_str,
                        "video_name": video_path.name,
                        "timestamp_sec": ts,
                        "timestamp_label": fmt_time(ts),
                        "duration_total": round(duration, 2),
                    }
                    store.append(vec, f"{video_path.name}@{ts}", frame_meta)
                    total += 1
                    time.sleep(0.05)
                except Exception as e:
                    log.append(f"    ts={fmt_time(ts)}: FAILED ({e})")

                if progress_callback:
                    progress_callback(
                        (idx + 1) / len(timestamps),
                        desc=f"{video_path.name} frame {idx+1}/{len(timestamps)}",
                    )

        log.append(f"    Done ({len(timestamps)} frames)")

    # Rebuild CAGRA once for all videos
    if store.has_data():
        store.rebuild_gpu_index()
        store._persist()

    log.append(f"\n{total} video frames indexed ({store.mode})")
    return total, "\n".join(log)


def ingest_single_video(file_path: str, project: str = DEFAULT_PROJECT, progress_callback=None) -> tuple[int, str]:
    """Ingest a single uploaded video. CAGRA rebuilt at end."""
    path = Path(file_path)
    proj_dir = get_project_dir(project)
    dest = proj_dir / "videos" / path.name
    shutil.copy2(str(path), str(dest))

    if not HAS_FFMPEG:
        return 0, "ffmpeg not found"

    store = get_store(project, "video_index")
    video_str = str(dest.resolve())
    duration = get_duration(video_str)
    if duration <= 0:
        return 0, f"Could not read duration for {path.name}"

    timestamps = [0.5]
    t = float(FRAME_EVERY_SEC)
    while t < duration:
        timestamps.append(round(t, 2))
        t += FRAME_EVERY_SEC
    timestamps = sorted(set(timestamps))
    count = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, ts in enumerate(timestamps):
            frame_path = os.path.join(tmp_dir, f"frame_{idx:05d}.jpg")
            if not extract_frame(video_str, ts, frame_path):
                continue
            try:
                with open(frame_path, "rb") as f:
                    frame_data = f.read()
                vec = embed_image_bytes(frame_data)
                frame_meta = {
                    "video_path": video_str,
                    "video_name": path.name,
                    "timestamp_sec": ts,
                    "timestamp_label": fmt_time(ts),
                    "duration_total": round(duration, 2),
                }
                store.append(vec, f"{path.name}@{ts}", frame_meta)
                count += 1
            except Exception as e:
                logger.error(f"Frame embed error: {e}")

            if progress_callback:
                progress_callback((idx + 1) / len(timestamps))

    # Rebuild CAGRA after all frames
    if store.has_data():
        store.rebuild_gpu_index()
        store._persist()

    return count, f"{count} frames indexed for {path.name} ({duration:.1f}s)"
