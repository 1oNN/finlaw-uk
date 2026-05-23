"""Sparse retrieval: in-memory document store with phrase, keyword, and BM25 search.

Loads static reference documents from `backend/data/` (recursive) at import time
into an in-memory database. Provides four search backends:
    - phrase regex match
    - inverted-index keyword overlap
    - BM25 (rank_bm25)
    - remote legislation.gov.uk best-effort lookup

Plus `add_documents()` for the upload pipeline to append chunks.

This module was extracted from the legacy `backend/rag_helper.py`. The graph
boost and high-level orchestration (`get_context`) now live in
`backend/retrieval/orchestrator.py`.

Environment:
    RAG_DATA_DIR        (default: <repo>/backend/data)
    RAG_MAX_SNIP        (default: 2200)
    RAG_TOPK            (default: 3)
    RAG_ENABLE_REMOTE   (default: 1)
    RAG_DEBUG           (default: 0)
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx  # python-docx
except Exception:
    docx = None

try:
    import pandas as pd
except Exception:
    pd = None

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except Exception:
    _BM25_AVAILABLE = False
    BM25Okapi = None  # type: ignore

import requests


ROOT_DIR = Path(os.getenv("RAG_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
MAX_SNIP = int(os.getenv("RAG_MAX_SNIP", "2200"))
TOPK = int(os.getenv("RAG_TOPK", "3"))
ENABLE_REMOTE = bool(int(os.getenv("RAG_ENABLE_REMOTE", "1")))
DEBUG = bool(int(os.getenv("RAG_DEBUG", "0")))


_LOCAL_DB: Dict[str, str] = {}
_INVERTED: Dict[str, List[str]] = {}
_DOC_TOKS: Dict[str, List[str]] = {}
_BM: Optional["BM25Okapi"] = None
_upload_counter = 0


_WORD_RE = re.compile(r"[A-Za-z0-9£]+")


def _tokens(s: str) -> List[str]:
    return _WORD_RE.findall(s.lower())


def _dbg(msg: str) -> None:
    if DEBUG:
        print(f"[RAG] {msg}")


def _snippet(full: str, hit: Optional[re.Match], max_chars: int = MAX_SNIP) -> str:
    if not full:
        return ""
    if hit:
        beg = max(0, hit.start() - 200)
    else:
        beg = 0
    raw = full[beg : beg + max_chars]
    clean = re.sub(r"\s+", " ", raw).strip()
    return clean + ("…" if len(raw) == max_chars else "")


def _load_pdf(fp: Path) -> str:
    if PyPDF2 is None:
        return ""
    try:
        reader = PyPDF2.PdfReader(str(fp))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _load_docx(fp: Path) -> str:
    if docx is None:
        return ""
    try:
        d = docx.Document(str(fp))
        return "\n".join(p.text for p in d.paragraphs)
    except Exception:
        return ""


def _load_txt(fp: Path) -> str:
    try:
        return fp.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _load_csv(fp: Path) -> str:
    if pd is None:
        return ""
    try:
        df = pd.read_csv(fp)
        return " ".join(df.astype(str).fillna("").values.ravel().tolist())
    except Exception:
        return ""


def _load_excel(fp: Path) -> str:
    if pd is None:
        return ""
    try:
        df = pd.read_excel(fp)
        return " ".join(df.astype(str).fillna("").values.ravel().tolist())
    except Exception:
        return ""


def _load_parquet(fp: Path) -> str:
    if pd is None:
        return ""
    try:
        df = pd.read_parquet(fp)
        pieces = []
        for col in df.columns:
            if df[col].dtype == "object":
                pieces.append(" ".join(df[col].astype(str).tolist()))
        return " ".join(pieces)
    except Exception:
        return ""


def _rebuild_bm25() -> None:
    global _BM
    if not _BM25_AVAILABLE:
        return
    if not _DOC_TOKS:
        _BM = None
        return
    corpus = list(_DOC_TOKS.values())
    _BM = BM25Okapi(corpus)


def _index_doc(key: str, text: str) -> None:
    _LOCAL_DB[key] = text
    toks = _tokens(text)
    _DOC_TOKS[key] = toks
    seen = set()
    for tok in toks:
        if tok in seen:
            continue
        seen.add(tok)
        _INVERTED.setdefault(tok, []).append(key)
        if len(seen) >= 5000:
            break
    if _BM25_AVAILABLE and len(_DOC_TOKS) % 50 == 0:
        _rebuild_bm25()


def _load_static() -> Tuple[int, int]:
    n_files = n_chars = 0
    if not ROOT_DIR.exists():
        _dbg(f"ROOT_DIR {ROOT_DIR} does not exist")
        return n_files, n_chars

    for fp in ROOT_DIR.rglob("*"):
        if not fp.is_file():
            continue
        ext = fp.suffix.lower()
        text = ""
        try:
            if ext == ".pdf":
                text = _load_pdf(fp)
            elif ext in (".txt", ".md"):
                text = _load_txt(fp)
            elif ext == ".docx":
                text = _load_docx(fp)
            elif ext == ".csv":
                text = _load_csv(fp)
            elif ext in (".xls", ".xlsx"):
                text = _load_excel(fp)
            elif ext == ".parquet":
                text = _load_parquet(fp)
            else:
                continue
            if not text:
                continue
            key = f"static::{fp.relative_to(ROOT_DIR)}"
            _index_doc(key, text)
            n_files += 1
            n_chars += len(text)
        except Exception:
            continue

    _rebuild_bm25()
    _dbg(f"Loaded {n_files} files, {n_chars:,} chars into local DB")
    _dbg(f"Inverted index size: {len(_INVERTED)} tokens")
    return n_files, n_chars


_load_static()


def add_documents(docs: List[str]) -> None:
    """Add user-uploaded chunks into the local DB."""
    global _upload_counter
    for chunk in docs:
        if not chunk:
            continue
        key = f"upload::{_upload_counter}"
        _upload_counter += 1
        _index_doc(key, chunk)
    _rebuild_bm25()


def search_phrase(query: str, k: int = TOPK) -> List[Tuple[str, str]]:
    patt = re.compile(re.escape(query), re.IGNORECASE)
    hits: List[Tuple[str, str]] = []
    for name, text in _LOCAL_DB.items():
        if not text:
            continue
        m = patt.search(text)
        if m:
            hits.append((name, _snippet(text, m)))
            if len(hits) >= k:
                break
    return hits


def search_keywords(query: str, k: int = TOPK) -> List[Tuple[str, str]]:
    q_toks = set(_tokens(query))
    if not q_toks:
        return []
    cand_keys = set()
    for tok in q_toks:
        for key in _INVERTED.get(tok, []):
            cand_keys.add(key)
    scored: List[Tuple[float, str, str]] = []
    for key in cand_keys:
        text = _LOCAL_DB.get(key, "")
        if not text:
            continue
        t_toks = set(_tokens(text[:100_000]))
        score = len(q_toks & t_toks)
        if score <= 0:
            continue
        m = None
        for tok in q_toks:
            m = re.search(r"\b" + re.escape(tok) + r"\b", text, flags=re.I)
            if m:
                break
        scored.append((score, key, _snippet(text, m)))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [(key, snip) for _, key, snip in scored[:k]]


def search_bm25(query: str, k: int = TOPK) -> List[Tuple[str, str]]:
    if not (_BM25_AVAILABLE and _BM):
        return []
    q = _tokens(query)
    scores = _BM.get_scores(q)
    keys = list(_DOC_TOKS.keys())
    ranked = sorted(zip(keys, scores), key=lambda x: x[1], reverse=True)[:k]
    out: List[Tuple[str, str]] = []
    for key, _ in ranked:
        text = _LOCAL_DB.get(key, "")
        first_token = query.split()[0] if query.split() else None
        m = re.search(re.escape(first_token), text, flags=re.I) if first_token else None
        out.append((key, _snippet(text, m)))
    return out


def search_remote(query: str, max_chars: int = MAX_SNIP) -> str:
    if not ENABLE_REMOTE:
        return ""
    try:
        encoded = requests.utils.requote_uri(query)
        search = f"https://www.legislation.gov.uk/all?searchTerm={encoded}&page-size=1"
        res = requests.get(search, headers={"Accept": "application/json"}, timeout=6)
        res.raise_for_status()
        uri = res.json()["results"][0]["uri"]
        xml = requests.get(f"{uri}/data.xml?wrap=true", timeout=6).text
        plain = re.sub(r"<[^>]+>", " ", xml)
        snippet = textwrap.shorten(plain, max_chars, placeholder="…")
        snippet = re.sub(r"\s+", " ", snippet).strip()
        return f"**Context (remote):**\n{snippet}\n\n"
    except Exception:
        return ""


def list_upload_keys() -> List[str]:
    return [k for k in _LOCAL_DB if k.startswith("upload::")]


def get_doc(key: str) -> str:
    return _LOCAL_DB.get(key, "")


def get_index_stats() -> Dict[str, int]:
    return {
        "num_docs": len(_LOCAL_DB),
        "num_tokens": len(_INVERTED),
        "total_chars": sum(len(t) for t in _LOCAL_DB.values()),
        "uploads": sum(1 for k in _LOCAL_DB if k.startswith("upload::")),
        "statics": sum(1 for k in _LOCAL_DB if k.startswith("static::")),
    }
