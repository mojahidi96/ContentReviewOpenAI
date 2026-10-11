"""Shared helpers for the content-review sample cases (used by pytest and scripts/run_live_cases.py)."""

import json
from pathlib import Path

CASES_FILE = Path(__file__).with_name("content_review_cases.json")
VALID_TYPES = {
    "spelling", "grammar", "typo", "punctuation", "clarity",
    "slang", "vulgarity", "deprecated_term", "inappropriate_language",
}


def load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def evaluate_case(case: dict, issues: list[tuple[str, str, str]]) -> list[str]:
    """Return failure messages (empty = pass). issues are (original, improved, issueType) in document order."""
    failures: list[str] = []
    originals = [original for original, _, _ in issues]
    used: set[int] = set()
    for want in case.get("expect", []):
        candidates = as_list(want["original"])
        types = set(as_list(want.get("types", [])))
        hit = next(
            (
                index
                for index, (original, improved, issue_type) in enumerate(issues)
                if index not in used
                and original in candidates
                and (not types or issue_type in types)
                and ("improved" not in want or improved == want["improved"])
            ),
            None,
        )
        if hit is None:
            failures.append(f"missing issue {candidates} types={sorted(types)} improved={want.get('improved')!r}")
        else:
            used.add(hit)
    for wanted_types in case.get("expect_types", []):
        options = set(as_list(wanted_types))
        if not any(issue_type in options for _, _, issue_type in issues):
            failures.append(f"no issue of type {sorted(options)}")
    for forbidden in case.get("forbid", []):
        bad = [original for original in originals if forbidden in original]
        if bad:
            failures.append(f"must not flag {forbidden!r} but flagged {bad}")
    for original, limit in case.get("max_per_original", {}).items():
        count = originals.count(original)
        if count > limit:
            failures.append(f"{original!r} flagged {count} times (max {limit})")
    if "exact_count" in case and len(issues) != case["exact_count"]:
        failures.append(f"expected exactly {case['exact_count']} issues, got {len(issues)}: {originals}")
    if "min_issues" in case and len(issues) < case["min_issues"]:
        failures.append(f"expected at least {case['min_issues']} issues, got {len(issues)}")
    return failures
