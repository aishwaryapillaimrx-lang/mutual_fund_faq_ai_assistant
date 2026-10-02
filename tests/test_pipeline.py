from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config, pipeline
from app.catalog import LARGE_CAP_SCHEME_ID, get_scheme
from app.config import INDEX_DIR
from app.main import app
from app.pipeline import answer_question
from app.rag.format import format_answer
from app.rag.generate import GenerationError
from app.rag.prompt import NOT_IN_SOURCES
from app.rag.cite import pick_source_url
from app.rag.retrieve import RetrievedChunk

client = TestClient(app)


def test_health_and_home() -> None:
    assert client.get("/health").json() == {"ok": True}
    home = client.get("/")
    assert home.status_code == 200
    html = home.text
    assert "Facts-only. No investment advice." in html
    assert "Ask factual questions about five HDFC mutual fund schemes." in html
    assert "What is the expense ratio of HDFC Large Cap Fund Direct Growth?" in html
    assert "What is the lock-in for HDFC ELSS Tax Saver?" in html
    assert "How do I download a capital-gains statement?" in html


def test_pii_does_not_echo_identifier() -> None:
    pan = "ABCDE1234F"
    data = answer_question(f"My PAN is {pan}, expense ratio?")
    assert data["type"] == "pii"
    assert pan not in data["answer"]
    assert data["source_url"].startswith("https://")
    assert data["last_updated"]
    assert data["scheme_id"] is None


def test_advice_refusal() -> None:
    data = answer_question("Should I invest?")
    assert data["type"] == "refusal"
    assert "advice" in data["answer"].lower() or "buy/sell" in data["answer"].lower()
    assert "amfiindia.com" in data["source_url"] or "sebi" in data["source_url"]


def _chunk(score: float, url: str = "https://files.hdfcfund.com/x.pdf") -> RetrievedChunk:
    return RetrievedChunk(
        text="Exit load is nil. Second sentence. Third sentence.",
        score=score,
        scheme_id=LARGE_CAP_SCHEME_ID,
        doc_type="kim",
        source_url=url,
        snapshot_date="2026-09-27",
    )


def test_factual_gate_pass_returns_one_cited_answer(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [_chunk(0.8)])
    monkeypatch.setattr(
        pipeline,
        "generate_answer",
        lambda q, c: "Exit load is nil. One. Two. Three. See https://evil.example/x",
    )
    data = answer_question("What is the exit load of HDFC Large Cap Fund?")
    assert data["type"] == "factual"
    assert data["answer"] == "Exit load is nil. One. Two."
    assert data["source_url"] == "https://files.hdfcfund.com/x.pdf"
    assert data["scheme_id"] == LARGE_CAP_SCHEME_ID


def test_factual_low_score_is_not_found_with_fallback(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [_chunk(0.05)])
    data = answer_question("What is the expense ratio of HDFC Large Cap Fund?")
    assert data["type"] == "not_found"
    assert data["source_url"] == get_scheme(LARGE_CAP_SCHEME_ID).factsheet_url
    assert data["last_updated"]


def test_factual_empty_index_is_not_found(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [])
    data = answer_question("What is the expense ratio of HDFC Large Cap Fund?")
    assert data["type"] == "not_found"
    assert "groww" not in data["source_url"].lower()


def test_model_says_not_in_sources_is_not_found(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [_chunk(0.8)])
    monkeypatch.setattr(pipeline, "generate_answer", lambda q, c: NOT_IN_SOURCES)
    data = answer_question("What is the expense ratio of HDFC Large Cap Fund?")
    assert data["type"] == "not_found"
    assert data["source_url"] == get_scheme(LARGE_CAP_SCHEME_ID).factsheet_url


def test_llm_failure_returns_busy_with_fallback(monkeypatch) -> None:
    def boom(q, c):
        raise GenerationError("timeout")

    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [_chunk(0.8)])
    monkeypatch.setattr(pipeline, "generate_answer", boom)
    data = answer_question("What is the exit load of HDFC Large Cap Fund?")
    assert data["type"] == "not_found"
    assert "busy" in data["answer"].lower()
    assert data["source_url"] and data["last_updated"]


def test_llm_not_called_when_gate_fails(monkeypatch) -> None:
    def fail(q, c):
        raise AssertionError("LLM must not be called")

    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [_chunk(0.05)])
    monkeypatch.setattr(pipeline, "generate_answer", fail)
    assert answer_question("exit load of HDFC Large Cap?")["type"] == "not_found"


def test_missing_api_key_is_busy_not_crash(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [_chunk(0.8)])
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    assert answer_question("exit load of HDFC Large Cap?")["type"] == "not_found"


def test_format_answer_caps_and_strips() -> None:
    raw = "**Lock-in** is 3 years. B. C. D.\nSource: https://x.y\nLast updated: today"
    assert format_answer(raw) == "Lock-in is 3 years. B. C."


def test_non_allowlisted_citation_is_dropped() -> None:
    assert pick_source_url([_chunk(0.9, "https://groww.in/x")]) is None


def test_real_index_gate() -> None:
    if not (INDEX_DIR / "chroma.sqlite3").exists():
        pytest.skip("index not built")
    if not (config.ANTHROPIC_API_KEY or config.GROQ_API_KEY):
        pytest.skip("no ANTHROPIC_API_KEY")
    ok = answer_question("What is the expense ratio of HDFC Large Cap Fund Direct Growth?")
    assert ok["type"] == "factual"
    assert ok["source_url"].startswith("https://")
    assert answer_question("asdfgh")["type"] == "not_found"


def test_chat_endpoint() -> None:
    res = client.post("/chat", json={"question": "Should I buy HDFC Small Cap?"})
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "refusal"
    assert "source_url" in body
    assert "last_updated" in body


def test_citation_follows_source_chosen_by_model(monkeypatch) -> None:
    chunks = [_chunk(0.9, "https://files.hdfcfund.com/a.pdf"), _chunk(0.8, "https://www.amfiindia.com/b")]
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: chunks)
    monkeypatch.setattr(pipeline, "generate_answer", lambda q, c: "SOURCE: 2\nIt is 3 years.")
    data = answer_question("exit load of HDFC Large Cap?")
    assert data["source_url"] == "https://www.amfiindia.com/b"
    assert data["answer"] == "It is 3 years."
    monkeypatch.setattr(pipeline, "generate_answer", lambda q, c: "SOURCE: 9\nIt is 3 years.")
    assert answer_question("exit load of HDFC Large Cap?")["source_url"] == "https://files.hdfcfund.com/a.pdf"


def test_empty_index_message_is_distinct(monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [])
    data = answer_question("exit load of HDFC Large Cap?")
    assert data["type"] == "not_found"
    assert "unavailable" in data["answer"]


def test_startup_logs_error_on_empty_index(monkeypatch, caplog) -> None:
    from app import main

    monkeypatch.setattr(main, "index_chunk_counts", lambda: {})
    with caplog.at_level("ERROR", logger="uvicorn.error"):
        with TestClient(main.app):
            pass
    assert "index is empty" in caplog.text


def test_startup_quiet_when_index_complete(monkeypatch, caplog) -> None:
    from app import main
    from app.catalog import SCHEMES

    monkeypatch.setattr(main, "index_chunk_counts", lambda: {s.scheme_id: 5 for s in SCHEMES})
    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "k")
    with caplog.at_level("ERROR", logger="uvicorn.error"):
        with TestClient(main.app):
            pass
    assert caplog.text == ""


def test_answer_date_follows_selected_source(monkeypatch):
    from dataclasses import replace
    chunk = replace(_chunk(0.8), snapshot_date="2026-10-02")
    monkeypatch.setattr(pipeline, "retrieve", lambda q, s=None: [chunk])
    monkeypatch.setattr(pipeline, "generate_answer", lambda q, c: "SOURCE: 1\nExit load is nil.")
    assert answer_question("exit load of HDFC Large Cap?")["last_updated"] == "2026-10-02"


def test_startup_accepts_groq_only(monkeypatch, caplog):
    from app import main
    from app.catalog import SCHEMES
    monkeypatch.setattr(main, "index_chunk_counts", lambda: {s.scheme_id: 5 for s in SCHEMES})
    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(main, "GROQ_API_KEY", "test-key")
    with caplog.at_level("ERROR", logger="uvicorn.error"):
        with TestClient(main.app):
            pass
    assert caplog.text == ""
