import json
import logging
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import Settings
from app.errors import InvalidModelOutput, ProviderRateLimited, ProviderUnavailable
from app.llm.structured_output import parse_structured_output

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required to initialize Gemini")
        self.model_name = settings.gemini_model
        self._client = genai.Client(
            api_key=settings.google_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=int(settings.provider_timeout_seconds * 1000)),
        )
        self._retries = settings.provider_max_retries

    def generate_structured(self, prompt: str, response_schema: type[T]) -> tuple[T, int | None, int | None]:
        for attempt in range(self._retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_schema,
                        temperature=0.1,
                    ),
                )
                if not response.text:
                    raise InvalidModelOutput()
                parsed = parse_structured_output(response.text, response_schema)
                usage = response.usage_metadata
                return (
                    parsed,
                    getattr(usage, "prompt_token_count", None),
                    getattr(usage, "candidates_token_count", None),
                )
            except errors.APIError as exc:
                status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                if status == 429:
                    raise ProviderRateLimited() from exc
                if status and int(status) < 500:
                    raise InvalidModelOutput() from exc
                if attempt >= self._retries:
                    logger.warning("Gemini provider failed after bounded retries")
                    raise ProviderUnavailable() from exc
                time.sleep(min(0.25 * (2**attempt), 1.0))
            except (InvalidModelOutput, ProviderRateLimited):
                raise
            except Exception as exc:
                if attempt >= self._retries:
                    logger.warning("Gemini provider failed after bounded retries")
                    raise ProviderUnavailable() from exc
                time.sleep(min(0.25 * (2**attempt), 1.0))
        raise ProviderUnavailable()


def schema_json(schema: type[BaseModel]) -> str:
    return json.dumps(schema.model_json_schema(), ensure_ascii=True)
