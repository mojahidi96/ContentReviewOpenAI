from openpyxl import Workbook

from app.config import get_settings
from app.llm.prompts import content_review_prompt
from app.schemas.content_review import ModelIssue, ModelReview, ReviewRequest
from app.services.content_review_service import ContentReviewService
from app.services.deprecated_terms import DeprecatedTerms


class FakeProvider:
    model_name = "fake"

    def __init__(self, issues=()):
        self.issues = list(issues)

    def generate_structured(self, prompt, response_schema, model=None):
        return ModelReview(issues=self.issues), None, None


def make_terms(tmp_path, rows, header=("Deprecated Term", "Replacement Term")):
    wb = Workbook()
    ws = wb.active
    if header:
        ws.append(list(header))
    for row in rows:
        ws.append(list(row))
    path = tmp_path / "terms.xlsx"
    wb.save(path)
    return DeprecatedTerms(path)


def test_shipped_excel_file_flags_customer_as_client():
    terms = DeprecatedTerms(get_settings().deprecated_terms_file)
    match = terms.find("Our customer called.")[0]
    assert (match.text, match.replacement, match.term) == ("customer", "client", "Customer")


def test_case_plural_and_word_boundaries(tmp_path):
    terms = make_terms(tmp_path, [("Customer", "Client")])
    found = {m.text: m.replacement for m in terms.find("Customer, customers, CUSTOMER and customerless.")}
    assert found == {"Customer": "Client", "customers": "clients", "CUSTOMER": "CLIENT"}


def test_longest_term_wins_and_multiword_whitespace(tmp_path):
    terms = make_terms(tmp_path, [("man", "person"), ("man hours", "person-hours")])
    matches = terms.find("Total man   hours.")
    assert [(m.text, m.replacement) for m in matches] == [("man   hours", "person-hours")]


def test_headerless_sheet_and_incomplete_rows_are_handled(tmp_path):
    terms = make_terms(tmp_path, [("Customer", "Client"), ("Orphan", None), (None, "x")], header=None)
    assert [m.replacement for m in terms.find("customer orphan")] == ["client"]


def test_file_changes_are_picked_up_and_missing_file_is_safe(tmp_path):
    import os

    terms = make_terms(tmp_path, [("Customer", "Client")])
    assert terms.find("buyer") == []
    wb = Workbook()
    wb.active.append(["Deprecated Term", "Replacement Term"])
    wb.active.append(["buyer", "purchaser"])
    wb.save(tmp_path / "terms.xlsx")
    os.utime(tmp_path / "terms.xlsx", (1, 9_999_999_999))
    assert terms.find("buyer")[0].replacement == "purchaser"
    assert DeprecatedTerms(tmp_path / "missing.xlsx").find("customer") == []


def test_service_adds_dictionary_issue_and_replaces_overlapping_model_issue(tmp_path):
    terms = make_terms(tmp_path, [("Customer", "Client")])
    content = "The customer asked ASAP."
    model_issues = [
        ModelIssue(issueType="deprecated_term", original="customer", improved="buyer",
                   suggestion="x", location={"prefix": "The ", "suffix": " asked"}),
        ModelIssue(issueType="clarity", original="ASAP", improved="as soon as possible (ASAP)",
                   suggestion="Spell out.", location={"prefix": "asked ", "suffix": "."}),
    ]
    service = ContentReviewService(FakeProvider(model_issues), 1000, deprecated_terms=terms)
    response = service.review(ReviewRequest(requestId="r", content=content))
    assert [(i.original, i.improved, i.issueType.value) for i in response.issues] == [
        ("customer", "client", "deprecated_term"),
        ("ASAP", "as soon as possible (ASAP)", "clarity"),
    ]
    assert response.issues[0].location.prefix == "The "
    assert "Customer" in response.issues[0].suggestion


def test_prompt_covers_acronyms_and_dictionary():
    prompt = content_review_prompt("x", "en")
    assert "FOMO" in prompt and "FIRST" in prompt and "full form" in prompt
    assert "dictionary check" in prompt
