#!/usr/bin/env python3
"""
query_vision_image.py
======================
Query the HF-native image_index using a text prompt.
Embeds the text with CLIP / Qwen3-VL, then performs cosine
similarity search against stored image embeddings.

Usage:
  python query_vision_image.py "sunset over water"
"""

import sys
import json
from pathlib import Path

from config import DEFAULT_PROJECT, EMBED_MODEL, EMBED_DIM
from vector_store import get_store
from embedding import embed_text

TOP_K = 5
MIN_SCORE = 0.15 # Adjusted for HF-native CLIP/Qwen scores

def search_images(query: str):
    print(f"\n{'='*60}")
    print(f"  ARIA Vision — Image Search (HF-Native)")
    print(f"{'='*60}")
    print(f"  Query: \"{query}\"")
    print(f"  Model: {EMBED_MODEL} ({EMBED_DIM}d)")
    print()

    print("  [1/3] Embedding query text...", end=" ", flush=True)
    query_vector = embed_text(query)
    print("✓")

    print("  [2/3] Searching image_index...", end=" ", flush=True)
    store = get_store(DEFAULT_PROJECT, "image_index")
    raw_results = store.search(query_vector, top_k=TOP_K)
    
    if not raw_results:
        print("no results.")
        print("\n  ⚠ No images found. Did you run ingest_sample_vision.py first?")
        return

    rows = [r for r in raw_results if r.get("score", 0) >= MIN_SCORE]
    print(f"✓ ({len(rows)} matches)")

    print(f"\n  [3/3] Results:")
    print(f"  {'─'*56}")
    print(f"  {'Rank':<6} {'File':<25} {'Size':<10} {'Resolution':<12} {'Score':<8}")
    print(f"  {'─'*56}")

    for i, row in enumerate(rows):
        file_name = row.get("file_name", Path(row.get("file_path", "?")).name)
        print(
            f"  {i+1:<6} {file_name[:24]:<25} "
            f"{row.get('file_size', '?'):<10} "
            f"{row.get('resolution', '?'):<12} "
            f"{row.get('score', 0):.4f}"
        )

    print(f"  {'─'*56}")

    output = {
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
            for r in rows
        ],
    }
    print(f"\n  JSON Response:")
    print(f"  {json.dumps(output, indent=2)}")
    print()

def main():
    if len(sys.argv) < 2:
        print("Usage: python query_vision_image.py \"your search query\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    search_images(query)

if __name__ == "__main__":
    main()
