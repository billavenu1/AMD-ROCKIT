#!/usr/bin/env python3
"""
ingest_sample_vision.py
========================
Populates the index with synthetic sample data (NO model download needed).
Uses random embeddings seeded by text hashes so that similar words produce
similar vectors — good enough to demonstrate the full search pipeline.

After ingestion, runs a sample query and prints results in the same
format as the original SurrealDB-based scripts.

Usage:
  python ingest_sample_vision.py
"""

import hashlib
import json
import numpy as np
from config import DEFAULT_PROJECT, EMBED_DIM
from vector_store import get_store

# -- Synthetic embedding (no model needed) ------------------------------------

def fake_embed(text: str, dim: int = EMBED_DIM) -> np.ndarray:
    """
    Deterministic pseudo-embedding from text.
    Same text always produces the same vector; similar texts produce
    somewhat similar vectors (via shared n-gram hashing).
    """
    rng = np.random.RandomState(int(hashlib.md5(text.encode()).hexdigest(), 16) % 2**31)
    vec = rng.randn(dim).astype(np.float32)

    # Mix in word-level hashes so "mountain landscape" is closer to "mountain" than "car"
    words = text.lower().split()
    for w in words:
        word_seed = int(hashlib.md5(w.encode()).hexdigest(), 16) % 2**31
        word_rng = np.random.RandomState(word_seed)
        vec += word_rng.randn(dim).astype(np.float32) * 0.5

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


# -- Sample Data --------------------------------------------------------------

SAMPLE_IMAGES = [
    {"file_name": "mountain_sunset.jpg",   "file_size": "245.3KB", "resolution": "1920x1080", "description": "a majestic mountain with sunset colors"},
    {"file_name": "dog_park.jpg",          "file_size": "189.7KB", "resolution": "1280x720",  "description": "a dog playing in the park"},
    {"file_name": "red_car.jpg",           "file_size": "312.1KB", "resolution": "1920x1080", "description": "a red sports car on a highway"},
    {"file_name": "ocean_waves.jpg",       "file_size": "276.4KB", "resolution": "2560x1440", "description": "ocean waves crashing on rocks"},
    {"file_name": "city_night.jpg",        "file_size": "198.2KB", "resolution": "1920x1080", "description": "city skyline at night with lights"},
    {"file_name": "cat_windowsill.jpg",    "file_size": "145.6KB", "resolution": "1280x960",  "description": "a cat sitting on a windowsill"},
    {"file_name": "forest_trail.jpg",      "file_size": "334.8KB", "resolution": "2560x1440", "description": "a forest trail with tall trees and sunlight"},
    {"file_name": "beach_sunset.jpg",      "file_size": "267.9KB", "resolution": "1920x1080", "description": "golden sunset over a sandy beach"},
    {"file_name": "snow_mountain.jpg",     "file_size": "289.3KB", "resolution": "3840x2160", "description": "snow covered mountain peak under blue sky"},
    {"file_name": "flower_garden.jpg",     "file_size": "203.5KB", "resolution": "1600x1200", "description": "colorful flowers in a garden"},
]

SAMPLE_VIDEO_FRAMES = [
    {"video_name": "nature_doc.mp4", "video_path": "/data/videos/nature_doc.mp4", "duration_total": 120.0, "frames": [
        (0.5,  "a wide shot of african savanna"),
        (5.0,  "a rhino walking through grass"),
        (10.0, "close up of a rhino face"),
        (15.0, "birds flying over the savanna"),
        (20.0, "a zebra herd drinking water"),
        (25.0, "sunset over the savanna landscape"),
        (30.0, "a lion resting under a tree"),
        (35.0, "elephants crossing a river"),
        (40.0, "aerial view of the grasslands"),
        (45.0, "a cheetah running at full speed"),
    ]},
    {"video_name": "big_buck_bunny.mp4", "video_path": "/data/videos/big_buck_bunny.mp4", "duration_total": 60.0, "frames": [
        (0.5,  "animated forest scene with butterflies"),
        (5.0,  "a big bunny sitting in a meadow"),
        (10.0, "the bunny stretching and yawning"),
        (15.0, "small animals annoying the bunny"),
        (20.0, "the bunny looking angry"),
        (25.0, "the bunny chasing small creatures"),
        (30.0, "a bird flying through the forest"),
        (35.0, "the bunny setting up a trap"),
        (40.0, "an explosion of fruit"),
        (45.0, "the bunny laughing happily"),
    ]},
]


# -- Helpers ------------------------------------------------------------------

def fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


# -- Main ---------------------------------------------------------------------

def main():
    print(f"\n{'='*60}")
    print(f"  ARIA Vision — Sample Ingestion (Synthetic Embeddings)")
    print(f"{'='*60}")
    print(f"  Embed dim: {EMBED_DIM}")
    print(f"  Project  : {DEFAULT_PROJECT}")
    print()

    # -- 1. Clear old indexes ---------------------------------------------
    print("[1/4] Clearing old indexes...")
    img_store = get_store(DEFAULT_PROJECT, "image_index")
    vid_store = get_store(DEFAULT_PROJECT, "video_index")
    img_store.clear()
    vid_store.clear()
    print("  Done.\n")

    # -- 2. Ingest sample images ------------------------------------------
    print("[2/4] Ingesting sample images...")
    img_vecs = []
    img_ids = []
    img_meta = []

    for img in SAMPLE_IMAGES:
        vec = fake_embed(img["description"])
        img_vecs.append(vec)
        img_ids.append(img["file_name"])
        img_meta.append({
            "file_name": img["file_name"],
            "file_size": img["file_size"],
            "resolution": img["resolution"],
            "file_path": f"/data/images/{img['file_name']}",
        })
        print(f"  OK {img['file_name']} ({img['resolution']})")

    img_store.add(np.stack(img_vecs), img_ids, img_meta)
    print(f"  {len(img_ids)} images indexed -> {img_store}\n")

    # -- 3. Ingest sample video frames ------------------------------------
    print("[3/4] Ingesting sample video frames...")
    total_frames = 0

    for video in SAMPLE_VIDEO_FRAMES:
        print(f"  {video['video_name']} ({video['duration_total']:.0f}s -> {len(video['frames'])} frames)")
        for ts, desc in video["frames"]:
            vec = fake_embed(desc)
            frame_meta = {
                "video_path": video["video_path"],
                "video_name": video["video_name"],
                "timestamp_sec": ts,
                "timestamp_label": fmt(ts),
                "duration_total": video["duration_total"],
            }
            vid_store.append(vec, f"{video['video_name']}@{ts}", frame_meta)
            total_frames += 1

    # Rebuild CAGRA once after all frames
    vid_store.rebuild_gpu_index()
    vid_store._persist()
    print(f"  {total_frames} video frames indexed -> {vid_store}\n")

    # -- 4. Run sample queries --------------------------------------------
    print("[4/4] Running sample queries...\n")

    # --- Image query ---
    query = "a majestic mountain"
    print(f"{'='*60}")
    print(f"  ARIA Vision — Image Search")
    print(f"{'='*60}")
    print(f"  Query: \"{query}\"")
    print()

    qvec = fake_embed(query)
    results = img_store.search(qvec, top_k=5)

    print(f"  {'-'*56}")
    print(f"  {'Rank':<6} {'File':<25} {'Size':<10} {'Resolution':<12} {'Score':<8}")
    print(f"  {'-'*56}")
    for i, r in enumerate(results):
        print(f"  {i+1:<6} {r.get('file_name','?'):<25} "
              f"{r.get('file_size','?'):<10} "
              f"{r.get('resolution','?'):<12} "
              f"{r.get('score',0):.4f}")
    print(f"  {'-'*56}")

    output_img = {
        "mode": "Image",
        "query": query,
        "results": [
            {
                "file_path": r.get("file_path", ""),
                "file_name": r.get("file_name", ""),
                "file_size": r.get("file_size", ""),
                "resolution": r.get("resolution", ""),
                "score": round(r.get("score", 0), 4),
            }
            for r in results
        ],
    }
    print(f"\n  JSON Response:")
    print(f"  {json.dumps(output_img, indent=2)}")

    # --- Video query ---
    query2 = "a big bunny"
    print(f"\n{'='*60}")
    print(f"  ARIA Vision — Video Intelligence Search")
    print(f"{'='*60}")
    print(f"  Query: \"{query2}\"")
    print()

    qvec2 = fake_embed(query2)
    vid_results = vid_store.search(qvec2, top_k=10)

    # Merge into time ranges
    from search import _merge_video_hits
    spans = _merge_video_hits(vid_results, gap=10.0)

    print(f"  {'-'*62}")
    print(f"  {'#':<4} {'Video':<24} {'Time Range':<16} {'Duration':<9} {'Frames':<7} {'Score'}")
    print(f"  {'-'*62}")
    for i, s in enumerate(spans):
        dur = s["end_sec"] - s["start_sec"]
        print(f"  {i+1:<4} {s['video_name'][:23]:<24} "
              f"{fmt(s['start_sec'])} -> {fmt(s['end_sec']):<9} "
              f"{dur:4.0f}s     "
              f"{s['frames']:<7} "
              f"{s['peak_score']:.4f}")
    print(f"  {'-'*62}")

    output_vid = {
        "mode": "Video Intelligence",
        "query": query2,
        "matches": [
            {
                "video_name": s["video_name"],
                "video_path": s.get("video_path", ""),
                "start": fmt(s["start_sec"]),
                "end": fmt(s["end_sec"]),
                "start_seconds": s["start_sec"],
                "end_seconds": s["end_sec"],
                "score": round(s["peak_score"], 4),
                "frames_matched": s["frames"],
            }
            for s in spans
        ],
    }
    print(f"\n  JSON Response:")
    print(f"  {json.dumps(output_vid, indent=2)}")

    print(f"\n{'='*60}")
    print(f"  OK Done — {len(img_ids)} images + {total_frames} video frames indexed")
    print(f"  Store: {img_store}")
    print(f"  Store: {vid_store}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
