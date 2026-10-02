"""Retriever: embed the question, query Chroma, apply the retrieval gate."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import COLLECTION_NAME, INDEX_DIR, RETRIEVAL_SCORE_THRESHOLD
from app.rag.ingest import get_embed_fn, open_client

logger = logging.getLogger(__name__)

TOP_K = 6
CANDIDATES = 24  # pulled by embedding, then re-ranked with a keyword boost
KEYWORD_WEIGHT = 0.15

# Words that carry no signal for matching a fact (question words + scheme names).
_STOPWORDS = frozenset(
    "what which whose when where how does with from that this have your about tell please "
    "give show the and for are can i is of in to a an me my hdfc fund funds cap direct growth "
    "plan scheme schemes flexi large small tax saver elss balanced advantage equity amount level".split()
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower())


def _keywords(question: str) -> list[str]:
    return [w for w in _norm(question).split() if len(w) >= 3 and w not in _STOPWORDS]


def _keyword_boost(keywords: list[str], text: str) -> float:
    if not keywords:
        return 0.0
    haystack = _norm(text)
    return sum(1 for w in keywords if w in haystack) / len(keywords)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float  # cosine similarity: 1 - distance
    scheme_id: str | None
    doc_type: str
    source_url: str
    snapshot_date: str


def retrieve(
    question: str,
    scheme_id: str | None = None,
    *,
    k: int = TOP_K,
    index_dir: Path = INDEX_DIR,
    embed_fn=None,
) -> list[RetrievedChunk]:
    """Top-k chunks, best first. Empty list if the index is missing or empty."""
    try:
        collection = open_client(index_dir).get_collection(
            COLLECTION_NAME, embedding_function=None
        )
        if collection.count() == 0:
            logger.error("Index is empty; run scripts/ingest.py")
            return []
        embed = embed_fn or get_embed_fn()
        result = collection.query(
            query_embeddings=embed([question]),
            n_results=max(k, CANDIDATES),
            where={"scheme_id": scheme_id} if scheme_id else None,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:  # missing collection / index problems -> gate returns not_found
        logger.exception("Retrieval failed")
        return []

    chunks = []
    for text, meta, dist in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        chunks.append(
            RetrievedChunk(
                text=text,
                score=1.0 - float(dist),
                scheme_id=meta.get("scheme_id") or None,
                doc_type=meta.get("doc_type", ""),
                source_url=meta.get("source_url", ""),
                snapshot_date=meta.get("snapshot_date", ""),
            )
        )
    keywords = _keywords(question)
    ranked = sorted(
        chunks,
        key=lambda c: c.score + KEYWORD_WEIGHT * _keyword_boost(keywords, c.text),
        reverse=True,
    )
    return ranked[:k]


def index_chunk_counts(index_dir: Path = INDEX_DIR) -> dict[str, int]:
    """Chunk count per scheme_id ("" = shared docs). Empty dict if no usable index."""
    try:
        collection = open_client(index_dir).get_collection(
            COLLECTION_NAME, embedding_function=None
        )
        metas = collection.get(include=["metadatas"])["metadatas"]
    except Exception:
        return {}
    counts: dict[str, int] = {}
    for meta in metas:
        key = meta.get("scheme_id") or ""
        counts[key] = counts.get(key, 0) + 1
    return counts


def passes_gate(
    chunks: list[RetrievedChunk], threshold: float = RETRIEVAL_SCORE_THRESHOLD
) -> bool:
    """Gate on the best raw similarity (ranking may reorder by keyword boost)."""
    return bool(chunks) and max(c.score for c in chunks) >= threshold
