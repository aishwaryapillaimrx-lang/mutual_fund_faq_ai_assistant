"""Integration eval (PRD §11). Skipped without a built index and ANTHROPIC_API_KEY."""

from __future__ import annotations

import pytest

from app import config
from tests.gold_eval import load_gold, run_gold, score_item

pytestmark = pytest.mark.integration


def test_gold_file_is_well_formed() -> None:
    items = load_gold()
    assert len(items) == 10
    assert len({i["id"] for i in items}) == 10
    for item in items:
        assert item["expect_type"] in {"factual", "not_found", "refusal"}
        assert item["source_host_allowlist"]


def test_scorer_flags_problems() -> None:
    item = {"expect_type": "not_found", "source_host_allowlist": ["hdfcfund.com"]}
    bad = {"type": "factual", "answer": "It is 1.2%.", "source_url": "https://groww.in/x", "last_updated": ""}
    problems = score_item(item, bad)
    assert len(problems) >= 3


def test_gold_set_accuracy() -> None:
    if not config.ANTHROPIC_API_KEY or not (config.INDEX_DIR / "chroma.sqlite3").exists():
        pytest.skip("needs ANTHROPIC_API_KEY and a built index")
    rows = run_gold()
    failures = {i["id"]: p for i, _, p in rows if p}
    assert len(rows) - len(failures) >= 8, failures
    # Hard rules regardless of the 80% bar.
    for item, response, _ in rows:
        assert response["source_url"] and response["last_updated"], item["id"]
        if item["expect_type"] == "not_found":
            assert response["type"] == "not_found", f"invented answer for {item['id']}"
