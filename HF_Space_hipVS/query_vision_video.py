#!/usr/bin/env python3
"""
query_vision_video.py
======================
Query HF-native video_index using a text prompt.
Each row is one embedded frame at a specific second.
Adjacent high-scoring frames are merged into contiguous time ranges.

Usage:
  python query_vision_video.py "rhino running in the wild"
  python query_vision_video.py "person waving"  --top 10  --min-score 0.15
"""

import sys
import json
from pathlib import Path

from config import DEFAULT_PROJECT, EMBED_MODEL, EMBED_DIM
from vector_store import get_store
from embedding import embed_text
from search import _merge_video_hits, _fmt as fmt

TOP_K = 30
MIN_SCORE = 0.15 # Adjusted for HF-native CLIP/Qwen scores
MERGE_GAP_SEC = 10

def search_video(query: str, top_k: int = TOP_K, min_score: float = MIN_SCORE):
    print(f"\n{'='*60}")
    print(f"  ARIA Vision — Video Intelligence Search (HF-Native)")
    print(f"{'='*60}")
    print(f"  Query      : \"{query}\"")
    print(f"  Model      : {EMBED_MODEL} ({EMBED_DIM}d)")
    print(f"  Min score  : {min_score}  |  Merge gap: {MERGE_GAP_SEC}s  |  Fetch top: {top_k}")
    print()

    print("  [1/3] Embedding query...", end=" ", flush=True)
    qvec = embed_text(query)
    print("✓")

    print("  [2/3] Searching video_index...", end=" ", flush=True)
    store = get_store(DEFAULT_PROJECT, "video_index")
    raw_results = store.search(qvec, top_k=top_k)

    if not raw_results:
        print("no results.\n  ⚠ Run ingest_sample_vision.py first.")
        return

    print(f"✓  ({len(raw_results)} raw frames returned)")

    hits = [r for r in raw_results if r.get("score", 0) >= min_score]
    if not hits:
        top3 = sorted(raw_results, key=lambda r: -r.get("score", 0))[:3]
        print(f"\n  ⚠ No frames above score threshold ({min_score}).")
        print(f"  Top 3 raw scores: {[round(r.get('score',0),4) for r in top3]}")
        return

    print(f"  [3/3] Merging {len(hits)} hits into time ranges...")
    spans = _merge_video_hits(hits, gap=MERGE_GAP_SEC)

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
            f"{s['frames']:<7} "
            f"{s['peak_score']:.4f}"
        )

    print(f"  {'─'*62}")

    output = {
        "mode":    "Video Intelligence",
        "query":   query,
        "matches": [
            {
                "video_name":    s["video_name"],
                "video_path":    s.get("video_path", ""),
                "start":         fmt(s["start_sec"]),
                "end":           fmt(s["end_sec"]),
                "start_seconds": s["start_sec"],
                "end_seconds":   s["end_sec"],
                "score":         round(s["peak_score"], 4),
                "frames_matched": s["frames"],
            }
            for s in spans
        ],
    }

    print()
    print("  JSON Response:")
    print(f"  {json.dumps(output, indent=2)}")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top  = int(next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--top"), TOP_K))
    msc  = float(next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--min-score"), MIN_SCORE))

    if not args:
        print('Usage: python query_vision_video.py "your query"')
        sys.exit(1)

    search_video(" ".join(args), top_k=top, min_score=msc)

if __name__ == "__main__":
    main()
