import json
import logging
import math
import re
import random
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import Settings
from app.errors import InvalidModelOutput, ProviderRateLimited, ProviderTimeout, ProviderUnavailable
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
        self._call_timeout = settings.provider_timeout_seconds
        self._total_timeout = settings.provider_total_timeout_seconds

    def generate_structured(
        self, prompt: str, response_schema: type[T], model: str | None = None
    ) -> tuple[T, int | None, int | None]:
        model = model or self.model_name
        deadline = time.monotonic() + self._total_timeout
        for attempt in range(self._retries + 1):
            # Never start a call that cannot finish inside the overall budget: the caller
            # (Node) gives up at its own timeout and would otherwise leave this call running.
            remaining = deadline - time.monotonic()
            if remaining < 2:
                logger.warning("Gemini call budget of %.0fs exhausted", self._total_timeout)
                raise ProviderTimeout()
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=gemini_schema(response_schema),
                        temperature=0.1,
                        http_options=types.HttpOptions(timeout=int(min(self._call_timeout, remaining) * 1000)),
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
                    raise rate_limit_error(exc, model) from exc
                if status and int(status) < 500:
                    logger.warning("Gemini rejected the request: %s", exc)
                    raise InvalidModelOutput() from exc
                if attempt >= self._retries:
                    logger.warning("Gemini provider failed after bounded retries: %s", exc)
                    raise ProviderUnavailable() from exc
                _backoff(attempt)
            except (InvalidModelOutput, ProviderRateLimited, ProviderTimeout):
                raise
            except Exception as exc:
                if attempt >= self._retries:
                    logger.warning("Gemini provider failed after bounded retries: %s", exc)
                    raise ProviderUnavailable() from exc
                _backoff(attempt)
        raise ProviderUnavailable()


def rate_limit_error(exc: errors.APIError, model: str) -> ProviderRateLimited:
    """Extract the quota scope and reset delay from a Gemini 429 response."""
    retry_after: int | None = None
    scope = "unknown"
    body = getattr(exc, "details", None)
    items = body.get("error", body).get("details", []) if isinstance(body, dict) else []
    for item in items:
        kind = str(item.get("@type", ""))
        if kind.endswith("RetryInfo"):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(item.get("retryDelay", "")))
            if match:
                retry_after = math.ceil(float(match.group(1)))
        elif kind.endswith("QuotaFailure"):
            quota_id = " ".join(str(v.get("quotaId", "")) for v in item.get("violations", []))
            scope = "daily" if "PerDay" in quota_id else "minute" if "PerMinute" in quota_id else scope
    return ProviderRateLimited(model=model, retry_after_seconds=retry_after, quota_scope=scope)


def _backoff(attempt: int) -> None:
    # Gemini 503 "high demand" spikes last seconds, so back off longer than sub-second, with jitter.
    time.sleep(min(1.0 * (2**attempt), 8.0) + random.uniform(0, 0.5))


# JSON Schema keywords the Gemini SDK's Schema type rejects. Strict validation still happens
# afterwards via parse_structured_output with the full Pydantic model.
_UNSUPPORTED_SCHEMA_KEYS = {"additionalProperties", "exclusiveMinimum", "exclusiveMaximum", "const"}


def gemini_schema(schema: type[BaseModel]) -> dict:
    root = schema.model_json_schema()
    defs = root.pop("$defs", {})

    def clean(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return clean(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {key: clean(value) for key, value in node.items() if key not in _UNSUPPORTED_SCHEMA_KEYS}
        if isinstance(node, list):
            return [clean(item) for item in node]
        return node

    return clean(root)


def schema_json(schema: type[BaseModel]) -> str:
    return json.dumps(schema.model_json_schema(), ensure_ascii=True)
