"""Offline ingest: manifest → download/read → extract → chunk → embed → Chroma.

Runs once before the demo (``python scripts/ingest.py``). Never called from /chat.
Only allowlisted official hosts are accepted; anything else (e.g. groww.in) is
skipped before any network request is made.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.catalog import SCHEMES
from app.config import (
    ALLOWED_HOSTS,
    CHUNK_OVERLAP_WORDS,
    CHUNK_WORDS,
    COLLECTION_NAME,
    CORPUS_DIR,
    CORPUS_SNAPSHOT_DATE,
    EMBED_MODEL,
    INDEX_DIR,
    LLM_API_KEY,
    LLM_BASE_URL,
    MANIFEST_PATH,
    ROOT_DIR,
)

DOC_TYPES = frozenset(
    {"factsheet", "kim", "sid", "faq", "fees", "riskometer", "statements", "education"}
)
# Chroma metadata cannot hold None, so shared (non-scheme) docs use "".
SHARED_SCHEME_ID = ""

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
_DOWNLOAD_CACHE = CORPUS_DIR / "cache"

EmbedFn = Callable[[list[str]], list[list[float]]]

# pypdf warns loudly about missing fontTools on HDFC PDFs; text still extracts.
logging.getLogger("pypdf").setLevel(logging.ERROR)


class IngestError(Exception):
    pass


@dataclass(frozen=True)
class ManifestDoc:
    scheme_id: str | None
    doc_type: str
    title: str
    source_url: str
    local_path: str | None = None
    optional: bool = False


@dataclass
class IngestReport:
    snapshot_date: str
    embed_model: str
    chunks_by_scheme: Counter = field(default_factory=Counter)
    chunks_by_doc_type: Counter = field(default_factory=Counter)
    ingested: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    @property
    def total_chunks(self) -> int:
        return sum(self.chunks_by_scheme.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_date": self.snapshot_date,
            "embed_model": self.embed_model,
            "total_chunks": self.total_chunks,
            "chunks_by_scheme": dict(self.chunks_by_scheme),
            "chunks_by_doc_type": dict(self.chunks_by_doc_type),
            "ingested": self.ingested,
            "skipped": self.skipped,
        }


# --- allowlist -------------------------------------------------------------


def is_allowed_url(url: str, allowed_hosts: Sequence[str] = ALLOWED_HOSTS) -> bool:
    """True only for http(s) URLs on an allowlisted host or its subdomain."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts)


# --- manifest --------------------------------------------------------------


def load_manifest(path: Path = MANIFEST_PATH) -> list[ManifestDoc]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    known_schemes = {scheme.scheme_id for scheme in SCHEMES}
    docs: list[ManifestDoc] = []
    for i, entry in enumerate(raw.get("documents", [])):
        doc = ManifestDoc(
            scheme_id=entry.get("scheme_id"),
            doc_type=entry.get("doc_type", ""),
            title=entry.get("title") or entry.get("source_url", ""),
            source_url=entry.get("source_url", ""),
            local_path=entry.get("local_path"),
            optional=bool(entry.get("optional", False)),
        )
        if doc.doc_type not in DOC_TYPES:
            raise IngestError(f"manifest[{i}]: unknown doc_type {doc.doc_type!r}")
        if doc.scheme_id is not None and doc.scheme_id not in known_schemes:
            raise IngestError(f"manifest[{i}]: unknown scheme_id {doc.scheme_id!r}")
        if not doc.source_url:
            raise IngestError(f"manifest[{i}]: source_url is required")
        docs.append(doc)
    return docs


# --- fetch + extract -------------------------------------------------------


def _cache_path(url: str) -> Path:
    return _DOWNLOAD_CACHE / hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _looks_like_pdf(data: bytes) -> bool:
    return data.lstrip()[:5] == b"%PDF-"


def fetch_document(
    doc: ManifestDoc,
    *,
    allowed_hosts: Sequence[str] = ALLOWED_HOSTS,
    refresh: bool = False,
    timeout: float = 60.0,
) -> bytes:
    """Return raw bytes from local_path, the download cache, or the network."""
    if doc.local_path:
        local = Path(doc.local_path)
        if not local.is_absolute():
            local = ROOT_DIR / local
        if not local.exists():
            raise IngestError(f"local file not found: {doc.local_path}")
        return local.read_bytes()

    cached = _cache_path(doc.source_url)
    if cached.exists() and not refresh:
        return cached.read_bytes()

    with httpx.Client(
        headers={"User-Agent": _USER_AGENT}, follow_redirects=True, timeout=timeout
    ) as client:
        response = client.get(doc.source_url)
    if not is_allowed_url(str(response.url), allowed_hosts):
        raise IngestError(f"redirected to non-allowlisted host: {response.url}")
    if response.status_code != 200:
        raise IngestError(
            f"HTTP {response.status_code} (save the page manually and set local_path)"
        )

    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(response.content)
    return response.content


def _clean(text: str) -> str:
    text = text.replace("​", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_text(data: bytes) -> str:
    """Extract plain text from PDF or HTML bytes."""
    if _looks_like_pdf(data):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return _clean(" ".join(page.extract_text() or "" for page in reader.pages))

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return _clean(main.get_text(" "))


# --- chunk -----------------------------------------------------------------


def chunk_text(
    text: str,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """Split into overlapping word windows (~1.3 tokens per word)."""
    if overlap_words >= chunk_words:
        raise ValueError("overlap must be smaller than chunk size")
    words = text.split()
    if not words:
        return []
    step = chunk_words - overlap_words
    chunks: list[str] = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + chunk_words]))
        if start + chunk_words >= len(words):
            break
    return chunks


def build_chunk_records(
    doc: ManifestDoc, text: str, snapshot_date: str
) -> list[dict[str, Any]]:
    """Chunk records per architecture §5.2 (embedding added at upsert time)."""
    doc_key = hashlib.sha1(doc.source_url.encode("utf-8")).hexdigest()[:10]
    records = []
    for i, chunk in enumerate(chunk_text(text)):
        records.append(
            {
                "chunk_id": f"{doc_key}-{i:04d}",
                # Title prefix lets chunks that never name the scheme still match it.
                "text": f"{doc.title}\n{chunk}",
                "metadata": {
                    "scheme_id": doc.scheme_id or SHARED_SCHEME_ID,
                    "doc_type": doc.doc_type,
                    "source_url": doc.source_url,
                    "snapshot_date": snapshot_date,
                    "title": doc.title,
                },
            }
        )
    return records


# --- embed + store ---------------------------------------------------------


def _local_embed_fn() -> EmbedFn:
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    model = DefaultEmbeddingFunction()
    return lambda texts: [list(map(float, vec)) for vec in model(texts)]


def _api_embed_fn() -> EmbedFn:
    if not LLM_API_KEY:
        raise IngestError("EMBED_MODEL is set to an API model but LLM_API_KEY is empty")

    def embed(texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            f"{LLM_BASE_URL.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={"model": EMBED_MODEL, "input": texts},
            timeout=60.0,
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in rows]

    return embed


def get_embed_fn() -> EmbedFn:
    """Shared by ingest and retrieval so both use the same vector space."""
    if EMBED_MODEL.strip().lower() in ("", "local"):
        return _local_embed_fn()
    return _api_embed_fn()


def open_client(index_dir: Path = INDEX_DIR):
    import chromadb
    from chromadb.config import Settings

    index_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(index_dir), settings=Settings(anonymized_telemetry=False)
    )


def _recreate_collection(client, snapshot_date: str):
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:  # collection did not exist yet
        pass
    return client.create_collection(
        COLLECTION_NAME,
        embedding_function=None,
        metadata={
            "hnsw:space": "cosine",
            "embed_model": EMBED_MODEL,
            "snapshot_date": snapshot_date,
        },
    )


# --- orchestration ---------------------------------------------------------


def run_ingest(
    *,
    manifest_path: Path = MANIFEST_PATH,
    index_dir: Path = INDEX_DIR,
    snapshot_date: str = CORPUS_SNAPSHOT_DATE,
    allowed_hosts: Sequence[str] = ALLOWED_HOSTS,
    refresh: bool = False,
    embed_fn: EmbedFn | None = None,
    log: Callable[[str], None] = print,
) -> IngestReport:
    """Rebuild the index from the manifest. Returns counts and skipped docs."""
    docs = load_manifest(manifest_path)
    report = IngestReport(snapshot_date=snapshot_date, embed_model=EMBED_MODEL)
    records: list[dict[str, Any]] = []

    for doc in docs:
        if not is_allowed_url(doc.source_url, allowed_hosts):
            reason = "host not allowlisted"
            report.skipped.append({"source_url": doc.source_url, "reason": reason})
            log(f"REJECT  {doc.source_url}  ({reason})")
            continue
        try:
            text = extract_text(
                fetch_document(doc, allowed_hosts=allowed_hosts, refresh=refresh)
            )
        except (IngestError, httpx.HTTPError) as exc:
            report.skipped.append({"source_url": doc.source_url, "reason": str(exc)})
            label = "SKIP   " if doc.optional else "FAIL   "
            log(f"{label} {doc.title}  ({exc})")
            continue
        if not text:
            report.skipped.append({"source_url": doc.source_url, "reason": "no text"})
            log(f"FAIL    {doc.title}  (no extractable text)")
            continue

        doc_records = build_chunk_records(doc, text, snapshot_date)
        records.extend(doc_records)
        report.ingested.append(doc.source_url)
        for record in doc_records:
            report.chunks_by_scheme[record["metadata"]["scheme_id"] or "shared"] += 1
            report.chunks_by_doc_type[doc.doc_type] += 1
        log(f"OK      {doc.title}  ({len(doc_records)} chunks)")

    if not records:
        raise IngestError("no documents ingested; index left unchanged")

    embed = embed_fn or get_embed_fn()
    collection = _recreate_collection(open_client(index_dir), snapshot_date)
    batch = 64
    for start in range(0, len(records), batch):
        part = records[start : start + batch]
        texts = [record["text"] for record in part]
        collection.add(
            ids=[record["chunk_id"] for record in part],
            documents=texts,
            metadatas=[record["metadata"] for record in part],
            embeddings=embed(texts),
        )

    (index_dir / "ingest_report.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    return report
