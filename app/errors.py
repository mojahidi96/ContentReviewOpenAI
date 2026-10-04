from dataclasses import dataclass


@dataclass
class ServiceError(Exception):
    code: str
    message: str
    status_code: int = 500


class ProviderUnavailable(ServiceError):
    def __init__(self) -> None:
        super().__init__("LLM_PROVIDER_UNAVAILABLE", "The AI service is temporarily unavailable.", 503)


class ProviderRateLimited(ServiceError):
    def __init__(self) -> None:
        super().__init__("LLM_QUOTA_EXHAUSTED", "The AI provider is temporarily rate limited.", 429)


class InvalidModelOutput(ServiceError):
    def __init__(self) -> None:
        super().__init__("INVALID_MODEL_OUTPUT", "The AI provider returned an unusable response.", 502)


class VectorStoreUnavailable(ServiceError):
    def __init__(self) -> None:
        super().__init__("VECTOR_STORE_UNAVAILABLE", "Document storage is temporarily unavailable.", 503)
