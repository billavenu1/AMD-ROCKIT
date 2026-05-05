"""
api/llm_provider.py
====================
Single centralized module for ALL LLM and Embedding calls.
Every router/service should import from here instead of creating its own clients.
"""

import json
import os
from pathlib import Path
from typing import AsyncGenerator, List, Optional

from loguru import logger

# ── Configuration ────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
_AVAILABLE_MODELS_FILE = DATA_DIR / "available_models.json"


def get_available_models() -> list[dict]:
    """Return the list of available chat models from available_models.json."""
    if not _AVAILABLE_MODELS_FILE.exists():
        return []
    with open(_AVAILABLE_MODELS_FILE, "r") as f:
        return json.load(f)


def get_default_model_id() -> str:
    """Return the first model ID from available_models.json (the default)."""
    models = get_available_models()
    if models:
        return models[0]["id"]
    return os.getenv("DEFAULT_CHAT_MODEL", "gemini-2.5-flash-preview-05-20")


def _get_api_key() -> str:
    """Resolve the Gemini / Google API key from environment."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set")
    return key


def _get_openai_base_url() -> str:
    """Return the OpenAI-compatible base URL for Gemini."""
    return os.getenv(
        "OPENAI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )


# ── Lazy-init Gemini native client (for embeddings) ─────────────────────────

_genai_client = None


def _get_genai_client():
    """Lazy-init the google.genai Client (used for embedding calls)."""
    global _genai_client
    if _genai_client is None:
        from google import genai

        _genai_client = genai.Client(api_key=_get_api_key())
    return _genai_client


# ── Embedding ────────────────────────────────────────────────────────────────


def embed_text(
    text: str,
    model: str = "gemini-embedding-2",
    output_dimensionality: int = 2048,
) -> list[float]:
    """
    Embed a single text string using the Gemini embedding model.
    Returns a list of floats (the embedding vector).
    """
    from google.genai import types

    client = _get_genai_client()
    result = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=output_dimensionality),
    )
    return list(result.embeddings[0].values)


# ── Multimodal helpers ───────────────────────────────────────────────────────


def encode_image_to_data_url(
    image_path: str,
    mime_type: Optional[str] = None,
) -> str:
    """
    Read an image file and return a base64-encoded data URL
    suitable for the OpenAI-compatible ``image_url`` content part.

    Usage in messages::

        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {"type": "image_url", "image_url": {"url": encode_image_to_data_url("photo.jpg")}}
            ]
        }
    """
    import base64
    import mimetypes

    path = Path(image_path)
    if not mime_type:
        mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{b64}"


def encode_video_frame(
    video_path: str,
    timestamp_sec: float = 0.0,
    mime_type: str = "image/jpeg",
) -> str:
    """
    Extract a single frame from a video at the given timestamp and return
    it as a base64 data URL.  Requires ffmpeg in PATH.
    """
    import base64
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(timestamp_sec),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                tmp_path,
            ],
            capture_output=True,
            check=True,
        )
        with open(tmp_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def build_multimodal_message(
    text: str,
    image_paths: Optional[List[str]] = None,
    image_urls: Optional[List[str]] = None,
    role: str = "user",
) -> dict:
    """
    Build an OpenAI-format message with text + images.

    Parameters
    ----------
    text : str
        The text portion of the message.
    image_paths : list[str] | None
        Local file paths to images -- they will be base64-encoded automatically.
    image_urls : list[str] | None
        Already-encoded data URLs or public HTTP URLs for images.
    role : str
        Message role (default "user").

    Returns
    -------
    dict
        A message dict ready to be appended to the messages list.
    """
    content: list[dict] = [{"type": "text", "text": text}]

    for path in (image_paths or []):
        data_url = encode_image_to_data_url(path)
        content.append({
            "type": "image_url",
            "image_url": {"url": data_url},
        })

    for url in (image_urls or []):
        content.append({
            "type": "image_url",
            "image_url": {"url": url},
        })

    return {"role": role, "content": content}


# ── LLM Chat Completion (streaming) ─────────────────────────────────────────


async def stream_chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream an OpenAI-compatible chat completion from Gemini.

    Yields raw JSON chunks (one per line, no SSE `data:` prefix) suitable
    for piping straight into an NDJSON response.

    Parameters
    ----------
    messages : list[dict]
        OpenAI-format messages ([{"role": "user", "content": "..."}]).
    model : str | None
        Model ID to use.  Falls back to the first available model.
    system_prompt : str | None
        If provided and no system message exists in `messages`, it will be
        prepended.
    """
    from openai import AsyncOpenAI

    resolved_model = model or get_default_model_id()
    api_key = _get_api_key()

    client = AsyncOpenAI(api_key=api_key, base_url=_get_openai_base_url())

    # Inject system prompt if needed
    if system_prompt and not any(m["role"] == "system" for m in messages):
        messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        stream = await client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            stream=True,
        )
    except Exception as api_err:
        logger.error(f"LLM API Error with model {resolved_model}: {api_err}")
        error_chunk = {
            "id": "error",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": resolved_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": (
                            f"\n\n**Error:** Failed to connect to AI Provider. "
                            f"Model `{resolved_model}` may be invalid or API key "
                            f"is restricted.\n\nDetails: `{str(api_err)}`"
                        )
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        yield json.dumps(error_chunk) + "\n"
        return

    async for chunk in stream:
        yield chunk.model_dump_json() + "\n"


async def get_chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Non-streaming chat completion.  Returns the full response text.
    """
    full_response = ""
    async for chunk_json in stream_chat_completion(messages, model, system_prompt):
        try:
            data = json.loads(chunk_json)
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_response += content
        except json.JSONDecodeError:
            continue
    return full_response
