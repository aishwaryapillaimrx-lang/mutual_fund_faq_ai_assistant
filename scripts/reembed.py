"""Re-embed existing verified passages into a separate index without downloading sources."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import COLLECTION_NAME, EMBED_MODEL, INDEX_DIR
from app.rag.ingest import IngestError, get_embed_fn, open_client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == INDEX_DIR.resolve():
        parser.error("Output must be separate from the active index")
    source = open_client(INDEX_DIR).get_collection(COLLECTION_NAME, embedding_function=None)
    records = source.get(include=["documents", "metadatas"])
    if not records["ids"]:
        raise IngestError("The existing index is empty")
    output = open_client(args.output)
    if COLLECTION_NAME in [collection.name for collection in output.list_collections()]:
        raise IngestError("Output collection already exists; choose a new output directory")
    embed = get_embed_fn()
    vectors = []
    batch = 16 if EMBED_MODEL.startswith("hf:") else 64
    for start in range(0, len(records["ids"]), batch):
        part = records["documents"][start:start + batch]
        vectors.extend(embed(part))
        print(f"Embedded {min(start + batch, len(records['ids']))}/{len(records['ids'])}", flush=True)
    collection = output.create_collection(COLLECTION_NAME, embedding_function=None,
        metadata={**(source.metadata or {}), "embed_model": EMBED_MODEL})
    for start in range(0, len(records["ids"]), batch):
        collection.add(ids=records["ids"][start:start + batch],
            documents=records["documents"][start:start + batch],
            metadatas=records["metadatas"][start:start + batch],
            embeddings=vectors[start:start + batch])
    print(f"Created {collection.count()} chunks with {EMBED_MODEL}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
