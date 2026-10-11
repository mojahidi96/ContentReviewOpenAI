import logging
from uuid import uuid4

from app.errors import InvalidModelOutput, InvalidModelSelection, ServiceError
from app.llm.base import LLMProvider
from app.services.deprecated_terms import DeprecatedTerms
from app.llm.prompts import content_review_prompt
from app.schemas.content_review import (
    Issue,
    IssueLocation,
    IssueType,
    ModelIssue,
    ModelReview,
    ReviewRequest,
    ReviewResponse,
    Severity,
    Usage,
)

logger = logging.getLogger(__name__)
MAX_ISSUES = 500
CONTEXT_CHARS = 30


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
    def __init__(
        self,
        provider: LLMProvider,
        max_chars: int,
        allowed_models: list[str] | None = None,
        deprecated_terms: DeprecatedTerms | None = None,
    ) -> None:
        self._deprecated_terms = deprecated_terms
        self._provider = provider
        self._max_chars = max_chars
        self._allowed_models = allowed_models

    def review(self, request: ReviewRequest) -> ReviewResponse:
        if len(request.content) > self._max_chars:
            raise ServiceError("CONTENT_TOO_LARGE", "Review content exceeds the configured limit.", 413)
        model = request.model
        if model and self._allowed_models is not None and model not in self._allowed_models:
            raise InvalidModelSelection(model, self._allowed_models)
        result, input_tokens, output_tokens = self._provider.generate_structured(
            content_review_prompt(request.content, request.language), ModelReview, model
        )
        located = self._validated_issues(result, request)
        model_issue_count = len(located)
        located = self._merge_dictionary_issues(located, request.content)
        issues = [issue for _, issue in located]
        logger.info(
            "Review %s: model returned %d issues, %d kept after validation, %d total with dictionary",
            request.requestId,
            len(result.issues),
            model_issue_count,
            len(issues),
        )
        return ReviewResponse(
            requestId=request.requestId,
            issues=issues,
            model=model or self._provider.model_name,
            usage=Usage(inputTokens=input_tokens, outputTokens=output_tokens),
        )

    def _merge_dictionary_issues(
        self, located: list[tuple[int, Issue]], content: str
    ) -> list[tuple[int, Issue]]:
        """Add deprecated-term issues from the Excel dictionary; they replace overlapping model issues."""
        if self._deprecated_terms is None:
            return located
        matches = self._deprecated_terms.find(content)
        if not matches:
            return located
        spans = [(m.start, m.end) for m in matches]

        def overlaps(start: int, original: str) -> bool:
            end = start + len(original)
            return any(start < s_end and s_start < end for s_start, s_end in spans)

        kept = [(start, issue) for start, issue in located if not overlaps(start, issue.original)]
        for m in matches:
            kept.append(
                (
                    m.start,
                    Issue(
                        id=f"issue-{uuid4().hex[:12]}",
                        issueType=IssueType.DEPRECATED_TERM,
                        severity=Severity.MEDIUM,
                        original=m.text,
                        improved=m.replacement,
                        suggestion=f'"{m.term}" is a deprecated term. Use "{m.replacement}" instead.',
                        location=IssueLocation(
                            prefix=content[max(0, m.start - CONTEXT_CHARS) : m.start],
                            suffix=content[m.end : m.end + CONTEXT_CHARS],
                        ),
                    ),
                )
            )
        kept.sort(key=lambda pair: pair[0])
        return kept

    @staticmethod
    def _validated_issues(result: ModelReview, request: ReviewRequest) -> list[tuple[int, Issue]]:
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
                        suggestion=candidate.suggestion.strip() or "Review this text.",
                        location=IssueLocation(prefix=candidate.location.prefix, suffix=candidate.location.suffix),
                    ),
                )
            )
        if len(issues) > MAX_ISSUES:
            raise InvalidModelOutput()
        issues.sort(key=lambda pair: pair[0])
        return issues
