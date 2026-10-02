"""Answer formatter: cap body to 3 sentences, strip links/markdown the model may add."""

from __future__ import annotations

import re

MAX_SENTENCES = 3

_URL = re.compile(r"https?://\S+|www\.\S+")
_MARKDOWN = re.compile(r"[*_`#>]+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_SOURCE_LINE = re.compile(r"(?im)^\s*(source|last updated)[^\n]*$")


_SOURCE_ID = re.compile(r"(?im)^\s*SOURCE:\s*(\d+)\s*$")


def split_source_id(raw: str) -> tuple[int | None, str]:
    """Pull the model's `SOURCE: n` line (1-based chunk id) out of the raw reply."""
    match = _SOURCE_ID.search(raw)
    if not match:
        return None, raw
    return int(match.group(1)), _SOURCE_ID.sub("", raw, count=1)


def format_answer(text: str, max_sentences: int = MAX_SENTENCES) -> str:
    text = _SOURCE_LINE.sub("", text)
    text = _URL.sub("", text)
    text = _MARKDOWN.sub("", text)
    text = " ".join(text.split())
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s]
    return " ".join(sentences[:max_sentences])
