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

    def generate_structured(self, prompt, response_schema):
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
