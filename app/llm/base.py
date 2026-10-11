from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    model_name: str

    def generate_structured(
        self, prompt: str, response_schema: type[T], model: str | None = None
    ) -> tuple[T, int | None, int | None]: ...
