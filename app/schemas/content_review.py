from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


class IssueType(StrEnum):
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    TYPO = "typo"
    PUNCTUATION = "punctuation"
    CLARITY = "clarity"
    SLANG = "slang"
    VULGARITY = "vulgarity"
    DEPRECATED_TERM = "deprecated_term"
    INAPPROPRIATE_LANGUAGE = "inappropriate_language"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    content: Annotated[str, StringConstraints(min_length=1, max_length=100_000)]
    language: Annotated[str, StringConstraints(min_length=2, max_length=32)] = "en"
    model: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None


class ModelListResponse(BaseModel):
    defaultModel: str
    models: list[str]


class IssueLocation(BaseModel):
    prefix: str = ""
    suffix: str = ""


class Issue(BaseModel):
    id: str
    issueType: IssueType
    severity: Severity
    original: str
    improved: str
    suggestion: str
    location: IssueLocation


class Usage(BaseModel):
    inputTokens: int | None = None
    outputTokens: int | None = None


class ReviewResponse(BaseModel):
    requestId: str
    issues: list[Issue]
    model: str
    usage: Usage


class ModelIssue(BaseModel):
    issueType: IssueType
    severity: Severity = Severity.MEDIUM
    original: str
    improved: str
    suggestion: str = ""
    location: IssueLocation = IssueLocation()


class ModelReview(BaseModel):
    issues: list[ModelIssue]


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    insufficientEvidence: bool = False


HistoryRole = Literal["user", "assistant"]
