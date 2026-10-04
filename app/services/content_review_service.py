from uuid import uuid4

from app.errors import InvalidModelOutput
from app.llm.base import LLMProvider
from app.llm.prompts import content_review_prompt
from app.schemas.content_review import (
    Finding,
    ModelReview,
    ReviewCategory,
    ReviewRequest,
    ReviewResponse,
    Usage,
)


def utf16_slice(content: str, start: int, end: int) -> str | None:
    encoded = content.encode("utf-16-le")
    if start < 0 or end <= start or end * 2 > len(encoded):
        return None
    try:
        return encoded[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        return None


class ContentReviewService:
    def __init__(self, provider: LLMProvider, max_chars: int) -> None:
        self._provider = provider
        self._max_chars = max_chars

    def review(self, request: ReviewRequest) -> ReviewResponse:
        if len(request.content) > self._max_chars:
            from app.errors import ServiceError

            raise ServiceError("CONTENT_TOO_LARGE", "Review content exceeds the configured limit.", 413)
        result, input_tokens, output_tokens = self._provider.generate_structured(
            content_review_prompt(request.content, request.categories, request.language), ModelReview
        )
        findings = self._validated_findings(result, request)
        return ReviewResponse(
            requestId=request.requestId,
            findings=findings,
            model=self._provider.model_name,
            usage=Usage(inputTokens=input_tokens, outputTokens=output_tokens),
        )

    @staticmethod
    def _validated_findings(result: ModelReview, request: ReviewRequest) -> list[Finding]:
        findings: list[Finding] = []
        ranges: list[tuple[int, int]] = []
        for candidate in result.findings:
            if candidate.category not in request.categories:
                continue
            matched = utf16_slice(request.content, candidate.startOffset, candidate.endOffset)
            if matched != candidate.originalText:
                continue
            if any(candidate.startOffset < end and candidate.endOffset > start for start, end in ranges):
                continue
            if candidate.suggestedText == candidate.originalText:
                continue
            findings.append(
                Finding(
                    findingId=f"finding_{uuid4().hex[:12]}",
                    category=candidate.category,
                    severity=candidate.severity,
                    originalText=candidate.originalText,
                    suggestedText=candidate.suggestedText,
                    explanation=candidate.explanation,
                    startOffset=candidate.startOffset,
                    endOffset=candidate.endOffset,
                )
            )
            ranges.append((candidate.startOffset, candidate.endOffset))
        if len(findings) > 500:
            raise InvalidModelOutput()
        return findings
