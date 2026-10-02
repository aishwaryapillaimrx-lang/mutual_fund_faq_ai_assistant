"""Citation picker: one allowlisted source URL, taken from the best chunk."""

from __future__ import annotations

from collections.abc import Sequence

from app.rag.ingest import is_allowed_url
from app.rag.retrieve import RetrievedChunk


def pick_source_url(chunks: Sequence[RetrievedChunk]) -> str | None:
    """URL of the highest-scoring chunk on an allowlisted host, else None."""
    for chunk in sorted(chunks, key=lambda c: c.score, reverse=True):
        if is_allowed_url(chunk.source_url):
            return chunk.source_url
    return None
