#!/usr/bin/env python3
"""
query_vision_image.py
======================
Query the image_index in SurrealDB using a text prompt.
Embeds the text with gemini-embedding-2, then performs cosine
similarity search against stored image embeddings.

Usage:
  uv run query_vision_image.py "sunset over water"
  uv run query_vision_image.py "a cat sitting on a windowsill"
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

# Reuse project's SurrealDB connection
sys.path.insert(0, str(Path(__file__).parent))
from open_notebook.database.repository import repo_query

# Config
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 2048
TOP_K = 5
MIN_SCORE = 0.3  # lower threshold for demo purposes

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY or GOOGLE_API_KEY not found in .env")
    sys.exit(1)

client = genai.Client(api_key=api_key)


def embed_text(text: str) -> list[float]:
    """Embed a text query using gemini-embedding-2."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(result.embeddings[0].values)


async def search_images(query: str):
    """Search image_index for images matching the text query."""
    print(f"\n{'='*60}")
    print(f"  ARIA Vision — Image Search")
    print(f"{'='*60}")
    print(f"  Query: \"{query}\"")
    print(f"  Model: {EMBEDDING_MODEL} ({EMBEDDING_DIM}d)")
    print()

    # 1. Embed the query text
    print("  [1/3] Embedding query text...", end=" ")
    query_vector = embed_text(query)
    print("✓")

    # 2. Vector search in SurrealDB
    print("  [2/3] Searching image_index...", end=" ")

    # SurrealDB vector search syntax
    results = await repo_query(
        """
        SELECT
            file_path,
            file_name,
            file_size,
            resolution,
            vector::similarity::cosine(embedding, $query_vec) AS score
        FROM image_index
        ORDER BY score DESC
        LIMIT $top_k;
        """,
        {"query_vec": query_vector, "top_k": TOP_K},
    )

    # Flatten result (repo_query returns list of statement results)
    rows = results[0] if results and isinstance(results[0], list) else results
    if not rows:
        print("no results.")
        print("\n  ⚠ No images found. Did you run ingest_sample_vision.py first?")
        return

    # Filter by score threshold
    rows = [r for r in rows if r.get("score", 0) >= MIN_SCORE]
    print(f"✓ ({len(rows)} matches)")

    # 3. Display results
    print(f"\n  [3/3] Results:")
    print(f"  {'─'*56}")
    print(f"  {'Rank':<6} {'File':<25} {'Size':<10} {'Resolution':<12} {'Score':<8}")
    print(f"  {'─'*56}")

    for i, row in enumerate(rows):
        file_name = row.get("file_name", Path(row.get("file_path", "?")).name)
        print(
            f"  {i+1:<6} {file_name:<25} "
            f"{row.get('file_size', '?'):<10} "
            f"{row.get('resolution', '?'):<12} "
            f"{row.get('score', 0):.4f}"
        )

    print(f"  {'─'*56}")

    # JSON output for programmatic use
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


async def main():
    if len(sys.argv) < 2:
        print("Usage: uv run query_vision_image.py \"your search query\"")
        print()
        print("Examples:")
        print("  uv run query_vision_image.py \"sunset over water\"")
        print("  uv run query_vision_image.py \"a dog playing in the park\"")
        print("  uv run query_vision_image.py \"mountain landscape\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    await search_images(query)


if __name__ == "__main__":
    asyncio.run(main())
