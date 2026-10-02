"""Chat pipeline: PII -> intent -> retrieve -> gate -> generate -> format."""

from __future__ import annotations

from typing import Any

from app.catalog import HDFC_FACTSHEET_HUB, SCHEMES, get_scheme
from app.config import (
    AMFI_KNOWLEDGE_URL,
    CORPUS_SNAPSHOT_DATE,
    HDFC_FUNDS_URL,
    SEBI_INVESTOR_URL,
)
from app.policy import analyze_question
from app.rag.cite import pick_source_url
from app.rag.format import format_answer, split_source_id
from app.rag.generate import GenerationError, generate_answer
from app.rag.prompt import NOT_IN_SOURCES
from app.rag.retrieve import passes_gate, retrieve


def _scheme_names() -> str:
    return "; ".join(scheme.display_name for scheme in SCHEMES)


def _fallback_url(scheme_id: str | None) -> str:
    if scheme_id:
        scheme = get_scheme(scheme_id)
        if scheme:
            return scheme.factsheet_url
    return HDFC_FACTSHEET_HUB


def _response(
    *,
    type_: str,
    answer: str,
    source_url: str,
    scheme_id: str | None,
) -> dict[str, Any]:
    return {
        "type": type_,
        "answer": answer,
        "source_url": source_url,
        "last_updated": CORPUS_SNAPSHOT_DATE,
        "scheme_id": scheme_id,
    }


def answer_question(question: str) -> dict[str, Any]:
    """Return architecture §5.3 JSON. Does not persist messages or log PII."""
    policy = analyze_question(question or "")

    if policy.contains_pii:
        return _response(
            type_="pii",
            answer=(
                "Personal identifiers are not accepted. "
                "Do not share PAN, Aadhaar, account numbers, OTPs, emails, or phone numbers. "
                "Ask a scheme fact without those details."
            ),
            source_url=SEBI_INVESTOR_URL,
            scheme_id=None,
        )

    if policy.intent == "advice":
        return _response(
            type_="refusal",
            answer=(
                "I can only share documented scheme facts, not buy/sell or portfolio advice. "
                "Please ask about expense ratio, exit load, SIP, lock-in, riskometer, or benchmark. "
                "SEBI and AMFI explain how mutual funds work for investors."
            ),
            source_url=AMFI_KNOWLEDGE_URL,
            scheme_id=policy.scheme_id,
        )

    if policy.intent == "performance":
        source = _fallback_url(policy.scheme_id)
        return _response(
            type_="refusal",
            answer=(
                "I do not compute or compare returns. "
                "Please open the official factsheet for performance figures. "
                "Ask a documented fee or feature fact if you want an in-app answer."
            ),
            source_url=source,
            scheme_id=policy.scheme_id,
        )

    if policy.intent == "out_of_scope":
        return _response(
            type_="refusal",
            answer=(
                f"I only cover five HDFC schemes: {_scheme_names()}. "
                "Other AMCs are out of scope for this demo. "
                "See HDFC Mutual Fund’s public site for official scheme pages."
            ),
            source_url=HDFC_FUNDS_URL,
            scheme_id=None,
        )

    if policy.clarify:
        return _response(
            type_="clarify",
            answer=(
                "Which scheme do you mean? "
                f"I can answer facts for: {_scheme_names()}."
            ),
            source_url=HDFC_FUNDS_URL,
            scheme_id=None,
        )

    chunks = retrieve(question, policy.scheme_id)
    source_url = pick_source_url(chunks) if passes_gate(chunks) else None
    if source_url is None:
        return _response(
            type_="not_found",
            answer=(
                "I could not find that in the indexed official documents. "
                "Please check the linked official page for scheme details."
                if chunks
                else "The official document index is unavailable right now. "
                "Please open the linked official page for scheme details."
            ),
            source_url=_fallback_url(policy.scheme_id),
            scheme_id=policy.scheme_id,
        )

    try:
        used = [c for c in chunks if passes_gate([c])]
        raw = generate_answer(question, used)
    except GenerationError:
        return _response(
            type_="not_found",
            answer="Service busy. Please open the official page for this scheme.",
            source_url=_fallback_url(policy.scheme_id),
            scheme_id=policy.scheme_id,
        )

    source_id, body = split_source_id(raw)
    answer = format_answer(body)
    if source_id is not None and 1 <= source_id <= len(used):
        source_url = pick_source_url([used[source_id - 1]]) or source_url
    if not answer or NOT_IN_SOURCES in raw:
        return _response(
            type_="not_found",
            answer=(
                "That detail is not in the indexed official sources. "
                "Please check the linked official page."
            ),
            source_url=_fallback_url(policy.scheme_id),
            scheme_id=policy.scheme_id,
        )
    return _response(
        type_="factual", answer=answer, source_url=source_url, scheme_id=policy.scheme_id
    )
