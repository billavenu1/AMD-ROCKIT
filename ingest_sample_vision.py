#!/usr/bin/env python3
"""
ingest_sample_vision.py
========================
Master ingestion script for ARIA Vision.

Strategy:
  - IMAGES: embed each image file directly as multimodal bytes (gemini-embedding-2)
  - VIDEOS:  extract 1 representative frame every FRAME_EVERY_SEC seconds via ffmpeg,
             embed each frame as an image, store the exact timestamp.
             → Every second window gets a DIFFERENT vector → meaningful semantic search.

This replaces the "embed whole video as one chunk" approach which gave identical
vectors (and ~0.35 generic scores) for every query.

Schema:
  image_index  — file_path, file_name, file_size, resolution, embedding
  video_index  — video_path, video_name, timestamp_sec, timestamp_label,
                 frame_path (temp), duration_total, embedding

Prerequisites:
  - ffmpeg + ffprobe on PATH
  - SurrealDB running on ws://localhost:8000/rpc
  - GEMINI_API_KEY in .env
  - Place images in data/vision_samples/images/
  - Place videos in data/vision_samples/videos/

Usage:
  uv run ingest_sample_vision.py              # full run
  uv run ingest_sample_vision.py --video-only # re-index video only
  uv run ingest_sample_vision.py --image-only # re-index images only
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types
from PIL import Image as PILImage

sys.path.insert(0, str(Path(__file__).parent))
from open_notebook.database.repository import repo_query, repo_create

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
EMBEDDING_MODEL    = "gemini-embedding-2"
EMBEDDING_DIM      = 2048
IMAGE_DIR          = Path(__file__).parent / "data" / "vision_samples" / "images"
VIDEO_DIR          = Path(__file__).parent / "data" / "vision_samples" / "videos"

# How many seconds apart to sample frames.
# 5 → 1 embedding per 5-second window (balanced quality vs API calls)
# 1 → 1 embedding per second (richest, but ~120 calls for a 2-min video)
FRAME_EVERY_SEC    = 5

IMAGE_EXTENSIONS   = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS   = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY / GOOGLE_API_KEY not set in .env")
    sys.exit(1)

client = genai.Client(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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
    """Return duration in seconds via ffprobe, or 0.0 on failure."""
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
        print(f"  [WARN] ffprobe error: {e}")
        return 0.0


def extract_frame(video_path: str, timestamp_sec: float, out_path: str) -> bool:
    """
    Extract a single JPEG frame at `timestamp_sec` from `video_path` into `out_path`.
    Uses -ss (fast seek) before -i for speed, then accurate re-encode to JPEG.
    Returns True on success.
    """
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", f"{timestamp_sec:.3f}",   # fast seek
            "-i", video_path,
            "-frames:v", "1",                 # 1 frame only
            "-q:v", "2",                       # JPEG quality (2=best, 31=worst)
            "-vf", "scale=640:-1",             # resize to 640px wide (saves API bytes)
            out_path,
        ],
        capture_output=True, timeout=30,
    )
    return result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0


def embed_bytes(data: bytes, mime: str) -> list[float]:
    """Embed raw bytes using gemini-embedding-2."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=mime)],
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(result.embeddings[0].values)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — SurrealDB Schema
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
DEFINE TABLE OVERWRITE image_index SCHEMAFULL;
DEFINE FIELD file_path       ON image_index TYPE string;
DEFINE FIELD file_name       ON image_index TYPE string;
DEFINE FIELD file_size       ON image_index TYPE string;
DEFINE FIELD resolution      ON image_index TYPE string;
DEFINE FIELD mime_type       ON image_index TYPE string;
DEFINE FIELD embedding       ON image_index TYPE array<float>;
DEFINE FIELD created         ON image_index TYPE datetime DEFAULT time::now();
DEFINE FIELD updated         ON image_index TYPE datetime DEFAULT time::now();
DEFINE INDEX image_embedding_idx ON image_index
    FIELDS embedding MTREE DIMENSION 2048 DIST COSINE;

DEFINE TABLE OVERWRITE video_index SCHEMAFULL;
DEFINE FIELD video_path      ON video_index TYPE string;
DEFINE FIELD video_name      ON video_index TYPE string;
DEFINE FIELD timestamp_sec   ON video_index TYPE float;
DEFINE FIELD timestamp_label ON video_index TYPE string;
DEFINE FIELD duration_total  ON video_index TYPE float;
DEFINE FIELD embedding       ON video_index TYPE array<float>;
DEFINE FIELD created         ON video_index TYPE datetime DEFAULT time::now();
DEFINE FIELD updated         ON video_index TYPE datetime DEFAULT time::now();
DEFINE INDEX video_embedding_idx ON video_index
    FIELDS embedding MTREE DIMENSION 2048 DIST COSINE;
DEFINE INDEX video_time_idx ON video_index
    FIELDS video_path, timestamp_sec;
"""


async def setup_schema():
    print("\n[SCHEMA] Defining tables and indexes...")

    # Purge old video_index fields that no longer exist in the new per-frame schema.
    # SurrealDB SCHEMAFULL keeps old field definitions even after DEFINE TABLE OVERWRITE
    # unless we explicitly REMOVE them first.
    cleanup = [
        "REMOVE FIELD IF EXISTS timestamp_end ON video_index",
        "REMOVE FIELD IF EXISTS timestamp_start ON video_index",
        "REMOVE INDEX IF EXISTS video_embedding_idx ON video_index",
        "REMOVE INDEX IF EXISTS video_time_idx ON video_index",
    ]
    for stmt in cleanup:
        try:
            await repo_query(stmt + ";")
        except Exception:
            pass  # field/index may not exist yet — that's fine

    for stmt in SCHEMA_SQL.strip().split(";"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            await repo_query(stmt + ";")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"  [WARN] {e}")
    print("  Schema OK")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Image Ingestion (unchanged, it was working)
# ─────────────────────────────────────────────────────────────────────────────

def get_image_meta(path: Path) -> dict:
    stat   = path.stat()
    size   = f"{round(stat.st_size / 1024, 1)}KB"
    try:
        with PILImage.open(path) as img:
            res = f"{img.width}x{img.height}"
    except Exception:
        res = "unknown"
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp"}.get(
        path.suffix.lower(), "image/jpeg"
    )
    return {"file_path": str(path.resolve()), "file_name": path.name,
            "file_size": size, "resolution": res, "mime_type": mime}


async def ingest_images():
    print("\n[IMAGES] Ingesting...")
    files = sorted(f for f in IMAGE_DIR.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS)[:30]

    if not files:
        print(f"  ⚠ No images in {IMAGE_DIR} — skipping.")
        return 0

    await repo_query("DELETE image_index;")
    print(f"  {len(files)} files found — cleared old index")

    count = 0
    for i, p in enumerate(files):
        meta = get_image_meta(p)
        print(f"  [{i+1}/{len(files)}] {p.name} ...", end=" ", flush=True)
        try:
            with open(p, "rb") as f:
                data = f.read()
            meta["embedding"] = embed_bytes(data, meta["mime_type"])
            await repo_create("image_index", meta)
            print(f"✓  ({meta['resolution']}, {meta['file_size']})")
            count += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"✗  {e}")

    print(f"  ✓ {count} images indexed")
    return count


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Video Ingestion (REWRITTEN — frame-by-frame)
# ─────────────────────────────────────────────────────────────────────────────

async def ingest_videos():
    print("\n[VIDEOS] Ingesting (frame-per-second window approach)...")

    if not HAS_FFMPEG:
        print("  ✗ ffmpeg not found — cannot do frame extraction.")
        print("    Run start-all.ps1 first to auto-install ffmpeg.")
        return 0

    files = sorted(f for f in VIDEO_DIR.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS)
    if not files:
        print(f"  ⚠ No videos in {VIDEO_DIR} — skipping.")
        return 0

    # Clear the old (whole-file) index
    await repo_query("DELETE video_index;")
    print(f"  {len(files)} video(s) found — cleared old index")
    print(f"  Sampling 1 frame every {FRAME_EVERY_SEC} seconds (resize → 640px wide)")
    print()

    total = 0

    for video_path in files:
        video_str  = str(video_path.resolve())
        duration   = get_duration(video_str)

        if duration <= 0:
            print(f"  ⚠ Skipping {video_path.name} (duration unreadable)")
            continue

        # Build the list of timestamps to sample
        # Always include 0.5s (not 0.0 which is often a black frame),
        # then every FRAME_EVERY_SEC until the end.
        timestamps = [0.5]
        t = float(FRAME_EVERY_SEC)
        while t < duration:
            timestamps.append(round(t, 2))
            t += FRAME_EVERY_SEC
        # Ensure we get the last second if not already covered
        if (duration - 1.0) not in timestamps:
            timestamps.append(round(max(0, duration - 1.0), 2))
        timestamps = sorted(set(timestamps))

        print(f"  ▶ {video_path.name}  ({duration:.1f}s → {len(timestamps)} frames to embed)")
        bar_width = 40

        with tempfile.TemporaryDirectory() as tmp_dir:
            for idx, ts in enumerate(timestamps):
                frame_path = os.path.join(tmp_dir, f"frame_{idx:05d}.jpg")

                ok = extract_frame(video_str, ts, frame_path)
                if not ok:
                    print(f"    [{idx+1}/{len(timestamps)}] {fmt_time(ts)} — frame extract FAILED, skipping")
                    continue

                try:
                    with open(frame_path, "rb") as f:
                        frame_data = f.read()

                    embedding = embed_bytes(frame_data, "image/jpeg")

                    await repo_create("video_index", {
                        "video_path":      video_str,
                        "video_name":      video_path.name,
                        "timestamp_sec":   ts,
                        "timestamp_label": fmt_time(ts),
                        "duration_total":  round(duration, 2),
                        "embedding":       embedding,
                    })

                    total += 1

                    # Progress bar
                    done = int(bar_width * (idx + 1) / len(timestamps))
                    bar  = "█" * done + "░" * (bar_width - done)
                    pct  = 100 * (idx + 1) // len(timestamps)
                    print(f"\r    [{bar}] {pct:3d}%  ts={fmt_time(ts)}  frames={total}", end="", flush=True)

                    # Polite rate-limit (image embeddings: 1500 RPM limit)
                    time.sleep(0.2)

                except Exception as e:
                    print(f"\n    ✗ ts={fmt_time(ts)}: {e}")

        print(f"\n    ✓ Done — {len(timestamps)} frames embedded for {video_path.name}")
        print()

    print(f"  ✓ Total video frames indexed: {total}")
    return total


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Summary
# ─────────────────────────────────────────────────────────────────────────────

def extract_count(result) -> int:
    try:
        if not result:
            return 0
        first = result[0]
        if isinstance(first, dict):
            return first.get("count", 0)
        if isinstance(first, list) and first:
            return first[0].get("count", 0)
        return 0
    except Exception:
        return 0


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    print("=" * 60)
    print("  ARIA Vision — Sample Data Ingestion")
    print("=" * 60)
    print(f"  Embedding model : {EMBEDDING_MODEL} ({EMBEDDING_DIM}d)")
    print(f"  Frame interval  : every {FRAME_EVERY_SEC}s  (change FRAME_EVERY_SEC in script)")
    print(f"  Image source    : {IMAGE_DIR}")
    print(f"  Video source    : {VIDEO_DIR}")
    print(f"  ffmpeg present  : {'Yes (OK)' if HAS_FFMPEG else 'NO - videos will be skipped'}")
    print()

    await setup_schema()

    if mode in ("all", "--image-only"):
        img_count = await ingest_images()
    else:
        img_count = None

    if mode in ("all", "--video-only"):
        vid_count = await ingest_videos()
    else:
        vid_count = None

    # Verification
    print("\n[VERIFY] Counting rows...")
    img_rows  = await repo_query("SELECT count() FROM image_index GROUP ALL;")
    vid_rows  = await repo_query("SELECT count() FROM video_index GROUP ALL;")
    img_total = extract_count(img_rows)
    vid_total = extract_count(vid_rows)

    print(f"  image_index : {img_total} rows")
    print(f"  video_index : {vid_total} rows  (each row = 1 unique timestamp)")

    print()
    print("=" * 60)
    print("  ✓ Ingestion complete!")
    print("=" * 60)
    print()
    print("Run queries:")
    print('  uv run query_vision_image.py "red sports car at night"')
    print('  uv run query_vision_video.py "rhino running in the wild"')


if __name__ == "__main__":
    asyncio.run(main())
