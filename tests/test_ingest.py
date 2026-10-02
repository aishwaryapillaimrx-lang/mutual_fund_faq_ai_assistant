from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.catalog import SCHEMES
from app.config import MANIFEST_PATH
from app.rag.ingest import (
    IngestError,
    ManifestDoc,
    build_chunk_records,
    chunk_text,
    is_allowed_url,
    load_manifest,
    run_ingest,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.hdfcfund.com/",
        "https://files.hdfcfund.com/s3fs-public/KIM/x.pdf",
        "https://www.amfiindia.com/online-center/download-cas",
        "https://investor.sebi.gov.in/",
    ],
)
def test_allowlisted_hosts_accepted(url: str) -> None:
    assert is_allowed_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        "https://www.moneycontrol.com/mutual-funds/hdfc",
        "https://hdfcfund.com.evil.example/x.pdf",
        "https://nothdfcfund.com/x.pdf",
        "ftp://files.hdfcfund.com/x.pdf",
        "not a url",
    ],
)
def test_other_hosts_rejected(url: str) -> None:
    assert not is_allowed_url(url)


def test_manifest_covers_five_schemes_with_official_urls_only() -> None:
    docs = load_manifest(MANIFEST_PATH)
    covered = {doc.scheme_id for doc in docs if doc.scheme_id}
    assert covered == {scheme.scheme_id for scheme in SCHEMES}
    assert any(doc.doc_type == "statements" for doc in docs)
    assert any(doc.doc_type == "education" for doc in docs)
    for doc in docs:
        assert "groww" not in doc.source_url.lower()
        assert is_allowed_url(doc.source_url), doc.source_url


def test_manifest_rejects_unknown_scheme(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"documents": [{"scheme_id": "sbi_bluechip", "doc_type": "kim", "source_url": "https://www.hdfcfund.com/"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(IngestError):
        load_manifest(manifest)


def test_chunk_text_overlaps_and_covers_all_words() -> None:
    words = [f"w{i}" for i in range(500)]
    chunks = chunk_text(" ".join(words), chunk_words=200, overlap_words=50)
    assert len(chunks) == 3
    assert chunks[0].split()[-50:] == chunks[1].split()[:50]
    assert chunks[-1].split()[-1] == "w499"
    assert chunk_text("") == []


def test_chunk_records_have_required_metadata() -> None:
    doc = ManifestDoc(
        scheme_id=None,
        doc_type="statements",
        title="Guide",
        source_url="https://www.amfiindia.com/guide",
    )
    records = build_chunk_records(doc, "word " * 400, "2026-09-27")
    assert records
    for record in records:
        meta = record["metadata"]
        assert meta["source_url"] == doc.source_url
        assert meta["snapshot_date"] == "2026-09-27"
        assert meta["doc_type"] == "statements"
        assert meta["scheme_id"] == ""
    assert len({record["chunk_id"] for record in records}) == len(records)


def test_run_ingest_rejects_groww_before_fetching(tmp_path: Path) -> None:
    page = tmp_path / "official.html"
    page.write_text(
        "<html><body><nav>menu</nav><main><p>The ELSS scheme has a statutory "
        "lock-in of 3 years.</p></main></body></html>",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "scheme_id": "hdfc_elss_direct_growth",
                        "doc_type": "factsheet",
                        "source_url": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
                    },
                    {
                        "scheme_id": "hdfc_elss_direct_growth",
                        "doc_type": "kim",
                        "title": "Official page",
                        "source_url": "https://files.hdfcfund.com/official.pdf",
                        "local_path": str(page),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = run_ingest(
        manifest_path=manifest,
        index_dir=tmp_path / "index",
        embed_fn=lambda texts: [[1.0, 0.0, 0.0] for _ in texts],
        log=lambda _msg: None,
    )

    assert report.skipped == [
        {
            "source_url": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
            "reason": "host not allowlisted",
        }
    ]
    assert report.ingested == ["https://files.hdfcfund.com/official.pdf"]
    assert report.chunks_by_scheme["hdfc_elss_direct_growth"] == 1
    assert (tmp_path / "index" / "ingest_report.json").exists()
