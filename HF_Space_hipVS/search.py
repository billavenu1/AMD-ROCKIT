# HF_Space_hipVS/search.py
# =========================
# Search — embed query, search project's vector store, LLM interpret.

import logging
from embedding import embed_text, llm_summarize
from vector_store import get_store
from config import DEFAULT_PROJECT

logger = logging.getLogger(__name__)


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _merge_video_hits(hits: list[dict], gap: float = 10.0) -> list[dict]:
    """Merge adjacent frame-level hits into time ranges."""
    if not hits:
        return []
    by_video: dict[str, list[dict]] = {}
    for h in hits:
        by_video.setdefault(h.get("video_name", "?"), []).append(h)

    merged = []
    for video_name, frames in by_video.items():
        frames.sort(key=lambda x: x.get("timestamp_sec", 0))
        cur = {
            "video_name": video_name,
            "video_path": frames[0].get("video_path", ""),
            "start_sec":  frames[0].get("timestamp_sec", 0),
            "end_sec":    frames[0].get("timestamp_sec", 0),
            "peak_score": frames[0].get("score", 0),
            "frames":     1,
        }
        for f in frames[1:]:
            ts = f.get("timestamp_sec", 0)
            if ts <= cur["end_sec"] + gap:
                cur["end_sec"]    = ts
                cur["peak_score"] = max(cur["peak_score"], f.get("score", 0))
                cur["frames"]    += 1
            else:
                merged.append(cur)
                cur = {
                    "video_name": video_name,
                    "video_path": f.get("video_path", ""),
                    "start_sec":  ts,
                    "end_sec":    ts,
                    "peak_score": f.get("score", 0),
                    "frames":     1,
                }
        merged.append(cur)

    return sorted(merged, key=lambda x: -x["peak_score"])


def search_images(query: str, project: str = DEFAULT_PROJECT, top_k: int = 10, min_score: float = 0.15) -> dict:
    store = get_store(project, "image_index")
    if store.count == 0:
        return {
            "query": query, "results": [],
            "llm_summary": f"No images indexed in project '{project}'. Upload images first.",
            "store_info": str(store),
        }

    query_vec = embed_text(query)
    raw = store.search(query_vec, top_k=top_k)
    filtered = [r for r in raw if r.get("score", 0) >= min_score]
    summary = llm_summarize(query, filtered, mode="image")

    return {
        "query": query,
        "results": filtered,
        "llm_summary": summary,
        "store_info": str(store),
    }


def search_videos(query: str, project: str = DEFAULT_PROJECT, top_k: int = 30, min_score: float = 0.15) -> dict:
    store = get_store(project, "video_index")
    if store.count == 0:
        return {
            "query": query, "matches": [],
            "llm_summary": f"No videos indexed in project '{project}'. Upload videos first.",
            "store_info": str(store),
        }

    query_vec = embed_text(query)
    raw = store.search(query_vec, top_k=top_k)
    filtered = [r for r in raw if r.get("score", 0) >= min_score]
    spans = _merge_video_hits(filtered)

    result_for_llm = [
        {
            "video_name": s["video_name"],
            "timestamp_sec": s["start_sec"],
            "timestamp_label": f"{_fmt(s['start_sec'])} - {_fmt(s['end_sec'])}",
            "score": s["peak_score"],
        }
        for s in spans
    ]
    summary = llm_summarize(query, result_for_llm, mode="video")

    return {
        "query": query,
        "matches": [
            {
                "id": i + 1,
                "video_name": s["video_name"],
                "start": _fmt(s["start_sec"]),
                "end": _fmt(s["end_sec"]),
                "start_seconds": s["start_sec"],
                "end_seconds": s["end_sec"],
                "score": round(s["peak_score"], 4),
                "frames": s["frames"],
            }
            for i, s in enumerate(spans)
        ],
        "llm_summary": summary,
        "store_info": str(store),
    }
