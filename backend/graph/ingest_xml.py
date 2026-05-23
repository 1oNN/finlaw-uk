"""Ingestion: legislation.gov.uk XML → list of `Provision` dicts.

Fetches the five core UK finance-regulation primary sources, walks the XML
tree to locate section / regulation / article elements, normalises citations
to the short-form convention used elsewhere in the codebase, and chunks any
single block longer than 1500 characters using LangChain's
`RecursiveCharacterTextSplitter` so dense retrieval has digestible units.

Each yielded dict matches the shape consumed by `backend.graph.seed.seed_provisions`:

    {
        'id':            unique key (e.g. 'FSMA2000_s19' or 'MLR2017_reg27_chunk0'),
        'cite':          short citation (e.g. 'FSMA 2000 s.19'),
        'title':         the section/regulation heading,
        'text':          the full text (or one chunk of it),
        'module':        regulator code (FSMA, FCA, HMT, ESMA, ...),
        'domain':        coarse topic tag,
        'terms':         pipe-separated keywords (populated later by extract_xrefs),
        'threshold':     '' (legacy provisions only),
        'deadline':      '' (legacy provisions only),
        'document':      'FSMA 2000' / 'MLR 2017' / ...
        'regulator':     'FCA' / 'HMT' / 'ESMA' / ...
        'hierarchy_path': '/Part 1/Section 19' (best-effort)
    }

Environment:
    LEGISLATION_CACHE_DIR (default: ./data/raw)
    LEGISLATION_FETCH_TIMEOUT (default: 30 seconds)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import requests

try:
    from lxml import etree
    _LXML_AVAILABLE = True
except Exception:
    etree = None  # type: ignore
    _LXML_AVAILABLE = False

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    _SPLITTER_AVAILABLE = True
except Exception:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        _SPLITTER_AVAILABLE = True
    except Exception:
        RecursiveCharacterTextSplitter = None  # type: ignore
        _SPLITTER_AVAILABLE = False


CACHE_DIR = Path(os.getenv("LEGISLATION_CACHE_DIR", "./data/raw"))
FETCH_TIMEOUT = int(os.getenv("LEGISLATION_FETCH_TIMEOUT", "30"))
CHUNK_SIZE = int(os.getenv("INGEST_CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("INGEST_CHUNK_OVERLAP", "150"))

log = logging.getLogger(__name__)


@dataclass
class LegislationSource:
    slug: str
    url: str
    document: str
    short_doc: str
    regulator: str
    domain: str
    cite_kind: str  # 's', 'reg', 'art'


LEGISLATION_SOURCES: List[LegislationSource] = [
    LegislationSource(
        slug="fsma_2000",
        url="https://www.legislation.gov.uk/ukpga/2000/8/data.xml",
        document="FSMA 2000",
        short_doc="FSMA 2000",
        regulator="HMT",
        domain="FSMA",
        cite_kind="s",
    ),
    LegislationSource(
        slug="rao_2001",
        url="https://www.legislation.gov.uk/uksi/2001/544/data.xml",
        document="Regulated Activities Order 2001",
        short_doc="RAO 2001",
        regulator="HMT",
        domain="FSMA",
        cite_kind="art",
    ),
    LegislationSource(
        slug="mlr_2017",
        url="https://www.legislation.gov.uk/uksi/2017/692/data.xml",
        document="Money Laundering Regulations 2017",
        short_doc="MLR 2017",
        regulator="HMT",
        domain="AML",
        cite_kind="reg",
    ),
    LegislationSource(
        slug="psr_2017",
        url="https://www.legislation.gov.uk/uksi/2017/752/data.xml",
        document="Payment Services Regulations 2017",
        short_doc="PSR 2017",
        regulator="HMT",
        domain="Payments",
        cite_kind="reg",
    ),
    LegislationSource(
        slug="uk_mar",
        url="https://www.legislation.gov.uk/eur/2014/596/data.xml",
        document="UK Market Abuse Regulation",
        short_doc="UK MAR",
        regulator="FCA",
        domain="Market",
        cite_kind="art",
    ),
]


def fetch_xml(url: str, slug: str) -> bytes:
    """Return the XML bytes for `url`, using `data/raw/<slug>.xml` as cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{slug}.xml"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        log.info("xml cache hit: %s", cache_path)
        return cache_path.read_bytes()

    log.info("fetching %s", url)
    resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": "FinLaw-UK/0.1"})
    resp.raise_for_status()
    data = resp.content
    cache_path.write_bytes(data)
    return data


def _strip_namespaces(root):
    """In-place strip XML namespaces so XPath stays simple."""
    for elem in root.iter():
        if isinstance(elem.tag, str) and "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]
        for attr in list(elem.attrib):
            if "}" in attr:
                new_attr = attr.split("}", 1)[1]
                elem.attrib[new_attr] = elem.attrib.pop(attr)
    return root


def _text_content(elem) -> str:
    """Concatenate all text content under `elem`, normalising whitespace."""
    parts: List[str] = []
    for piece in elem.itertext():
        if piece:
            parts.append(piece)
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _heading_for(elem) -> str:
    """Title for a P1 element. legislation.gov.uk puts the heading on the
    *parent* `P1group`, not on the `P1` itself, so check the parent first."""
    parent = elem.getparent() if hasattr(elem, "getparent") else None
    if parent is not None and parent.tag == "P1group":
        t = parent.find("./Title")
        if t is not None:
            text = _text_content(t)
            if text:
                return text
    # Some structures put Title inside the P1.
    t = elem.find("./Title")
    if t is not None:
        text = _text_content(t)
        if text:
            return text
    return ""


def _number_for(elem) -> Optional[str]:
    """Section/regulation/article number. legislation.gov.uk Acts often have
    an empty `<Pnumber>` and rely on the `id` attribute (e.g. `section-19`);
    SIs and EUR docs typically have the digit inside `<Pnumber>`."""
    pnum = elem.find("./Pnumber")
    if pnum is not None:
        t = _text_content(pnum)
        if t:
            m = re.search(r"(\d+[A-Za-z]?)", t)
            if m:
                return m.group(1)
    eid = elem.get("id") or ""
    m = re.search(
        r"(?:section|regulation|article|reg|art)[-_]?(\d+[A-Za-z]?)",
        eid,
        re.I,
    )
    if m:
        return m.group(1)
    return None


def _iter_provisions(root) -> Iterator:
    """Yield every `<P1>` element in the document, in document order. P1 is
    the canonical 'provision' tag across all of legislation.gov.uk's
    schemas — Acts call it a section, SIs a regulation, EUR docs an article,
    but the markup is uniform."""
    for elem in root.iter():
        if elem.tag == "P1":
            yield elem


_FILLER_RE = re.compile(r"[\s.…]+")


def _is_repealed_or_empty(text: str) -> bool:
    """legislation.gov.uk renders repealed text as long strings of dots and
    spaces (e.g. '. . . . . . .'). Treat anything whose non-filler content
    is under 40 chars as not worth indexing."""
    if not text:
        return True
    non_filler = _FILLER_RE.sub("", text)
    return len(non_filler) < 40


def _build_cite(src: LegislationSource, number: str) -> str:
    return f"{src.short_doc} {src.cite_kind}.{number}"


def _build_id(src: LegislationSource, number: str) -> str:
    safe_slug = src.slug.upper().replace("_", "")
    return f"{safe_slug}_{src.cite_kind}{number}"


def _maybe_chunk(text: str) -> List[str]:
    """Split long text into <=CHUNK_SIZE pieces using LangChain when available;
    otherwise fall back to a recursive separator-based splitter that mimics
    LangChain's behaviour (paragraph → sentence → word → char)."""
    if len(text) <= CHUNK_SIZE:
        return [text]
    if _SPLITTER_AVAILABLE:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return [c.strip() for c in splitter.split_text(text) if c.strip()]

    # Fallback: try a cascade of separators, fall through to char-level slicing.
    for sep in ("\n\n", "\n", ". ", " "):
        if sep in text:
            return _split_on_separator(text, sep, CHUNK_SIZE, CHUNK_OVERLAP)
    # Last resort — character-level windowing with overlap.
    return _slice_with_overlap(text, CHUNK_SIZE, CHUNK_OVERLAP)


def _split_on_separator(text: str, sep: str, size: int, overlap: int) -> List[str]:
    """Pack `text` split by `sep` into windows of <= `size`. If any single piece
    exceeds `size`, recurse on it with the next coarser separator."""
    pieces = text.split(sep)
    chunks: List[str] = []
    buf = ""
    for piece in pieces:
        candidate = (buf + sep + piece) if buf else piece
        if len(candidate) <= size:
            buf = candidate
            continue
        if buf:
            chunks.append(buf.strip())
        if len(piece) > size:
            # Piece itself is too long — slice it as a last resort.
            chunks.extend(_slice_with_overlap(piece, size, overlap))
            buf = ""
        else:
            buf = piece
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if c]


def _slice_with_overlap(text: str, size: int, overlap: int) -> List[str]:
    if size <= 0:
        return [text]
    step = max(1, size - overlap)
    out: List[str] = []
    i = 0
    while i < len(text):
        chunk = text[i : i + size].strip()
        if chunk:
            out.append(chunk)
        i += step
    return out


def parse_legislation_xml(xml_bytes: bytes, source: LegislationSource) -> Iterator[Dict]:
    """Yield provision dicts (possibly chunked) from one legislation XML payload."""
    if not _LXML_AVAILABLE:
        raise RuntimeError(
            "lxml is required for XML ingestion. Install with `pip install lxml`."
        )
    root = etree.fromstring(xml_bytes)
    _strip_namespaces(root)

    seen_numbers: set[str] = set()
    for elem in _iter_provisions(root):
        number = _number_for(elem)
        if not number:
            continue
        if number in seen_numbers:
            continue
        seen_numbers.add(number)
        title = _heading_for(elem)
        text = _text_content(elem)
        if _is_repealed_or_empty(text):
            continue
        cite = _build_cite(source, number)
        base_id = _build_id(source, number)
        chunks = _maybe_chunk(text)
        for i, chunk in enumerate(chunks):
            yield {
                "id": base_id if len(chunks) == 1 else f"{base_id}_chunk{i}",
                "cite": cite,
                "title": title or f"{source.short_doc} {source.cite_kind}.{number}",
                "text": chunk,
                "module": source.regulator,
                "domain": source.domain,
                "terms": "",
                "threshold": "",
                "deadline": "",
                "document": source.short_doc,
                "regulator": source.regulator,
                "hierarchy_path": f"/{source.short_doc}/{source.cite_kind}.{number}"
                + (f"/chunk{i}" if len(chunks) > 1 else ""),
            }


def ingest_all(sources: Optional[List[LegislationSource]] = None) -> List[Dict]:
    """Fetch + parse every configured legislation source. Returns the combined
    list of provision dicts. Counts are logged per-source."""
    sources = sources or LEGISLATION_SOURCES
    out: List[Dict] = []
    for src in sources:
        try:
            xml = fetch_xml(src.url, src.slug)
        except Exception as e:
            log.warning("Failed to fetch %s (%s): %s", src.slug, src.url, e)
            continue
        try:
            provisions = list(parse_legislation_xml(xml, src))
        except Exception as e:
            log.warning("Failed to parse %s: %s", src.slug, e)
            continue
        log.info("%s: %d provisions parsed", src.short_doc, len(provisions))
        out.extend(provisions)
    return out
