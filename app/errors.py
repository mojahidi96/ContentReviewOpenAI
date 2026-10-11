from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def quota_scope_label(scope: str) -> str:
    return {"daily": "daily", "minute": "per-minute"}.get(scope, "request")


def format_duration(seconds: int) -> str:
    hours, rest = divmod(max(seconds, 0), 3600)
    minutes = rest // 60
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{max(seconds, 1)}s"


@dataclass
class ServiceError(Exception):
    code: str
    message: str
    status_code: int = 500
    details: dict | None = None


class ProviderUnavailable(ServiceError):
    def __init__(self) -> None:
        super().__init__("LLM_PROVIDER_UNAVAILABLE", "The AI service is temporarily unavailable.", 503)


class ProviderRateLimited(ServiceError):
    def __init__(
        self,
        model: str | None = None,
        retry_after_seconds: int | None = None,
        quota_scope: str = "unknown",
    ) -> None:
        details: dict = {"model": model, "quotaScope": quota_scope}
        message = "The AI provider is temporarily rate limited."
        if model:
            message = f"The {quota_scope_label(quota_scope)} quota for model {model} is exhausted."
        if retry_after_seconds is not None:
            reset_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after_seconds)
            details["retryAfterSeconds"] = retry_after_seconds
            details["resetAt"] = reset_at.isoformat(timespec="seconds")
            message += f" It resets in about {format_duration(retry_after_seconds)}."
        message += " Try again later or choose a different model."
        super().__init__("LLM_QUOTA_EXHAUSTED", message, 429, details)


class InvalidModelSelection(ServiceError):
    def __init__(self, model: str, allowed: list[str]) -> None:
        super().__init__(
            "MODEL_NOT_ALLOWED",
            f"Model {model} is not available. Choose one of: {', '.join(allowed)}.",
            422,
            {"model": model, "allowedModels": allowed},
        )


class ProviderTimeout(ServiceError):
    def __init__(self) -> None:
        super().__init__(
            "LLM_PROVIDER_TIMEOUT",
            "The AI provider took too long to respond. Try again or choose a different model.",
            504,
        )


class InvalidModelOutput(ServiceError):
    def __init__(self) -> None:
        super().__init__("INVALID_MODEL_OUTPUT", "The AI provider returned an unusable response.", 502)


class VectorStoreUnavailable(ServiceError):
    def __init__(self) -> None:
        super().__init__("VECTOR_STORE_UNAVAILABLE", "Document storage is temporarily unavailable.", 503)
