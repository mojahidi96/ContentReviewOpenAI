from uuid import uuid4

from app.errors import InvalidModelOutput, ServiceError
from app.llm.base import LLMProvider
from app.llm.prompts import content_review_prompt
from app.schemas.content_review import (
    Issue,
    IssueLocation,
    ModelIssue,
    ModelReview,
    ReviewRequest,
    ReviewResponse,
    Usage,
)

MAX_ISSUES = 500


def _occurrences(content: str, text: str) -> list[int]:
    positions: list[int] = []
    start = content.find(text)
    while start != -1:
        positions.append(start)
        start = content.find(text, start + 1)
    return positions


def locate_issue(content: str, issue: ModelIssue) -> int | None:
    """Return the start index of the issue's original text, or None if it cannot be placed."""
    positions = _occurrences(content, issue.original)
    if not positions:
        return None
    prefix, suffix = issue.location.prefix, issue.location.suffix
    exact = [
        pos
        for pos in positions
        if content[:pos].endswith(prefix) and content[pos + len(issue.original) :].startswith(suffix)
    ]
    if exact:
        return exact[0]
    # The model may have trimmed or slightly altered context; accept only an unambiguous match.
    return positions[0] if len(positions) == 1 else None


class ContentReviewService:
    def __init__(self, provider: LLMProvider, max_chars: int) -> None:
        self._provider = provider
        self._max_chars = max_chars

    def review(self, request: ReviewRequest) -> ReviewResponse:
        if len(request.content) > self._max_chars:
            raise ServiceError("CONTENT_TOO_LARGE", "Review content exceeds the configured limit.", 413)
        result, input_tokens, output_tokens = self._provider.generate_structured(
            content_review_prompt(request.content, request.language), ModelReview
        )
        return ReviewResponse(
            requestId=request.requestId,
            issues=self._validated_issues(result, request),
            model=self._provider.model_name,
            usage=Usage(inputTokens=input_tokens, outputTokens=output_tokens),
        )

    @staticmethod
    def _validated_issues(result: ModelReview, request: ReviewRequest) -> list[Issue]:
        issues: list[tuple[int, Issue]] = []
        seen: set[tuple[int, str]] = set()
        for candidate in result.issues:
            if not candidate.original or candidate.improved == candidate.original:
                continue
            start = locate_issue(request.content, candidate)
            if start is None or (start, candidate.original) in seen:
                continue
            seen.add((start, candidate.original))
            issues.append(
                (
                    start,
                    Issue(
                        id=f"issue-{uuid4().hex[:12]}",
                        issueType=candidate.issueType,
                        severity=candidate.severity,
                        original=candidate.original,
                        improved=candidate.improved,
                        suggestion=candidate.suggestion,
                        location=IssueLocation(prefix=candidate.location.prefix, suffix=candidate.location.suffix),
                    ),
                )
            )
        if len(issues) > MAX_ISSUES:
            raise InvalidModelOutput()
        issues.sort(key=lambda pair: pair[0])
        return [issue for _, issue in issues]
