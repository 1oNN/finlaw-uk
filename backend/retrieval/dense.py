"""Dense semantic retrieval using sentence-transformers + FAISS.

Provides `DenseRetriever`, which encodes documents and queries into 384-dim
vectors using `BAAI/bge-small-en-v1.5` (default) and finds nearest neighbours
by inner product on normalised vectors — equivalent to cosine similarity.

FAISS (`IndexFlatIP`) is the index when available; otherwise a NumPy
implementation is used as a fallback (slower but correct). The persistent
cache is stored as a `.npy` file (embeddings) plus a JSON sidecar (keys
and model name) under `data/cache/` — no Python pickle is used, so the
cache is portable and safe to share.

Environment:
    DENSE_MODEL       (default: BAAI/bge-small-en-v1.5)
    DENSE_CACHE_DIR   (default: ./data/cache)
    DENSE_DEVICE      (default: cpu)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except Exception:
    faiss = None  # type: ignore
    _FAISS_AVAILABLE = False


DEFAULT_MODEL = os.getenv("DENSE_MODEL", "BAAI/bge-small-en-v1.5")
DEFAULT_CACHE_DIR = Path(os.getenv("DENSE_CACHE_DIR", "./data/cache"))
DEFAULT_DEVICE = os.getenv("DENSE_DEVICE", "cpu")


class DenseRetriever:
    """Sentence-transformer + FAISS dense retriever.

    Args:
        model_name: HF identifier for the encoder. Default BGE-small (384-dim, ~134 MB).
        cache_dir:  on-disk cache location for embeddings and metadata.
        device:     'cpu' or 'cuda'.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        cache_dir: Optional[Path] = None,
        device: str = DEFAULT_DEVICE,
    ):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
        self.device = device
        self._model = None
        self.keys: List[str] = []
        self.embeddings: Optional[np.ndarray] = None
        self.index = None  # FAISS index (None if FAISS unavailable)

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def _encode(self, texts: List[str]) -> np.ndarray:
        model = self._load_model()
        embs = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embs.astype("float32")

    def _build_faiss_index(self) -> None:
        if not _FAISS_AVAILABLE or self.embeddings is None or len(self.embeddings) == 0:
            self.index = None
            return
        d = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(d)
        self.index.add(self.embeddings)

    def index_documents(self, docs: Dict[str, str], persist: bool = True) -> None:
        """Encode the entire corpus and rebuild the index. Overwrites any
        previous state. If `persist=True`, writes the cache."""
        self.keys = list(docs.keys())
        texts = [docs[k] for k in self.keys]
        if not texts:
            self.embeddings = np.zeros((0, 384), dtype="float32")
            self.index = None
            return
        self.embeddings = self._encode(texts)
        self._build_faiss_index()
        if persist:
            self._save_cache()

    def add_documents(self, docs: Dict[str, str], persist: bool = True) -> None:
        """Incrementally append documents to the index."""
        if not docs:
            return
        new_keys = [k for k in docs.keys() if k not in self.keys]
        if not new_keys:
            return
        new_texts = [docs[k] for k in new_keys]
        new_embs = self._encode(new_texts)
        if self.embeddings is None or len(self.embeddings) == 0:
            self.embeddings = new_embs
        else:
            self.embeddings = np.vstack([self.embeddings, new_embs])
        self.keys.extend(new_keys)
        self._build_faiss_index()
        if persist:
            self._save_cache()

    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """Return up to k `(doc_key, cosine_score)` pairs, highest first."""
        if not self.keys or self.embeddings is None or len(self.embeddings) == 0:
            return []
        q_emb = self._encode([query])[0]
        if _FAISS_AVAILABLE and self.index is not None:
            scores, idxs = self.index.search(q_emb.reshape(1, -1), min(k, len(self.keys)))
            return [
                (self.keys[i], float(scores[0][j]))
                for j, i in enumerate(idxs[0])
                if i >= 0
            ]
        sims = self.embeddings @ q_emb
        order = np.argsort(-sims)[: min(k, len(self.keys))]
        return [(self.keys[i], float(sims[i])) for i in order]

    def _cache_paths(self) -> Tuple[Path, Path]:
        return (
            self.cache_dir / "dense_embeddings.npy",
            self.cache_dir / "dense_meta.json",
        )

    def _save_cache(self) -> None:
        if self.embeddings is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        emb_path, meta_path = self._cache_paths()
        np.save(emb_path, self.embeddings)
        meta = {
            "model_name": self.model_name,
            "embedding_dim": int(self.embeddings.shape[1]) if self.embeddings.ndim == 2 else 0,
            "num_docs": int(self.embeddings.shape[0]) if self.embeddings.ndim == 2 else 0,
            "keys": self.keys,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)

    def load_cache(self) -> bool:
        """Try to restore embeddings + keys from disk. Returns True on success.
        Returns False if any file is missing, the model name doesn't match, or
        the shapes are inconsistent — caller should rebuild from scratch."""
        emb_path, meta_path = self._cache_paths()
        if not (emb_path.exists() and meta_path.exists()):
            return False
        try:
            embeddings = np.load(emb_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("model_name") != self.model_name:
                return False
            keys = meta.get("keys") or []
            if len(keys) != embeddings.shape[0]:
                return False
            self.embeddings = embeddings.astype("float32")
            self.keys = list(keys)
            self._build_faiss_index()
            return True
        except Exception:
            return False

    def num_docs(self) -> int:
        return len(self.keys)
