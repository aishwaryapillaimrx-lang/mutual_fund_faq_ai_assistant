"""Deterministic policy: PII, intent, scheme resolution."""

from __future__ import annotations

from dataclasses import dataclass

from app.policy.intent import classify_intent
from app.policy.pii import contains_pii
from app.policy.scheme_resolver import resolve_scheme


@dataclass(frozen=True)
class PolicyResult:
    contains_pii: bool
    intent: str | None
    scheme_id: str | None
    clarify: bool


def analyze_question(question: str) -> PolicyResult:
    """PII is checked first. Never log `question` from this function."""
    if contains_pii(question):
        return PolicyResult(
            contains_pii=True,
            intent=None,
            scheme_id=None,
            clarify=False,
        )

    intent = classify_intent(question)
    scheme_id, clarify = resolve_scheme(question)
    if clarify:
        return PolicyResult(
            contains_pii=False,
            intent=intent,
            scheme_id=None,
            clarify=True,
        )
    return PolicyResult(
        contains_pii=False,
        intent=intent,
        scheme_id=scheme_id,
        clarify=False,
    )
