"""Keyword intent router. PII is handled by the caller before this module."""

from __future__ import annotations

import re

from app.policy.scheme_resolver import resolve_scheme

_ADVICE_PATTERNS = (
    re.compile(r"\bshould\s+i\b", re.IGNORECASE),
    re.compile(r"\bbuy\b", re.IGNORECASE),
    re.compile(r"\bsell\b", re.IGNORECASE),
    re.compile(r"\binvest\s+in\b", re.IGNORECASE),
    re.compile(r"\bbetter\s+than\b", re.IGNORECASE),
    re.compile(r"\brecommend", re.IGNORECASE),
    re.compile(r"\ballocate\b", re.IGNORECASE),
    re.compile(r"\bportfolio\b", re.IGNORECASE),
)

_PERFORMANCE_PATTERNS = (
    re.compile(r"\bcagr\b", re.IGNORECASE),
    re.compile(r"\breturns?\b", re.IGNORECASE),
    re.compile(r"\bbest\s+performing\b", re.IGNORECASE),
    re.compile(r"\boutperform", re.IGNORECASE),
    re.compile(r"\b(?:1|3|5)\s*[-]?\s*(?:y|yr|year)s?\b", re.IGNORECASE),
    re.compile(r"\b(?:1y|3y|5y)\b", re.IGNORECASE),
)

_OTHER_AMC = re.compile(
    r"\b("
    r"sbi|icici|nippon|axis|kotak|uti|mirae|dsp|franklin|ppfas|"
    r"aditya\s+birla|birla\s+sun\s+life|parag\s+parikh|motilal|"
    r"invesco|hsbc|bandhan|tata\s+(?:mutual|mf)|quant\s+(?:mutual|mf)|"
    r"edelweiss|canara\s+robeco|sundaram"
    r")\b",
    re.IGNORECASE,
)


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def classify_intent(question: str) -> str:
    """Return advice | performance | out_of_scope | factual.

    Advice wins over factual keywords. Other AMCs are out of scope unless
    one of the five catalog schemes is clearly mentioned.
    """
    if _matches_any(question, _ADVICE_PATTERNS):
        return "advice"
    if _matches_any(question, _PERFORMANCE_PATTERNS):
        return "performance"

    scheme_id, clarify = resolve_scheme(question)
    mentions_ours = scheme_id is not None or clarify
    if _OTHER_AMC.search(question) and not mentions_ours:
        return "out_of_scope"

    return "factual"
