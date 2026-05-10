import os
from typing import Any, ClassVar, Dict, Optional, Union

from esperanto import (
    AIFactory,
    EmbeddingModel,
    LanguageModel,
    SpeechToTextModel,
    TextToSpeechModel,
)
from loguru import logger

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.base import ObjectModel, RecordModel
from open_notebook.exceptions import ConfigurationError

ModelType = Union[LanguageModel, EmbeddingModel, SpeechToTextModel, TextToSpeechModel]


class Model(ObjectModel):
    table_name: ClassVar[str] = "model"
    nullable_fields: ClassVar[set[str]] = {"credential"}
    name: str
    provider: str
    type: str
    credential: Optional[str] = None

    @classmethod
    async def get_models_by_type(cls, model_type):
        models = await repo_query(
            "SELECT * FROM model WHERE type=$model_type;", {"model_type": model_type}
        )
        return [Model(**model) for model in models]

    @classmethod
    async def get_by_credential(cls, credential_id: str):
        """Get all models linked to a specific credential."""
        models = await repo_query(
            "SELECT * FROM model WHERE credential=$cred_id;",
            {"cred_id": ensure_record_id(credential_id)},
        )
        return [Model(**model) for model in models]

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = super()._prepare_save_data()
        if data.get("credential"):
            data["credential"] = ensure_record_id(data["credential"])
        return data

    async def get_credential_obj(self):
        """Get the Credential object linked to this model, if any."""
        if not self.credential:
            return None
        from open_notebook.domain.credential import Credential

        try:
            return await Credential.get(self.credential)
        except Exception:
            logger.warning(f"Could not load credential {self.credential} for model {self.id}")
            return None


class DefaultModels(RecordModel):
    record_id: ClassVar[str] = "open_notebook:default_models"
    default_chat_model: Optional[str] = None
    default_transformation_model: Optional[str] = None
    large_context_model: Optional[str] = None
    default_text_to_speech_model: Optional[str] = None
    default_speech_to_text_model: Optional[str] = None
    # default_vision_model: Optional[str]
    default_embedding_model: Optional[str] = None
    default_tools_model: Optional[str] = None

    @classmethod
    async def get_instance(cls) -> "DefaultModels":
        """Always fetch fresh defaults from database (override parent caching behavior)"""
        result = await repo_query(
            "SELECT * FROM ONLY $record_id",
            {"record_id": ensure_record_id(cls.record_id)},
        )

        if result:
            if isinstance(result, list) and len(result) > 0:
                data = result[0]
            elif isinstance(result, dict):
                data = result
            else:
                data = {}
        else:
            data = {}

        # Create new instance with fresh data (bypass singleton cache)
        instance = object.__new__(cls)
        object.__setattr__(instance, "__dict__", {})
        super(RecordModel, instance).__init__(**data)
        return instance


class ModelManager:
    def __init__(self):
        pass  # No caching needed

    def _infer_provider_from_model_name(self, model_name: str) -> Optional[str]:
        name = model_name.lower()
        if name.startswith("gemini"):
            return "google"
        if name.startswith("gpt") or name.startswith("o1") or name.startswith("o3") or name.startswith("o4"):
            return "openai"
        if name.startswith("claude"):
            return "anthropic"
        return None

    async def _get_env_model_by_name(self, model_name: str, model_type: str, **kwargs) -> Optional[ModelType]:
        provider = self._infer_provider_from_model_name(model_name)
        if not provider:
            return None

        from open_notebook.ai.key_provider import provision_provider_keys

        await provision_provider_keys(provider)
        config = dict(kwargs)
        if model_type == "language":
            return AIFactory.create_language(
                model_name=model_name,
                provider=provider,
                config=config,
            )
        if model_type == "embedding":
            return AIFactory.create_embedding(
                model_name=model_name,
                provider=provider,
                config=config,
            )
        return None

    async def get_model(self, model_id: str, **kwargs) -> Optional[ModelType]:
        """Get a model by ID. Esperanto will cache the actual model instance."""
        if not model_id:
            return None

        model: Optional[Model] = None

        if model_id.startswith("model:"):
            try:
                model = await Model.get(model_id)
            except Exception:
                raise ConfigurationError(f"Model with ID {model_id} not found in database")
        
        if not model:
            # Fall back to env var name if not a database model
            direct_model = await self._get_env_model_by_name(
                model_id, "language", **kwargs
            )
            if direct_model:
                return direct_model
            raise ConfigurationError(f"Model '{model_id}' not found in DB and could not be inferred from env")

        if not model.type or model.type not in [
            "language",
            "embedding",
            "speech_to_text",
            "text_to_speech",
        ]:
            raise ConfigurationError(f"Invalid model type: {model.type}")

        # Build config from credential if linked, otherwise fall back to env vars
        config: dict = {}
        if model.credential:
            credential = await model.get_credential_obj()
            if credential:
                config = credential.to_esperanto_config()
                logger.debug(
                    f"Using credential '{credential.name}' for model {model.name}"
                )
            else:
                logger.warning(
                    f"Model {model.id} has credential {model.credential} but it could not be loaded. "
                    f"Falling back to env vars."
                )
                # Fall back to env var provisioning
                from open_notebook.ai.key_provider import provision_provider_keys

                await provision_provider_keys(model.provider)
        else:
            # No credential linked - use env var fallback
            from open_notebook.ai.key_provider import provision_provider_keys

            await provision_provider_keys(model.provider)

        # Merge any additional kwargs (e.g. temperature)
        config.update(kwargs)

        # Normalize provider name: DB stores underscores but Esperanto expects hyphens
        provider = model.provider.replace("_", "-")

        # Create model based on type (Esperanto will cache the instance)
        if model.type == "language":
            return AIFactory.create_language(
                model_name=model.name,
                provider=provider,
                config=config,
            )
        elif model.type == "embedding":
            return AIFactory.create_embedding(
                model_name=model.name,
                provider=provider,
                config=config,
            )
        elif model.type == "speech_to_text":
            return AIFactory.create_speech_to_text(
                model_name=model.name,
                provider=provider,
                config=config,
            )
        elif model.type == "text_to_speech":
            return AIFactory.create_text_to_speech(
                model_name=model.name,
                provider=provider,
                config=config,
            )
        else:
            raise ConfigurationError(f"Invalid model type: {model.type}")

    async def get_defaults(self) -> DefaultModels:
        """Get the default models configuration from database"""
        defaults = await DefaultModels.get_instance()
        if not defaults:
            raise RuntimeError("Failed to load default models configuration")
        return defaults

    async def get_speech_to_text(self, **kwargs) -> Optional[SpeechToTextModel]:
        """Get the default speech-to-text model"""
        defaults = await self.get_defaults()
        model_id = defaults.default_speech_to_text_model
        if not model_id:
            return None
        model = await self.get_model(model_id, **kwargs)
        assert model is None or isinstance(model, SpeechToTextModel), (
            f"Expected SpeechToTextModel but got {type(model)}"
        )
        return model

    async def get_text_to_speech(self, **kwargs) -> Optional[TextToSpeechModel]:
        """Get the default text-to-speech model"""
        defaults = await self.get_defaults()
        model_id = defaults.default_text_to_speech_model
        if not model_id:
            return None
        model = await self.get_model(model_id, **kwargs)
        assert model is None or isinstance(model, TextToSpeechModel), (
            f"Expected TextToSpeechModel but got {type(model)}"
        )
        return model

    async def get_embedding_model(self, **kwargs) -> Optional[EmbeddingModel]:
        """Get the default embedding model"""
        defaults = await self.get_defaults()
        model_id = defaults.default_embedding_model
        if not model_id:
            return None
        model = await self.get_model(model_id, **kwargs)
        assert model is None or isinstance(model, EmbeddingModel), (
            f"Expected EmbeddingModel but got {type(model)}"
        )
        return model

    async def get_default_model(self, model_type: str, **kwargs) -> Optional[ModelType]:
        """
        Get the default model for a specific type.

        Args:
            model_type: The type of model to retrieve (e.g., 'chat', 'embedding', etc.)
            **kwargs: Additional arguments to pass to the model constructor
        """
        defaults = await self.get_defaults()
        model_id = None

        if model_type == "chat":
            model_id = os.getenv("DEFAULT_CHAT_MODEL") or defaults.default_chat_model
        elif model_type == "transformation":
            model_id = (
                os.getenv("DEFAULT_TRANSFORMATION_MODEL")
                or defaults.default_transformation_model
                or os.getenv("DEFAULT_CHAT_MODEL")
                or defaults.default_chat_model
            )
        elif model_type == "tools":
            model_id = (
                os.getenv("DEFAULT_TOOLS_MODEL")
                or defaults.default_tools_model
                or os.getenv("DEFAULT_CHAT_MODEL")
                or defaults.default_chat_model
            )
        elif model_type == "embedding":
            model_id = os.getenv("DEFAULT_EMBEDDING_MODEL") or defaults.default_embedding_model
        elif model_type == "text_to_speech":
            model_id = os.getenv("DEFAULT_TTS_MODEL") or defaults.default_text_to_speech_model
        elif model_type == "speech_to_text":
            model_id = os.getenv("DEFAULT_STT_MODEL") or defaults.default_speech_to_text_model
        elif model_type == "large_context":
            model_id = os.getenv("LARGE_CONTEXT_MODEL") or defaults.large_context_model

        if not model_id:
            logger.warning(
                f"No default model configured for type '{model_type}'. "
                f"Please go to Settings → Models and set a default model."
            )
            return None

        # Resolve model name to ID if needed (if it doesn't start with 'model:')
        if model_id and not model_id.startswith("model:"):
            try:
                # Look up model by name
                from open_notebook.database.repository import repo_query
                models = await repo_query(
                    "SELECT id FROM model WHERE string::lowercase(name) = $name LIMIT 1",
                    {"name": model_id.lower()}
                )
                if models:
                    model_id = models[0]["id"]
                else:
                    logger.warning(f"Could not resolve model name '{model_id}' from env var to a model ID")
            except Exception as e:
                logger.error(f"Error resolving model name '{model_id}': {e}")

        try:
            return await self.get_model(model_id, **kwargs)
        except (ValueError, ConfigurationError) as e:
            logger.error(
                f"Failed to load default model for type '{model_type}': {e}. "
                f"The configured model_id '{model_id}' may have been deleted or misconfigured. "
                f"Please go to Settings → Models and reconfigure the default model."
            )
            return None


model_manager = ModelManager()
