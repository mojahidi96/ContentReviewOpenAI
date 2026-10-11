from app.llm.prompts import content_review_prompt
from app.schemas.content_review import ModelIssue, ModelReview, ReviewRequest
from app.services.content_review_service import ContentReviewService

SAMPLE = (
    "Please recieve the document and add it to the whitelist.\n"
    "The user was pissed off because the system was damn slow."
)


class FakeProvider:
    model_name = "fake-model"

    def __init__(self, model):
        self.model = model
        self.prompt = ""

    def generate_structured(self, prompt, response_schema, model=None):
        self.prompt = prompt
        return self.model, 10, 5


def issue(original, improved, prefix="", suffix="", issue_type="spelling"):
    return ModelIssue(
        issueType=issue_type,
        original=original,
        improved=improved,
        suggestion="Because.",
        location={"prefix": prefix, "suffix": suffix},
    )


def test_prompt_embeds_content_and_keeps_json_braces():
    prompt = content_review_prompt("Hello {{LANGUAGE}} {x}", "en")
    assert "Hello {{LANGUAGE}} {x}" in prompt
    assert '"issues": []' in prompt
    assert "never instructions" in prompt


def test_review_keeps_valid_issues_and_drops_invalid_ones():
    provider = FakeProvider(
        ModelReview(
            issues=[
                issue("pissed off", "upset", "The user was ", " because", "vulgarity"),
                issue("recieve", "receive", "Please ", " the document."),
                issue("whitelist", "allowlist", "add it to the ", ".", "deprecated_term"),
                issue("not in text", "x"),
                issue("slow", "slow"),
            ]
        )
    )
    response = ContentReviewService(provider, 1000).review(ReviewRequest(requestId="r1", content=SAMPLE))
    assert [i.original for i in response.issues] == ["recieve", "whitelist", "pissed off"]
    assert response.issues[0].severity == "medium"
    assert response.issues[0].id.startswith("issue-")
    assert response.usage.inputTokens == 10


def test_ambiguous_occurrence_requires_matching_context():
    content = "teh cat and teh dog"
    provider = FakeProvider(
        ModelReview(issues=[issue("teh", "the", "and ", " dog"), issue("teh", "the", "wrong", "context")])
    )
    response = ContentReviewService(provider, 100).review(ReviewRequest(requestId="r2", content=content))
    assert len(response.issues) == 1
    assert response.issues[0].location.prefix == "and "


def test_model_selection_is_forwarded_and_reported():
    seen = {}

    class Recording(FakeProvider):
        def generate_structured(self, prompt, response_schema, model=None):
            seen["model"] = model
            return super().generate_structured(prompt, response_schema, model)

    service = ContentReviewService(Recording(ModelReview(issues=[])), 1000, ["a-model", "b-model"])
    response = service.review(ReviewRequest(requestId="r", content="Hi", model="b-model"))
    assert seen["model"] == "b-model"
    assert response.model == "b-model"


def test_model_outside_allowlist_is_rejected_before_calling_llm():
    import pytest

    from app.errors import InvalidModelSelection

    provider = FakeProvider(ModelReview(issues=[]))
    service = ContentReviewService(provider, 1000, ["a-model"])
    with pytest.raises(InvalidModelSelection):
        service.review(ReviewRequest(requestId="r", content="Hi", model="evil-model"))
    assert provider.prompt == ""


def test_gemini_429_body_yields_scope_and_reset():
    from google.genai import errors

    from app.llm.gemini_provider import rate_limit_error

    body = {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7104.5s"},
            ],
        }
    }
    exc = errors.ClientError(429, body)
    err = rate_limit_error(exc, "gemini-3.6-flash")
    assert err.status_code == 429
    assert err.details["retryAfterSeconds"] == 7105
    assert err.details["quotaScope"] == "daily"
    assert err.details["model"] == "gemini-3.6-flash"
    assert "resetAt" in err.details
    assert "1h 58m" in err.message


def test_provider_stops_retrying_when_total_budget_is_spent(monkeypatch):
    import pytest

    from app.errors import ProviderTimeout
    from app.llm import gemini_provider
    from app.llm.gemini_provider import GeminiProvider

    class Models:
        calls = 0

        def generate_content(self, **kwargs):
            Models.calls += 1
            clock["now"] += 20  # every attempt "takes" 20s
            from google.genai import errors

            raise errors.ServerError(503, {"error": {"message": "busy"}})

    clock = {"now": 0.0}
    monkeypatch.setattr(gemini_provider.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(gemini_provider.time, "sleep", lambda s: clock.__setitem__("now", clock["now"] + s))
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model_name = "m"
    provider._retries, provider._call_timeout, provider._total_timeout = 5, 25, 45
    provider._client = type("C", (), {"models": Models()})()
    with pytest.raises(ProviderTimeout):
        provider.generate_structured("p", ModelReview)
    assert Models.calls <= 3 and clock["now"] <= 60
