# vision/query/query_video.py

from vision.config import USING_AMD_GPU
from api.llm_provider import embed_text

if USING_AMD_GPU:
    from vision.hip_vs.hipvs_query import query_video_hipVS

async def query_video(text: str, top_k: int = 5):
    if USING_AMD_GPU:
        return await query_video_hipVS(text, top_k)

    # ── CPU path ──
    from open_notebook.database.repository import repo_query
    
    qvec = embed_text(text)
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
    
    rows = results[0] if results and isinstance(results[0], list) else results
    if not rows:
        return []
    return rows


if __name__ == "__main__":
    import asyncio
    import sys
    import json
    from dotenv import load_dotenv
    load_dotenv()

    async def main():
        if len(sys.argv) < 2:
            print("Usage: uv run python -m vision.query.query_video <query>")
            return
        query = " ".join(sys.argv[1:])
        print(f"Running video query: '{query}' (GPU={USING_AMD_GPU})")
        results = await query_video(query)
        print(json.dumps(results, indent=2))

    asyncio.run(main())
