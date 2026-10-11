"""Offline checks for tests/cases/content_review_cases.json. Never calls Gemini."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cases"))
import support  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.schemas.content_review import ModelIssue, ModelReview, ReviewRequest  # noqa: E402
from app.services.content_review_service import ContentReviewService  # noqa: E402
from app.services.deprecated_terms import DeprecatedTerms  # noqa: E402

CASES = support.load_cases()
CONTEXT = 20


class FakeProvider:
    model_name = "fake"

    def __init__(self, issues):
        self._issues = issues

    def generate_structured(self, prompt, response_schema, model=None):
        return ModelReview(issues=self._issues), None, None


def replay_model_issues(case) -> list[ModelIssue]:
    """Build what a perfect model would return for the case's expect list, with real contexts."""
    content, seen, issues = case["content"], {}, []
    for want in case.get("expect", []):
        original = support.as_list(want["original"])[0]
        nth = seen.get(original, 0)
        seen[original] = nth + 1
        pos = -1
        for _ in range(nth + 1):
            pos = content.index(original, pos + 1)
        types = support.as_list(want.get("types", ["spelling"]))
        issues.append(
            ModelIssue(
                issueType=types[0],
                original=original,
                improved=want.get("improved", original + "-fixed"),
                suggestion="Because.",
                location={
                    "prefix": content[max(0, pos - CONTEXT) : pos],
                    "suffix": content[pos + len(original) : pos + len(original) + CONTEXT],
                },
            )
        )
    return issues


def service(issues) -> ContentReviewService:
    terms = DeprecatedTerms(get_settings().deprecated_terms_file)
    return ContentReviewService(FakeProvider(issues), 100_000, deprecated_terms=terms)


def run(case, issues):
    response = service(issues).review(ReviewRequest(requestId=case["id"], content=case["content"]))
    return response.issues


def test_case_ids_are_unique_and_cover_every_group():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    assert {case["group"] for case in CASES} == {"A", "B", "C", "D"}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_definition_is_well_formed(case):
    assert case["content"].strip() and case["scenario"]
    for want in case.get("expect", []):
        assert any(o in case["content"] for o in support.as_list(want["original"])), want
        assert set(support.as_list(want.get("types", []))) <= support.VALID_TYPES
    for wanted in case.get("expect_types", []):
        assert set(support.as_list(wanted)) <= support.VALID_TYPES
    assert case.get("exact_count", 0) >= 0
    # Acronyms are flagged once per document, so batched groups must not repeat one across cases.
    assert case["group"] in "ABCD"


@pytest.mark.parametrize("case", [c for c in CASES if c.get("source") == "dictionary"], ids=lambda c: c["id"])
def test_dictionary_cases_pass_with_no_model_help(case):
    issues = run(case, [])
    triples = [(i.original, i.improved, i.issueType.value) for i in issues]
    assert support.evaluate_case(case, triples) == []


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.get("expect") and c.get("source") != "dictionary"], ids=lambda c: c["id"]
)
def test_model_cases_replay_with_correct_order_and_locations(case):
    issues = run(case, replay_model_issues(case))
    triples = [(i.original, i.improved, i.issueType.value) for i in issues]
    replayable = {k: case[k] for k in ("expect", "forbid", "max_per_original") if k in case}
    assert support.evaluate_case(replayable, triples) == []
    assert len(issues) == len(case["expect"])
    positions = [case["content"].index(i.original) for i in issues]
    assert positions == sorted(positions) or len({i.original for i in issues}) < len(issues)


def test_repeated_mistake_keeps_three_distinct_locations():
    case = next(c for c in CASES if c["id"] == "C7-repeated")
    issues = run(case, replay_model_issues(case))
    assert len(issues) == 3
    assert len({(i.location.prefix, i.location.suffix) for i in issues}) == 3


def test_boundary_issues_have_empty_prefix_or_suffix():
    case = next(c for c in CASES if c["id"] == "C8-boundaries")
    first, last = run(case, replay_model_issues(case))
    assert first.location.prefix == "" and last.location.suffix == ""


def test_evaluator_reports_failures():
    case = {"expect": [{"original": "teh", "types": ["typo"]}], "forbid": ["ROI"], "exact_count": 0, "max_per_original": {"x": 0}}
    failures = support.evaluate_case(case, [("ROI", "r", "clarity"), ("x", "y", "typo")])
    assert len(failures) == 4
