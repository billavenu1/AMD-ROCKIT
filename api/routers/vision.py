"""
api/routers/vision.py
======================
Real vision endpoint that embeds the user's text query with gemini-embedding-2,
then queries SurrealDB's video_index or image_index via cosine similarity.
Also serves media files from data/vision_samples/ for the frontend player.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from api.llm_provider import embed_text as _embed_text

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "vision_samples"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _merge_video_hits(hits: list[dict], gap: float = 10.0) -> list[dict]:
    """Merge adjacent frame-level hits into time ranges."""
    if not hits:
        return []

    by_video: dict[str, list[dict]] = {}
    for h in hits:
        key = h.get("video_name", "unknown")
        by_video.setdefault(key, []).append(h)

    merged = []
    for video_name, frames in by_video.items():
        frames.sort(key=lambda x: x.get("timestamp_sec", 0))
        current = {
            "video_name": video_name,
            "video_path": frames[0].get("video_path", ""),
            "start_sec":  frames[0].get("timestamp_sec", 0),
            "end_sec":    frames[0].get("timestamp_sec", 0),
            "peak_score": frames[0].get("score", 0),
            "frames":     1,
        }
        for f in frames[1:]:
            ts = f.get("timestamp_sec", 0)
            if ts <= current["end_sec"] + gap:
                current["end_sec"]    = ts
                current["peak_score"] = max(current["peak_score"], f.get("score", 0))
                current["frames"]    += 1
            else:
                merged.append(current)
                current = {
                    "video_name": video_name,
                    "video_path": f.get("video_path", ""),
                    "start_sec":  ts,
                    "end_sec":    ts,
                    "peak_score": f.get("score", 0),
                    "frames":     1,
                }
        merged.append(current)

    return sorted(merged, key=lambda x: -x["peak_score"])


# ── API Endpoints ────────────────────────────────────────────────────────────

class VisionChatRequest(BaseModel):
    prompt: str
    mode: str  # "Video Intelligence" or "Image"


@router.post("/chat")
async def vision_chat(request: VisionChatRequest):
    """
    Embed the text prompt with gemini-embedding-2 and search
    the appropriate SurrealDB vector index.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from open_notebook.database.repository import repo_query

    prompt = request.prompt
    mode   = request.mode

    try:
        query_vec = _embed_text(prompt)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Embedding failed: {str(e)}"},
        )

    if mode == "Video Intelligence":
        # Search video_index
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
            LIMIT 30;
            """,
            {"qvec": query_vec},
        )

        # Flatten (repo_query can return nested lists)
        rows = results[0] if results and isinstance(results[0], list) else results
        if not rows:
            rows = []

        # Filter by min threshold
        hits = [r for r in rows if r.get("score", 0) >= 0.35]

        spans = _merge_video_hits(hits)

        # Build the response
        video_name = spans[0]["video_name"] if spans else None
        duration   = spans[0].get("duration_total", 0) if spans else 0
        # Get duration from first row if available
        if not duration and rows:
            duration = rows[0].get("duration_total", 0)

        return {
            "mode":  "Video Intelligence",
            "query": prompt,
            "reply": f"I found {len(spans)} matching moment{'s' if len(spans) != 1 else ''} for \"{prompt}\".",
            "video_name": video_name,
            "duration": duration,
            "matches": [
                {
                    "id":            i + 1,
                    "video_name":    s["video_name"],
                    "start":         _fmt(s["start_sec"]),
                    "end":           _fmt(s["end_sec"]),
                    "start_seconds": s["start_sec"],
                    "end_seconds":   s["end_sec"],
                    "score":         round(s["peak_score"], 4),
                    "frames":        s["frames"],
                }
                for i, s in enumerate(spans)
            ],
        }

    else:
        # Search image_index
        results = await repo_query(
            """
            SELECT
                file_path,
                file_name,
                file_size,
                resolution,
                vector::similarity::cosine(embedding, $qvec) AS score
            FROM image_index
            ORDER BY score DESC
            LIMIT 10;
            """,
            {"qvec": query_vec},
        )

        rows = results[0] if results and isinstance(results[0], list) else results
        if not rows:
            rows = []

        hits = [r for r in rows if r.get("score", 0) >= 0.25]

        return {
            "mode":  "Image",
            "query": prompt,
            "reply": f"I found {len(hits)} matching image{'s' if len(hits) != 1 else ''} for \"{prompt}\".",
            "results": [
                {
                    "id":         i + 1,
                    "file_name":  r.get("file_name", ""),
                    "file_size":  r.get("file_size", ""),
                    "resolution": r.get("resolution", ""),
                    "score":      round(r.get("score", 0), 4),
                    # Serve via our static endpoint
                    "url":        f"/api/vision/media/images/{r.get('file_name', '')}",
                }
                for i, r in enumerate(hits)
            ],
        }


@router.get("/media/videos/{filename}")
async def serve_video(filename: str):
    """Serve a video file from data/vision_samples/videos/."""
    video_path = DATA_DIR / "videos" / filename
    if not video_path.exists():
        return JSONResponse(status_code=404, content={"error": "Video not found"})
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/media/images/{filename}")
async def serve_image(filename: str):
    """Serve an image file from data/vision_samples/images/."""
    image_path = DATA_DIR / "images" / filename
    if not image_path.exists():
        return JSONResponse(status_code=404, content={"error": "Image not found"})

    suffix = image_path.suffix.lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp"}.get(suffix, "image/jpeg")
    return FileResponse(path=str(image_path), media_type=mime)


@router.get("/videos")
async def list_videos():
    """List available videos for the dropdown."""
    videos_dir = DATA_DIR / "videos"
    if not videos_dir.exists():
        return []
    return [
        {"name": f.name, "size": f"{round(f.stat().st_size / (1024*1024), 1)}MB"}
        for f in sorted(videos_dir.iterdir())
        if f.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    ]
