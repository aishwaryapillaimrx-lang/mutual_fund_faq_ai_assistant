"""Map user wording onto the five catalog schemes."""

from __future__ import annotations

import re

from app.catalog import SCHEMES, Scheme


def _normalize(text: str) -> str:
    collapsed = re.sub(r"[-_]+", " ", text.lower())
    return re.sub(r"\s+", " ", collapsed).strip()


def _alias_in_text(text_norm: str, alias: str) -> bool:
    alias_norm = _normalize(alias)
    if not alias_norm:
        return False
    pattern = r"(?<!\w)" + re.escape(alias_norm) + r"(?!\w)"
    return re.search(pattern, text_norm) is not None


def _matching_schemes(question: str) -> tuple[Scheme, ...]:
    text_norm = _normalize(question)
    matched: list[Scheme] = []
    for scheme in SCHEMES:
        aliases_longest_first = sorted(scheme.aliases, key=len, reverse=True)
        if any(_alias_in_text(text_norm, alias) for alias in aliases_longest_first):
            matched.append(scheme)
    return tuple(matched)


def resolve_scheme(question: str) -> tuple[str | None, bool]:
    """Return (scheme_id, clarify).

    - 0 matches: (None, False) — still a factual question with unknown scheme
    - 1 match: (scheme_id, False)
    - 2+ distinct schemes: (None, True)
    """
    matched = _matching_schemes(question)
    if len(matched) == 0:
        return None, False
    if len(matched) == 1:
        return matched[0].scheme_id, False
    return None, True
