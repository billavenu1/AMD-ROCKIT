import json
import os
from pathlib import Path

from esperanto import LanguageModel
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from open_notebook.ai.models import model_manager
from open_notebook.exceptions import ConfigurationError
from open_notebook.utils import token_count


# ── vLLM / GPU Bridge ───────────────────────────────────────────────────────
# When USE_GPU=true, this module bypasses Esperanto and returns a ChatOpenAI
# object pointing directly at the local vLLM server.  This is the exact same
# pattern the user tested:
#
#   from langchain_openai import ChatOpenAI
#   llm = ChatOpenAI(model="Qwen/Qwen3-32B", base_url="http://localhost:8001/v1",
#                    api_key="EMPTY", streaming=True)
#   llm.invoke([HumanMessage(content="hello")])
#
# The returned object is a full BaseChatModel — it supports .invoke(),
# .stream(), .bind_tools(), and everything LangGraph needs.
# ─────────────────────────────────────────────────────────────────────────────


def _is_gpu_enabled() -> bool:
    """Check USE_GPU flag directly from env (avoids circular import with api layer)."""
    return os.getenv("USE_GPU", "false").lower() in ("true", "1", "yes")


def _get_vllm_langchain_model(**kwargs) -> BaseChatModel | None:
    """
    Try to create a ChatOpenAI pointing to a running vLLM deployment.
    Returns None if no deployment is available or langchain_openai is missing.
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        logger.warning("langchain_openai not installed — cannot use vLLM bridge. "
                       "Install with: pip install langchain-openai")
        return None

    base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")

    # 1. Check VLLM_MODEL_NAME env var (explicit override)
    model_name = os.getenv("VLLM_MODEL_NAME")

    # 2. Auto-detect from deployed_models.json
    if not model_name:
        deployed_file = Path(__file__).parent.parent.parent / "data" / "deployed_models.json"
        if deployed_file.exists():
            try:
                with open(deployed_file) as f:
                    deployments = json.load(f)
                for dep in deployments:
                    if dep.get("status", "").lower() == "running":
                        model_name = (
                            dep.get("config", {}).get("hf_model")
                            or dep.get("model_id", "")
                        )
                        if model_name:
                            break
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Could not read deployed_models.json: {e}")

    if not model_name:
        logger.debug("vLLM bridge: No running deployment found and VLLM_MODEL_NAME not set")
        return None

    try:
        max_tokens = kwargs.get("max_tokens", 8192)
        llm = ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key="EMPTY",
            max_tokens=max_tokens,
            streaming=True,
        )
        logger.info(f"vLLM bridge: Using local model '{model_name}' at {base_url}")
        return llm
    except Exception as e:
        logger.warning(f"vLLM bridge: Failed to create ChatOpenAI: {e}")
        return None


# ── Main Provisioner ─────────────────────────────────────────────────────────


async def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    """
    Returns the best model to use based on the context size and on whether there is a specific model being requested in Config.
    If context > 105_000, returns the large_context_model
    If model_id is specified in Config, returns that model
    Otherwise, returns the default model for the given type

    GPU Bridge: When USE_GPU=true and no explicit model_id is requested,
    this function will return a ChatOpenAI pointing at the local vLLM server
    instead of going through Esperanto.  This means the Notebook Chat,
    Source Chat, and Transformations all automatically use your GPU.
    """
    # ── GPU Bridge: try vLLM first when enabled ─────────────────────────
    if _is_gpu_enabled() and not model_id:
        vllm_model = _get_vllm_langchain_model(**kwargs)
        if vllm_model is not None:
            return vllm_model
        logger.debug("vLLM bridge: No model available, falling back to Esperanto")

    # ── Existing Esperanto logic (unchanged) ────────────────────────────
    tokens = token_count(content)
    model = None
    selection_reason = ""

    if tokens > 105_000:
        selection_reason = f"large_context (content has {tokens} tokens)"
        logger.debug(
            f"Using large context model because the content has {tokens} tokens"
        )
        model = await model_manager.get_default_model("large_context", **kwargs)
    elif model_id:
        selection_reason = f"explicit model_id={model_id}"
        model = await model_manager.get_model(model_id, **kwargs)
    else:
        selection_reason = f"default for type={default_type}"
        model = await model_manager.get_default_model(default_type, **kwargs)

    logger.debug(f"Using model: {model}")

    if model is None:
        logger.error(
            f"Model provisioning failed: No model found. "
            f"Selection reason: {selection_reason}. "
            f"model_id={model_id}, default_type={default_type}. "
            f"Please check Settings → Models and ensure a default model is configured for '{default_type}'."
        )
        raise ConfigurationError(
            f"No model configured for {selection_reason}. "
            f"Please go to Settings → Models and configure a default model for '{default_type}'."
        )

    if not isinstance(model, LanguageModel):
        logger.error(
            f"Model type mismatch: Expected LanguageModel but got {type(model).__name__}. "
            f"Selection reason: {selection_reason}. "
            f"model_id={model_id}, default_type={default_type}."
        )
        raise ConfigurationError(
            f"Model is not a LanguageModel: {model}. "
            f"Please check that the model configured for '{default_type}' is a language model, not an embedding or speech model."
        )

    return model.to_langchain()
