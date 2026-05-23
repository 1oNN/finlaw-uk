"""Unit tests for retrieval components.

Covers:
    - Reciprocal Rank Fusion (no model required)
    - DenseRetriever index/search and cache round-trip (sentence-transformers required;
      skipped if missing)
    - Orchestrator fallback cascade and hybrid-first behaviour (mocked sparse + dense)
    - Graph boost short-circuits when Neo4j is unavailable
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from backend.retrieval.hybrid import reciprocal_rank_fusion


def test_rrf_overlap_wins():
    # doc2 appears in all three lists (twice near the top) → highest fused score.
    list_a = ["doc1", "doc2", "doc3"]
    list_b = ["doc3", "doc2"]
    list_c = ["doc4", "doc2"]
    fused = reciprocal_rank_fusion([list_a, list_b, list_c], k=10, rrf_k=60)
    keys = [k for k, _ in fused]
    assert keys[0] == "doc2"
    assert set(keys) == {"doc1", "doc2", "doc3", "doc4"}


def test_rrf_single_list_preserves_order():
    fused = reciprocal_rank_fusion([["a", "b", "c"]], k=10, rrf_k=60)
    assert [k for k, _ in fused] == ["a", "b", "c"]


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_rrf_truncates_to_k():
    fused = reciprocal_rank_fusion([["a", "b", "c", "d", "e"]], k=3)
    assert len(fused) == 3


def test_rrf_scores_descending():
    fused = reciprocal_rank_fusion([["x", "y", "z"], ["x", "y", "z"]], k=10)
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)


def test_dense_retriever_finds_correct_doc(tmp_path):
    pytest.importorskip("sentence_transformers")
    from backend.retrieval.dense import DenseRetriever

    dr = DenseRetriever(cache_dir=tmp_path)
    docs = {
        "fsma": "FSMA section 19 general prohibition on carrying on a regulated activity in the UK unless authorised.",
        "cobs": "COBS 4.2 financial promotions must be fair, clear and not misleading.",
        "mlr": "MLR 2017 regulation 27 customer due diligence: identify and verify customer and beneficial owner.",
    }
    dr.index_documents(docs)
    assert dr.num_docs() == 3
    assert dr.embeddings is not None
    assert dr.embeddings.shape == (3, 384)

    results = dr.search("what is the UK general prohibition", k=3)
    assert len(results) == 3
    assert results[0][0] == "fsma"


def test_dense_cache_roundtrip(tmp_path):
    pytest.importorskip("sentence_transformers")
    from backend.retrieval.dense import DenseRetriever

    dr1 = DenseRetriever(cache_dir=tmp_path)
    dr1.index_documents({"hello": "hello world", "bye": "goodbye world"})

    dr2 = DenseRetriever(cache_dir=tmp_path)
    assert dr2.load_cache() is True
    assert set(dr2.keys) == {"hello", "bye"}
    assert dr2.embeddings.shape == (2, 384)

    # Reloaded retriever should find roughly the same nearest neighbour
    results = dr2.search("hello world", k=1)
    assert results[0][0] == "hello"


def test_dense_cache_rejects_model_mismatch(tmp_path):
    pytest.importorskip("sentence_transformers")
    from backend.retrieval.dense import DenseRetriever

    dr1 = DenseRetriever(cache_dir=tmp_path)
    dr1.index_documents({"a": "alpha"})

    dr2 = DenseRetriever(model_name="some-other-model", cache_dir=tmp_path)
    assert dr2.load_cache() is False


def test_orchestrator_falls_back_to_remote(monkeypatch):
    from backend.retrieval import orchestrator, sparse

    monkeypatch.setattr(orchestrator, "_hybrid_search", lambda q, k: [])
    monkeypatch.setattr(sparse, "search_phrase", lambda q, k: [])
    monkeypatch.setattr(sparse, "search_keywords", lambda q, k: [])
    monkeypatch.setattr(sparse, "list_upload_keys", lambda: [])
    monkeypatch.setattr(sparse, "search_remote", lambda q, m: "**Context (remote):**\nREMOTE_OK\n\n")

    result = orchestrator.get_context("anything")
    assert "REMOTE_OK" in result


def test_orchestrator_uses_hybrid_first(monkeypatch):
    from backend.retrieval import orchestrator, sparse

    monkeypatch.setattr(
        orchestrator, "_hybrid_search", lambda q, k: [("doc1", "HYBRID_SNIPPET")]
    )

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("Sparse fallback should not run when hybrid has hits")

    monkeypatch.setattr(sparse, "search_phrase", _should_not_be_called)

    result = orchestrator.get_context("anything")
    assert "HYBRID_SNIPPET" in result


def test_orchestrator_falls_back_to_phrase(monkeypatch):
    from backend.retrieval import orchestrator, sparse

    monkeypatch.setattr(orchestrator, "_hybrid_search", lambda q, k: [])
    monkeypatch.setattr(sparse, "search_phrase", lambda q, k: [("doc2", "PHRASE_SNIPPET")])

    result = orchestrator.get_context("anything")
    assert "PHRASE_SNIPPET" in result


def test_graph_boost_returns_empty_when_session_unavailable(monkeypatch):
    from backend.retrieval import orchestrator

    @contextmanager
    def fake_session():
        yield None

    monkeypatch.setattr(orchestrator, "get_session", fake_session)
    monkeypatch.setattr(orchestrator, "ENABLE_GRAPH", True)

    result = orchestrator.get_graph_boost("regulated activity")
    assert result == {"context_md": "", "source_line": "", "must_terms": []}


def test_graph_boost_returns_empty_when_disabled(monkeypatch):
    from backend.retrieval import orchestrator

    monkeypatch.setattr(orchestrator, "ENABLE_GRAPH", False)
    result = orchestrator.get_graph_boost("anything")
    assert result == {"context_md": "", "source_line": "", "must_terms": []}
