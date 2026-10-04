import logging

from google import genai
from google.genai import errors, types

from app.config import Settings
from app.errors import ProviderRateLimited, ProviderUnavailable

logger = logging.getLogger(__name__)


class GeminiEmbeddings:
    def __init__(self, settings: Settings) -> None:
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required to initialize Gemini embeddings")
        self._client = genai.Client(
            api_key=settings.google_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=int(settings.provider_timeout_seconds * 1000)),
        )
        self._model = settings.gemini_embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            result = self._client.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            if not result.embeddings:
                raise ProviderUnavailable()
            return [item.values for item in result.embeddings]
        except errors.APIError as exc:
            if getattr(exc, "code", None) == 429:
                raise ProviderRateLimited() from exc
            logger.warning("Gemini embedding request failed")
            raise ProviderUnavailable() from exc

    def embed_query(self, text: str) -> list[float]:
        try:
            result = self._client.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
            )
            if not result.embeddings:
                raise ProviderUnavailable()
            return result.embeddings[0].values
        except errors.APIError as exc:
            if getattr(exc, "code", None) == 429:
                raise ProviderRateLimited() from exc
            logger.warning("Gemini query embedding request failed")
            raise ProviderUnavailable() from exc
