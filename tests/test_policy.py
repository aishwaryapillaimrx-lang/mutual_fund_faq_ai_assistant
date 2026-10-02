"""Phase 1 policy tests: PII, intent, scheme aliases, catalog hosts."""

from __future__ import annotations

import pytest

from app.catalog import (
    FLEXI_CAP_SCHEME_ID,
    LARGE_CAP_SCHEME_ID,
    ELSS_SCHEME_ID,
    SMALL_CAP_SCHEME_ID,
    SCHEMES,
)
from app.policy import analyze_question
from app.policy.intent import classify_intent
from app.policy.pii import contains_pii
from app.policy.scheme_resolver import resolve_scheme


def test_catalog_has_exactly_five_schemes() -> None:
    assert len(SCHEMES) == 5
    ids = {scheme.scheme_id for scheme in SCHEMES}
    assert len(ids) == 5


def test_catalog_has_no_groww_urls() -> None:
    for scheme in SCHEMES:
        assert "groww" not in scheme.factsheet_url.lower()
        assert "groww.in" not in scheme.factsheet_url.lower()


@pytest.mark.parametrize(
    "text",
    [
        "ABCDE1234F",
        "My PAN is ABCDE1234F",
        "aadhaar 2345 6789 0123",
        "email me at user@example.com",
        "call 9876543210",
        "+91 9876543210",
        "otp is 482193",
        "account 123456789012",
    ],
)
def test_contains_pii(text: str) -> None:
    assert contains_pii(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "expense ratio HDFC Large Cap",
        "ELSS lock-in",
        "best 5-year return",
        "minimum SIP",
    ],
)
def test_no_pii_on_normal_questions(text: str) -> None:
    assert contains_pii(text) is False


def test_analyze_fake_pan_is_pii_and_skips_intent() -> None:
    result = analyze_question("ABCDE1234F")
    assert result.contains_pii is True
    assert result.intent is None
    assert result.scheme_id is None
    assert result.clarify is False


def test_should_i_buy_is_advice() -> None:
    question = "Should I buy HDFC Small Cap?"
    assert classify_intent(question) == "advice"
    result = analyze_question(question)
    assert result.contains_pii is False
    assert result.intent == "advice"
    assert result.scheme_id == SMALL_CAP_SCHEME_ID


def test_best_five_year_return_is_performance() -> None:
    question = "best 5-year return"
    assert classify_intent(question) == "performance"
    result = analyze_question(question)
    assert result.intent == "performance"


def test_expense_ratio_large_cap_is_factual() -> None:
    question = "expense ratio HDFC Large Cap"
    assert classify_intent(question) == "factual"
    scheme_id, clarify = resolve_scheme(question)
    assert scheme_id == LARGE_CAP_SCHEME_ID
    assert clarify is False
    result = analyze_question(question)
    assert result.intent == "factual"
    assert result.scheme_id == LARGE_CAP_SCHEME_ID


def test_sbi_bluechip_is_out_of_scope() -> None:
    question = "SBI Bluechip expense ratio"
    assert classify_intent(question) == "out_of_scope"
    result = analyze_question(question)
    assert result.intent == "out_of_scope"
    assert result.scheme_id is None


def test_elss_lock_in_resolves_elss() -> None:
    question = "ELSS lock-in"
    assert classify_intent(question) == "factual"
    scheme_id, clarify = resolve_scheme(question)
    assert scheme_id == ELSS_SCHEME_ID
    assert clarify is False


def test_hdfc_equity_fund_is_flexi_cap() -> None:
    question = "HDFC Equity Fund exit load"
    assert classify_intent(question) == "factual"
    scheme_id, clarify = resolve_scheme(question)
    assert scheme_id == FLEXI_CAP_SCHEME_ID
    assert clarify is False
    result = analyze_question(question)
    assert result.scheme_id == FLEXI_CAP_SCHEME_ID


def test_two_schemes_need_clarify() -> None:
    question = "expense ratio of HDFC Large Cap and HDFC Small Cap"
    scheme_id, clarify = resolve_scheme(question)
    assert scheme_id is None
    assert clarify is True
    result = analyze_question(question)
    assert result.clarify is True
    assert result.scheme_id is None
    assert result.intent == "factual"


def test_unknown_scheme_stays_factual_with_no_id() -> None:
    question = "What is the expense ratio?"
    scheme_id, clarify = resolve_scheme(question)
    assert scheme_id is None
    assert clarify is False
    result = analyze_question(question)
    assert result.intent == "factual"
    assert result.scheme_id is None
