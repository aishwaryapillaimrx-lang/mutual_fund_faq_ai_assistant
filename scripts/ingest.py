"""CLI: build the Chroma index from data/manifest.json.

Usage:
    python scripts/ingest.py                 # ingest (uses download cache)
    python scripts/ingest.py --refresh       # re-download every URL
    python scripts/ingest.py --check-url URL # allowlist check only; exit 1 if rejected
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.catalog import SCHEMES  # noqa: E402
from app.config import CORPUS_SNAPSHOT_DATE, INDEX_DIR  # noqa: E402
from app.rag.ingest import IngestError, is_allowed_url, run_ingest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download all URLs")
    parser.add_argument("--snapshot-date", default=CORPUS_SNAPSHOT_DATE)
    parser.add_argument("--check-url", metavar="URL", help="only test the host allowlist")
    args = parser.parse_args()

    if args.check_url:
        allowed = is_allowed_url(args.check_url)
        print(f"{'ALLOWED' if allowed else 'REJECTED'}: {args.check_url}")
        return 0 if allowed else 1

    print(f"Snapshot date: {args.snapshot_date}\n")
    try:
        report = run_ingest(snapshot_date=args.snapshot_date, refresh=args.refresh)
    except IngestError as exc:
        print(f"\nIngest failed: {exc}")
        return 1

    print(f"\nIndex written to {INDEX_DIR} ({report.total_chunks} chunks)")
    print("\nChunks by scheme_id:")
    for scheme in SCHEMES:
        print(f"  {scheme.scheme_id:<40} {report.chunks_by_scheme.get(scheme.scheme_id, 0)}")
    print(f"  {'shared (statements/education)':<40} {report.chunks_by_scheme.get('shared', 0)}")
    print("\nChunks by doc_type:")
    for doc_type, count in sorted(report.chunks_by_doc_type.items()):
        print(f"  {doc_type:<40} {count}")

    missing = [s.scheme_id for s in SCHEMES if not report.chunks_by_scheme.get(s.scheme_id)]
    if missing:
        print(f"\nWARNING: no chunks for {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
