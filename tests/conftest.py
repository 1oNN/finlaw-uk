"""Shared pytest configuration for the FinLaw-UK test suite.

We override `RAG_DATA_DIR` to a non-existent path *before* the backend
modules are imported so that `backend.retrieval.sparse._load_static()`
exits early instead of scanning the real ~130 MB corpus on every test run.
Tests that need a populated corpus should call `sparse.add_documents()`
or `DenseRetriever.index_documents()` explicitly.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_EMPTY = Path(tempfile.gettempdir()) / "finlaw_test_empty_rag_dir"
_EMPTY.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("RAG_DATA_DIR", str(_EMPTY))
os.environ.setdefault("RAG_ENABLE_REMOTE", "0")
os.environ.setdefault("RAG_ENABLE_GRAPH", "0")
os.environ.setdefault("RAG_ENABLE_DENSE", "1")
