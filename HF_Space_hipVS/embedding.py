# HF_Space_hipVS/embedding.py
# ============================
# Multimodal embedding + LLM calls.
#
# Embedding strategy: NO CAPTIONING.
#   GPU:  Qwen3-VL-Embedding (2B or 8B) — encodes images AND text into same space
#   CPU:  CLIP ViT-L/14 — same idea, lighter weight
#
# LLM strategy:
#   Primary:  Qwen3-35B-A3B (local or HF Inference API)
#   Fallback: Qwen3-1.7B or HF Inference API

import logging
import io
import numpy as np
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# ── Lazy-loaded model singletons ─────────────────────────────────────────────

_embed_model = None
_embed_processor = None
_embed_tokenizer = None
_is_clip = False


def _load_embed_model():
    """
    Lazy-init the multimodal embedding model.

    GPU path: Qwen3-VL-Embedding via transformers
    CPU path: CLIP via transformers (CLIPModel + CLIPProcessor)
    """
    global _embed_model, _embed_processor, _embed_tokenizer, _is_clip
    if _embed_model is not None:
        return

    import torch
    from config import EMBED_MODEL, DEVICE, USE_GPU

    model_lower = EMBED_MODEL.lower()

    if "clip" in model_lower:
        # ── CLIP path (CPU fallback) ────────────────────────────────────
        from transformers import CLIPModel, CLIPProcessor

        logger.info(f"Loading CLIP model: {EMBED_MODEL} on {DEVICE}")
        _embed_model = CLIPModel.from_pretrained(EMBED_MODEL).to(DEVICE)
        _embed_processor = CLIPProcessor.from_pretrained(EMBED_MODEL)
        _embed_model.eval()
        _is_clip = True
        logger.info("CLIP model loaded")

    else:
        # ── Qwen3-VL-Embedding path (GPU) ──────────────────────────────
        from transformers import AutoModel, AutoProcessor

        dtype = torch.float16 if USE_GPU else torch.float32
        logger.info(f"Loading Qwen3-VL-Embedding: {EMBED_MODEL} on {DEVICE}")
        _embed_model = AutoModel.from_pretrained(
            EMBED_MODEL,
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(DEVICE)
        _embed_processor = AutoProcessor.from_pretrained(
            EMBED_MODEL,
            trust_remote_code=True,
        )
        _embed_model.eval()
        _is_clip = False
        logger.info("Qwen3-VL-Embedding model loaded")


# ── Text Embedding ──────────────────────────────────────────────────────────

def embed_text(text: str) -> np.ndarray:
    """
    Embed a text string into the shared multimodal vector space.
    Works with both CLIP and Qwen3-VL-Embedding.
    Returns a normalized float32 numpy vector.
    """
    import torch
    from config import DEVICE

    _load_embed_model()

    with torch.no_grad():
        if _is_clip:
            inputs = _embed_processor(text=[text], return_tensors="pt", padding=True, truncation=True).to(DEVICE)
            features = _embed_model.get_text_features(**inputs)
        else:
            # Qwen3-VL-Embedding: text-only input
            inputs = _embed_processor(text=[text], return_tensors="pt", padding=True, truncation=True).to(DEVICE)
            outputs = _embed_model(**inputs)
            # Use the [CLS] token or mean pooling depending on model
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                features = outputs.pooler_output
            else:
                features = outputs.last_hidden_state[:, 0, :]

    vec = features.squeeze(0).cpu().float().numpy()
    # L2 normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def embed_texts(texts: list[str]) -> np.ndarray:
    """Batch embed multiple texts. Returns (N, D) float32 array."""
    import torch
    from config import DEVICE

    _load_embed_model()

    with torch.no_grad():
        if _is_clip:
            inputs = _embed_processor(text=texts, return_tensors="pt", padding=True, truncation=True).to(DEVICE)
            features = _embed_model.get_text_features(**inputs)
        else:
            inputs = _embed_processor(text=texts, return_tensors="pt", padding=True, truncation=True).to(DEVICE)
            outputs = _embed_model(**inputs)
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                features = outputs.pooler_output
            else:
                features = outputs.last_hidden_state[:, 0, :]

    vecs = features.cpu().float().numpy()
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vecs / norms


# ── Image Embedding (direct, no captioning) ─────────────────────────────────

def embed_image(image: PILImage.Image) -> np.ndarray:
    """
    Embed a PIL Image directly into the shared vector space.
    No captioning step — the vision encoder handles it natively.
    Returns a normalized float32 numpy vector.
    """
    import torch
    from config import DEVICE

    _load_embed_model()

    if image.mode != "RGB":
        image = image.convert("RGB")

    with torch.no_grad():
        if _is_clip:
            inputs = _embed_processor(images=image, return_tensors="pt").to(DEVICE)
            features = _embed_model.get_image_features(**inputs)
        else:
            # Qwen3-VL-Embedding: image input via processor
            inputs = _embed_processor(images=image, return_tensors="pt").to(DEVICE)
            outputs = _embed_model(**inputs)
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                features = outputs.pooler_output
            else:
                features = outputs.last_hidden_state[:, 0, :]

    vec = features.squeeze(0).cpu().float().numpy()
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def embed_image_bytes(data: bytes, mime_type: str = "image/jpeg") -> np.ndarray:
    """Embed raw image bytes. Returns normalized float32 vector."""
    image = PILImage.open(io.BytesIO(data))
    return embed_image(image)


# ── LLM Summarization ──────────────────────────────────────────────────────

def llm_summarize(query: str, search_results: list[dict], mode: str = "image") -> str:
    """
    Pass search results through an LLM for human-friendly interpretation.
    Tries: local model -> HF Inference API -> plain text fallback.
    """
    from config import LLM_MODEL, LLM_FALLBACK, HF_TOKEN

    if not search_results:
        return f'No results found for "{query}". Try uploading more media or using different search terms.'

    # Build prompt context
    if mode == "video":
        results_text = "\n".join(
            f"  - Video: {r.get('video_name', '?')}, "
            f"Time: {r.get('timestamp_label', '?')} ({r.get('timestamp_sec', 0):.1f}s), "
            f"Score: {r.get('score', 0):.4f}"
            for r in search_results
        )
        instruction = (
            "You are a vision search assistant. Summarize the video search results below. "
            "Highlight the most relevant moments and time ranges. Be concise. Use markdown."
        )
    else:
        results_text = "\n".join(
            f"  - Image: {r.get('file_name', '?')}, "
            f"Score: {r.get('score', 0):.4f}"
            for r in search_results
        )
        instruction = (
            "You are a vision search assistant. Summarize the image search results below. "
            "Highlight the most relevant matches. Be concise. Use markdown."
        )

    prompt = (
        f"{instruction}\n\n"
        f"User query: \"{query}\"\n\n"
        f"Search results ({len(search_results)} matches):\n{results_text}\n\n"
        f"Summary:"
    )

    # Try HF Inference API (works for both local and remote models)
    for model_id in (LLM_MODEL, LLM_FALLBACK):
        try:
            from huggingface_hub import InferenceClient

            client = InferenceClient(
                model=model_id,
                token=HF_TOKEN if HF_TOKEN else None,
            )
            response = client.text_generation(
                prompt,
                max_new_tokens=300,
                temperature=0.7,
                do_sample=True,
            )
            if response and response.strip():
                return response.strip()
        except Exception as e:
            logger.warning(f"LLM {model_id} failed: {e}")
            continue

    # Plain text fallback
    return (
        f"**Found {len(search_results)} results for \"{query}\"**\n\n"
        f"_(LLM summary unavailable)_\n\n"
        f"```\n{results_text}\n```"
    )
