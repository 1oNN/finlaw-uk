"""Supplementary PDF ingestion — scans the on-disk corpus under
`backend/data/{fca,pra_pdfs}/` and converts each PDF into one or more
provision dicts in the same shape as `ingest_xml.parse_legislation_xml`.

This is a coarser fallback to the formal legislation.gov.uk XML pipeline:
PDFs lack the `<Section>` / `<Regulation>` structure, so citations are
synthesised from the filename and chunks come from a simple text splitter
rather than the source document's own hierarchy. Use this to expand graph
coverage to FCA Handbook sourcebooks and PRA Rulebook material that
isn't available as legislation.gov.uk primary law.

Environment:
    PDF_INGEST_ROOT (default: ./backend/data)
    PDF_INGEST_SUBDIRS (default: fca,pra_pdfs — comma-separated)
    PDF_MAX_CHUNKS_PER_FILE (default: 20)
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List

try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except Exception:
    pdfplumber = None  # type: ignore
    _PDFPLUMBER_AVAILABLE = False

from backend.graph.ingest_xml import _maybe_chunk

PDF_ROOT = Path(os.getenv("PDF_INGEST_ROOT", "./backend/data"))
SUBDIRS = [s.strip() for s in os.getenv("PDF_INGEST_SUBDIRS", "fca,pra_pdfs").split(",") if s.strip()]
MAX_CHUNKS_PER_FILE = int(os.getenv("PDF_MAX_CHUNKS_PER_FILE", "20"))

log = logging.getLogger(__name__)


_FCA_SOURCEBOOKS = {
    "COBS", "BCOBS", "ICOBS", "MCOB", "PROD", "SYSC", "PRIN",
    "DISP", "DTR", "COMP", "COLL", "CONC", "MAR", "FUND",
    "PERG", "EG", "DEPP", "GEN",
}


def _slug(name: str) -> str:
    base = Path(name).stem
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_")
    return base


def _detect_module(filename: str, parent_dir: str) -> tuple[str, str, str]:
    """Return `(module, regulator, cite_prefix)` based on the filename and
    its parent directory. Best-effort — falls back to generic labels."""
    stem = Path(filename).stem.upper()
    if parent_dir == "fca":
        # Handbook sourcebooks are named after their module.
        if stem in _FCA_SOURCEBOOKS:
            return stem, "FCA", stem
        return "FCA", "FCA", "FCA"
    if parent_dir == "pra_pdfs":
        return "PRA", "PRA", "PRA"
    return parent_dir.upper(), "FCA", parent_dir.upper()


def _read_pdf_text(path: Path) -> str:
    """Extract text from a PDF using pdfplumber. Returns empty string on
    failure rather than raising, so one bad file doesn't kill the run."""
    if not _PDFPLUMBER_AVAILABLE:
        raise RuntimeError(
            "pdfplumber is required for PDF ingestion. Install with `pip install pdfplumber`."
        )
    try:
        with pdfplumber.open(str(path)) as pdf:
            pages: List[str] = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t:
                    pages.append(t)
            return "\n\n".join(pages)
    except Exception as e:
        log.warning("pdfplumber failed on %s: %s", path.name, e)
        return ""


def _provision_from_chunk(
    *,
    chunk: str,
    chunk_index: int,
    pdf_path: Path,
    parent_dir: str,
) -> Dict:
    module, regulator, cite_prefix = _detect_module(pdf_path.name, parent_dir)
    slug = _slug(pdf_path.name)
    title = f"{pdf_path.stem} (excerpt {chunk_index + 1})"
    return {
        "id": f"PDF_{slug}_c{chunk_index}",
        "cite": f"{cite_prefix} ({pdf_path.stem} p{chunk_index + 1})",
        "title": title,
        "text": chunk,
        "module": module,
        "domain": "Handbook" if parent_dir == "fca" else "Rulebook",
        "terms": "",
        "threshold": "",
        "deadline": "",
        "document": pdf_path.stem,
        "regulator": regulator,
        "hierarchy_path": f"/{parent_dir}/{pdf_path.name}/chunk{chunk_index}",
    }


def ingest_pdfs(root: Path = None, subdirs: List[str] = None) -> List[Dict]:
    """Walk the configured subdirs and yield provision dicts for every PDF found."""
    root = Path(root) if root else PDF_ROOT
    subdirs = subdirs or SUBDIRS
    out: List[Dict] = []
    if not root.exists():
        log.warning("PDF ingestion root does not exist: %s", root)
        return out

    for sub in subdirs:
        sub_path = root / sub
        if not sub_path.exists():
            log.info("Skipping missing subdir: %s", sub_path)
            continue
        pdf_paths = sorted(p for p in sub_path.rglob("*.pdf") if p.is_file())
        log.info("Found %d PDFs under %s", len(pdf_paths), sub_path)
        for path in pdf_paths:
            text = _read_pdf_text(path)
            if not text or len(text) < 200:
                log.info("Skipping empty/tiny PDF: %s", path.name)
                continue
            chunks = _maybe_chunk(text)
            if MAX_CHUNKS_PER_FILE > 0 and len(chunks) > MAX_CHUNKS_PER_FILE:
                log.info("Capping %s at %d chunks (had %d)", path.name, MAX_CHUNKS_PER_FILE, len(chunks))
                chunks = chunks[:MAX_CHUNKS_PER_FILE]
            for i, chunk in enumerate(chunks):
                out.append(
                    _provision_from_chunk(
                        chunk=chunk, chunk_index=i, pdf_path=path, parent_dir=sub
                    )
                )

    log.info("PDF ingestion total: %d provisions", len(out))
    return out
