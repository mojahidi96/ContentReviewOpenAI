import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.errors import InvalidModelOutput

T = TypeVar("T", bound=BaseModel)


def parse_structured_output(text: str, schema: type[T]) -> T:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    try:
        data = json.loads(candidate)
        return schema.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise InvalidModelOutput() from exc
