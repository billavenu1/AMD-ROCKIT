#!/usr/bin/env python3
"""
query_vision_video.py
======================
Query video_index using a text prompt.
Each row is one embedded frame at a specific second.
Adjacent high-scoring frames are merged into contiguous time ranges.

Usage:
  uv run query_vision_video.py "rhino running in the wild"
  uv run query_vision_video.py "person waving"  --top 10  --min-score 0.5
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).parent))
from open_notebook.database.repository import repo_query

# ── Config ───────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM   = 2048
TOP_K           = 30     # fetch enough raw hits to allow merging
MIN_SCORE       = 0.38   # lower = more results; raise if too many false positives
MERGE_GAP_SEC   = 10     # merge hits within N seconds of each other

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY / GOOGLE_API_KEY not set in .env")
    sys.exit(1)

client = genai.Client(api_key=api_key)


def fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def embed_text(text: str) -> list[float]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(result.embeddings[0].values)


def merge_hits(hits: list[dict], gap: float = MERGE_GAP_SEC) -> list[dict]:
    """
    Merge adjacent frame hits (by timestamp_sec) within `gap` seconds.
    Takes the max score in each merged span.
    Returns list of {video_name, video_path, start_sec, end_sec, score}.
    """
    if not hits:
        return []

    # Group hits by video first
    by_video: dict[str, list[dict]] = {}
    for h in hits:
        by_video.setdefault(h["video_name"], []).append(h)

    merged_all = []
    for video_name, frames in by_video.items():
        frames = sorted(frames, key=lambda x: x["timestamp_sec"])
        current = {
            "video_name": video_name,
            "video_path": frames[0].get("video_path", ""),
            "start_sec":  frames[0]["timestamp_sec"],
            "end_sec":    frames[0]["timestamp_sec"],
            "peak_score": frames[0]["score"],
            "frame_count": 1,
        }

        for f in frames[1:]:
            if f["timestamp_sec"] <= current["end_sec"] + gap:
                current["end_sec"]    = f["timestamp_sec"]
                current["peak_score"] = max(current["peak_score"], f["score"])
                current["frame_count"] += 1
            else:
                merged_all.append(current)
                current = {
                    "video_name":  video_name,
                    "video_path":  f.get("video_path", ""),
                    "start_sec":   f["timestamp_sec"],
                    "end_sec":     f["timestamp_sec"],
                    "peak_score":  f["score"],
                    "frame_count": 1,
                }

        merged_all.append(current)

    return sorted(merged_all, key=lambda x: -x["peak_score"])


async def search(query: str, top_k: int = TOP_K, min_score: float = MIN_SCORE):
    print(f"\n{'='*60}")
    print(f"  ARIA Vision — Video Intelligence Search")
    print(f"{'='*60}")
    print(f"  Query      : \"{query}\"")
    print(f"  Min score  : {min_score}  |  Merge gap: {MERGE_GAP_SEC}s  |  Fetch top: {top_k}")
    print()

    print("  [1/3] Embedding query...", end=" ", flush=True)
    qvec = embed_text(query)
    print("✓")

    print("  [2/3] Searching video_index...", end=" ", flush=True)
    results = await repo_query(
        """
        SELECT
            video_path,
            video_name,
            timestamp_sec,
            timestamp_label,
            duration_total,
            vector::similarity::cosine(embedding, $qvec) AS score
        FROM video_index
        ORDER BY score DESC
        LIMIT $top_k;
        """,
        {"qvec": qvec, "top_k": top_k},
    )

    # Flatten
    rows = results[0] if results and isinstance(results[0], list) else results
    if not rows:
        print("no results.\n  ⚠ Run ingest_sample_vision.py first.")
        return

    print(f"✓  ({len(rows)} raw frames returned)")

    # Filter by score
    hits = [r for r in rows if r.get("score", 0) >= min_score]
    if not hits:
        top3 = sorted(rows, key=lambda r: -r.get("score", 0))[:3]
        print(f"\n  ⚠ No frames above score threshold ({min_score}).")
        print(f"  Top 3 raw scores: {[round(r.get('score',0),4) for r in top3]}")
        print(f"  Try lowering MIN_SCORE at the top of this script.")
        return

    print(f"  [3/3] Merging {len(hits)} hits into time ranges...")

    spans = merge_hits(hits)

    # ── Print table ─────────────────────────────────────────────────────────
    print()
    print(f"  {'─'*62}")
    print(f"  {'#':<4} {'Video':<24} {'Time Range':<16} {'Duration':<9} {'Frames':<7} {'Score'}")
    print(f"  {'─'*62}")

    for i, s in enumerate(spans):
        dur = s["end_sec"] - s["start_sec"]
        print(
            f"  {i+1:<4} {s['video_name'][:23]:<24} "
            f"{fmt(s['start_sec'])} → {fmt(s['end_sec']):<9} "
            f"{dur:4.0f}s     "
            f"{s['frame_count']:<7} "
            f"{s['peak_score']:.4f}"
        )

    print(f"  {'─'*62}")

    # ── JSON output ──────────────────────────────────────────────────────────
    output = {
        "mode":    "Video Intelligence",
        "query":   query,
        "matches": [
            {
                "video_name":    s["video_name"],
                "video_path":    s["video_path"],
                "start":         fmt(s["start_sec"]),
                "end":           fmt(s["end_sec"]),
                "start_seconds": s["start_sec"],
                "end_seconds":   s["end_sec"],
                "score":         round(s["peak_score"], 4),
                "frames_matched": s["frame_count"],
            }
            for s in spans
        ],
    }

    print()
    print("  JSON Response:")
    print(f"  {json.dumps(output, indent=2)}")

    # ── Playback hint ────────────────────────────────────────────────────────
    if spans:
        best = spans[0]
        print()
        print("  Playback hints for best match:")
        print(f"     HTML5 : <video src=\"{best['video_name']}#t={best['start_sec']},{best['end_sec']}\">")
        print(f"     ffplay: ffplay -ss {best['start_sec']:.1f} "
              f"-t {best['end_sec'] - best['start_sec']:.1f} "
              f"\"{best['video_path']}\"")
    print()


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top  = int(next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--top"), TOP_K))
    msc  = float(next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--min-score"), MIN_SCORE))

    if not args:
        print('Usage: uv run query_vision_video.py "your query"')
        print('       uv run query_vision_video.py "zebra" --top 20 --min-score 0.4')
        sys.exit(1)

    await search(" ".join(args), top_k=top, min_score=msc)


if __name__ == "__main__":
    asyncio.run(main())
