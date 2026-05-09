"""
api/llm_provider.py
====================
Single centralized module for ALL LLM, Embedding, and TTS calls.
Every router/service should import from here instead of creating its own clients.

Three core functions:
  1. stream_chat_completion() / get_chat_completion()  — Text generation
  2. embed_text()                                       — Embeddings
  3. text_to_speech()                                   — TTS

All functions resolve models from data/available_models.json and respect
the USE_GPU flag from .env.
"""

import json
import os
import struct
import mimetypes
from pathlib import Path
from typing import AsyncGenerator, List, Optional

from loguru import logger

# ── Configuration ────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
_AVAILABLE_MODELS_FILE = DATA_DIR / "available_models.json"


def is_gpu_enabled() -> bool:
    """Check if GPU/vLLM mode is enabled via USE_GPU env var."""
    return os.getenv("USE_GPU", "false").lower() in ("true", "1", "yes")


def get_vllm_base_url() -> str:
    """Return the vLLM server base URL."""
    return os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")


def get_available_models() -> list[dict]:
    """Return the list of all models from available_models.json."""
    if not _AVAILABLE_MODELS_FILE.exists():
        return []
    with open(_AVAILABLE_MODELS_FILE, "r") as f:
        return json.load(f)


def get_models_by_type(model_type: str) -> list[dict]:
    """Return models filtered by type (language, embedding, tts)."""
    return [m for m in get_available_models() if m.get("type") == model_type]


def get_default_model_id() -> str:
    """Return the first language model ID from available_models.json (the default)."""
    models = get_models_by_type("language")
    if models:
        return models[0]["id"]
    return os.getenv("DEFAULT_CHAT_MODEL", "gemini-2.5-flash-preview-05-20")


def get_default_embedding_model() -> dict | None:
    """Return the first embedding model config from available_models.json."""
    models = get_models_by_type("embedding")
    if not models:
        return None
    # If GPU is enabled, prefer vllm provider; otherwise prefer google
    if is_gpu_enabled():
        vllm_models = [m for m in models if m.get("provider") == "vllm"]
        if vllm_models:
            return vllm_models[0]
    google_models = [m for m in models if m.get("provider") == "google"]
    return google_models[0] if google_models else models[0]


def get_default_tts_model() -> dict | None:
    """Return the first TTS model config from available_models.json."""
    models = get_models_by_type("tts")
    if not models:
        return None
    # If GPU is enabled, prefer vllm provider; otherwise prefer google
    if is_gpu_enabled():
        vllm_models = [m for m in models if m.get("provider") == "vllm"]
        if vllm_models:
            return vllm_models[0]
    google_models = [m for m in models if m.get("provider") == "google"]
    return google_models[0] if google_models else models[0]


def _resolve_model_config(model_id: str | None, model_type: str) -> dict:
    """Resolve a model ID to its full config dict from available_models.json."""
    if model_id:
        for m in get_available_models():
            if m["id"] == model_id and m.get("type") == model_type:
                return m
        # Fallback: return a minimal config with just the ID
        return {"id": model_id, "provider": "google", "type": model_type}

    if model_type == "embedding":
        cfg = get_default_embedding_model()
    elif model_type == "tts":
        cfg = get_default_tts_model()
    else:
        cfg = {"id": get_default_model_id(), "provider": "google", "type": "language"}

    if cfg is None:
        raise RuntimeError(f"No {model_type} model configured in available_models.json")
    return cfg


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
    model: str | None = None,
    output_dimensionality: int | None = None,
) -> list[float]:
    """
    Embed a single text string.
    Returns a list of floats (the embedding vector).

    Supports both Google Gemini and OpenAI-compatible (vLLM) endpoints.
    The provider is resolved from available_models.json based on the model ID.
    """
    model_config = _resolve_model_config(model, "embedding")
    provider = model_config.get("provider", "google")
    dim = output_dimensionality or model_config.get("params", {}).get("dimensions", 2048)
    model_id = model_config["id"]

    if provider == "google":
        from google.genai import types

        client = _get_genai_client()
        result = client.models.embed_content(
            model=model_id,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=dim),
        )
        return list(result.embeddings[0].values)

    elif provider == "vllm":
        from openai import OpenAI

        base_url = model_config.get("params", {}).get("base_url", get_vllm_base_url())
        client = OpenAI(base_url=base_url, api_key="EMPTY")
        result = client.embeddings.create(model=model_id, input=text)
        return list(result.data[0].embedding)

    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


# ── TTS (Text-to-Speech) ────────────────────────────────────────────────────


def _convert_l16_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Convert raw L16 PCM audio to WAV format."""
    bits_per_sample = 16
    sample_rate = 24000

    parts = mime_type.split(";")
    for param in parts:
        param = param.strip().lower()
        if param.startswith("rate="):
            try:
                sample_rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif "audio/l" in param:
            try:
                bits_per_sample = int(param.split("l", 1)[1])
            except (ValueError, IndexError):
                pass

    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1,
        num_channels, sample_rate, byte_rate, block_align,
        bits_per_sample, b"data", data_size,
    )
    return header + audio_data


async def text_to_speech(
    text: str,
    model: str | None = None,
    voice: str | None = None,
    output_path: str | None = None,
) -> bytes | str:
    """
    Generate speech from text.

    If output_path is provided, saves the audio file and returns the path.
    Otherwise returns raw audio bytes.

    Supports:
      - vLLM-served models (e.g. Qwen3-TTS) via OpenAI-compatible API
      - Google Gemini TTS via native API

    Parameters
    ----------
    text : str
        The text to convert to speech.
    model : str | None
        Model ID. Resolved from available_models.json if not provided.
    voice : str | None
        Voice name. Falls back to the first voice in model config.
    output_path : str | None
        If provided, saves audio to this path and returns the path string.
    """
    model_config = _resolve_model_config(model, "tts")
    provider = model_config.get("provider", "google")
    model_id = model_config["id"]
    params = model_config.get("params", {})
    default_voice = params.get("voices", ["Cherry"])[0]
    resolved_voice = voice or default_voice

    if provider == "vllm":
        from openai import OpenAI

        base_url = params.get("base_url", get_vllm_base_url())
        client = OpenAI(base_url=base_url, api_key="EMPTY")

        response = client.audio.speech.create(
            model=model_id,
            voice=resolved_voice,
            input=text,
        )
        audio_bytes = response.content

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"TTS audio saved to {output_path}")
            return output_path
        return audio_bytes

    elif provider == "google":
        from google.genai import types as genai_types

        client = _get_genai_client()

        contents = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=text)],
            ),
        ]

        generate_content_config = genai_types.GenerateContentConfig(
            temperature=1,
            response_modalities=["audio"],
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=resolved_voice
                    )
                )
            ),
        )

        audio_data = b""
        mime_type = "audio/L16;rate=24000"

        for chunk in client.models.generate_content_stream(
            model=model_id,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.parts is None:
                continue
            for part in chunk.parts:
                if part.inline_data and part.inline_data.data:
                    audio_data += part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type

        if not audio_data:
            raise RuntimeError("No audio data generated by Gemini TTS")

        # Convert L16 to WAV if needed
        file_extension = mimetypes.guess_extension(mime_type)
        if not file_extension or "L16" in mime_type:
            file_extension = ".wav"
            audio_data = _convert_l16_to_wav(audio_data, mime_type)

        if output_path:
            final_path = str(Path(output_path).with_suffix(file_extension))
            Path(final_path).parent.mkdir(parents=True, exist_ok=True)
            with open(final_path, "wb") as f:
                f.write(audio_data)
            logger.info(f"Gemini TTS audio saved to {final_path}")
            return final_path
        return audio_data

    else:
        raise ValueError(f"Unknown TTS provider: {provider}")


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
