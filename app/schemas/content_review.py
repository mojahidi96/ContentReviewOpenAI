from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


class ReviewCategory(StrEnum):
    GRAMMAR = "grammar"
    SPELLING = "spelling"
    PROFANITY = "profanity"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    content: Annotated[str, StringConstraints(min_length=1, max_length=100_000)]
    categories: Annotated[list[ReviewCategory], Field(min_length=1, max_length=3)]
    language: Annotated[str, StringConstraints(min_length=2, max_length=32)] = "en"


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findingId: str
    category: ReviewCategory
    severity: Severity
    originalText: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    suggestedText: Annotated[str, StringConstraints(max_length=2000)]
    explanation: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    startOffset: int = Field(ge=0)
    endOffset: int = Field(gt=0)


class Usage(BaseModel):
    inputTokens: int | None = None
    outputTokens: int | None = None


class ReviewResponse(BaseModel):
    requestId: str
    findings: list[Finding]
    model: str
    usage: Usage


class ModelFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ReviewCategory
    severity: Severity
    originalText: str
    suggestedText: str
    explanation: str
    startOffset: int = Field(ge=0)
    endOffset: int = Field(gt=0)


class ModelReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ModelFinding]


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    insufficientEvidence: bool = False


HistoryRole = Literal["user", "assistant"]
