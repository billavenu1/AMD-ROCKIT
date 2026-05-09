# vision/query/query_image.py

from vision.config import USING_AMD_GPU
from api.llm_provider import embed_text

if USING_AMD_GPU:
    from vision.hip_vs.hipvs_query import query_image_hipVS

async def query_image(text: str, top_k: int = 5):
    if USING_AMD_GPU:
        return await query_image_hipVS(text, top_k)

    # ── CPU path (existing SurrealDB flow) ──
    from open_notebook.database.repository import repo_query
    
    query_vector = embed_text(text)
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
        {"query_vec": query_vector, "top_k": top_k},
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
            print("Usage: uv run python -m vision.query.query_image <query>")
            return
        query = " ".join(sys.argv[1:])
        print(f"Running image query: '{query}' (GPU={USING_AMD_GPU})")
        results = await query_image(query)
        print(json.dumps(results, indent=2))

    asyncio.run(main())
