from types import SimpleNamespace

import pytest
import huggingface_hub

from app.rag import ingest, retrieve as retrieval


def test_hf_documents_and_queries_use_expected_inputs(monkeypatch):
    monkeypatch.setattr(ingest, "EMBED_MODEL", "hf:BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(ingest, "HF_TOKEN", "test-token")
    calls = []
    def feature_extraction(inputs, *, normalize, truncate):
        assert normalize and truncate
        calls.append(inputs)
        return [[3.0, 4.0] for _ in inputs]
    def client(**kwargs):
        assert kwargs["model"] == "BAAI/bge-small-en-v1.5"
        assert kwargs["provider"] == "hf-inference"
        return SimpleNamespace(feature_extraction=feature_extraction)
    monkeypatch.setattr(huggingface_hub, "InferenceClient", client)
    assert ingest.get_embed_fn()(["Document."]) == [[0.6, 0.8]]
    assert ingest.get_embed_fn(query=True)(["Question?"]) == [[0.6, 0.8]]
    assert calls == [["Document."], ["Represent this sentence for searching relevant passages: Question?"]]
    assert ingest.get_embed_fn()([]) == []


@pytest.mark.parametrize("result", [[], [[0.0, 0.0]], [[float("nan"), 1]], [[[1, 2], [3, 4]]]])
def test_hf_rejects_invalid_vectors(monkeypatch, result):
    monkeypatch.setattr(ingest, "EMBED_MODEL", "hf:BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(ingest, "HF_TOKEN", "test-token")
    monkeypatch.setattr(huggingface_hub, "InferenceClient", lambda **kw:
        SimpleNamespace(feature_extraction=lambda *args, **kwargs: result))
    with pytest.raises(ingest.IngestError, match="Hugging Face embedding failed"):
        ingest.get_embed_fn()(["Document"])


def test_hf_requires_token(monkeypatch):
    monkeypatch.setattr(ingest, "EMBED_MODEL", "hf:BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(ingest, "HF_TOKEN", "")
    with pytest.raises(ingest.IngestError, match="HF_TOKEN"):
        ingest.get_embed_fn()


def test_retrieval_rejects_previous_model_before_embedding(monkeypatch):
    collection = SimpleNamespace(metadata={"embed_model": "local"}, count=lambda: 1)
    monkeypatch.setattr(retrieval, "EMBED_MODEL", "hf:BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(retrieval, "open_client", lambda path:
        SimpleNamespace(get_collection=lambda *args, **kwargs: collection))
    def fail(**kwargs):
        pytest.fail("Mismatched index must not invoke embedding provider")
    monkeypatch.setattr(retrieval, "get_embed_fn", fail)
    assert retrieval.retrieve("expense ratio?") == []


def test_embedding_failure_preserves_existing_index(tmp_path):
    import json
    page = tmp_path / "page.html"
    page.write_text("<main>Official document text</main>", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"documents": [{"scheme_id": None,
        "doc_type": "statements", "source_url": "https://www.hdfcfund.com/source",
        "local_path": str(page)}]}), encoding="utf-8")
    index = tmp_path / "index"
    ingest.run_ingest(manifest_path=manifest, index_dir=index,
        embed_fn=lambda texts: [[1.0, 0.0] for _ in texts], log=lambda text: None)
    collection = ingest.open_client(index).get_collection(ingest.COLLECTION_NAME, embedding_function=None)
    before = collection.get(include=["documents"])
    def fail(texts):
        raise ingest.IngestError("provider unavailable")
    with pytest.raises(ingest.IngestError, match="provider unavailable"):
        ingest.run_ingest(manifest_path=manifest, index_dir=index, embed_fn=fail, log=lambda text: None)
    after = ingest.open_client(index).get_collection(ingest.COLLECTION_NAME, embedding_function=None).get(include=["documents"])
    assert before == after
