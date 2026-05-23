"""Cross-reference extraction.

Scans free text (a provision's body) for inline citations to other UK
financial-regulation provisions and returns them in canonical short-form,
matching the `cite` property used elsewhere in the codebase (e.g.
'FSMA 2000 s.19', 'MLR 2017 reg.27', 'COBS 4.2.1R', 'UK MAR art.17').

Used by `backend.graph.seed` to populate `:CITES` edges after the base
provision graph has been built.

Coverage:
    - Primary Acts:        FSMA 2000 s.<N>
    - Regulated Activities Order 2001:  RAO 2001 art.<N>
    - Statutory Instruments: MLR 2017 reg.<N>, PSR 2017 reg.<N>
    - Retained EU:         UK MAR art.<N>
    - FCA Handbook:        COBS / SYSC / PRIN / CONC / ICOBS / MCOB / PROD
                           / DISP / COMP / COLL / DTR / FUND / MAR / BCOBS
                           with optional sub-numbering (e.g. '4.2.1R')

Patterns are tolerant of common writing variants: 'section' vs 's.',
'regulation' vs 'reg.', extra whitespace, mixed case.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Set, Tuple

# FCA Handbook sourcebooks — short prefixes that act like a citation root.
_HANDBOOK_PREFIXES = (
    "BCOBS", "COBS", "SYSC", "PRIN", "CONC", "ICOBS", "MCOB", "PROD",
    "DISP", "COMP", "COLL", "DTR", "FUND", "MAR",
)
_HANDBOOK_GROUP = "|".join(_HANDBOOK_PREFIXES)


# Each entry: (compiled regex with one capture group for the number, act_label)
# The act_label is what `normalise_cite` keys off of.
_STATUTORY_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bFSMA\s*(?:2000)?\s*(?:section|sec|s)\.?\s*(\d+[A-Za-z]?)\b", re.I), "FSMA"),
    (re.compile(r"\bRAO\s*(?:2001)?\s*(?:article|art)\.?\s*(\d+[A-Za-z]?)\b", re.I), "RAO"),
    (re.compile(r"\bMLR\s*(?:2017)?\s*(?:regulation|reg)\.?\s*(\d+[A-Za-z]?)\b", re.I), "MLR"),
    (re.compile(r"\bPSR\s*(?:2017)?\s*(?:regulation|reg)\.?\s*(\d+[A-Za-z]?)\b", re.I), "PSR"),
    (re.compile(r"\bUK[\s_-]?MAR\s*(?:article|art)\.?\s*(\d+[A-Za-z]?)\b", re.I), "UK MAR"),
]

# FCA Handbook short form. The book and number are captured as named groups
# (rather than positional) because the act label and the number both come
# from the match, not from an external mapping.
_HANDBOOK_RULE: re.Pattern = re.compile(
    rf"\b(?P<book>{_HANDBOOK_GROUP})\s+(?P<num>\d+(?:\.\d+)*[A-Za-z]?(?:R|G)?)\b",
    re.I,
)


# Within a single legislative document, cross-references typically omit the
# Act name ("section 22" instead of "FSMA 2000 s.22"). When we know the
# source document we can apply these context-aware patterns to recover
# those internal links.
_CONTEXT_PATTERNS: Dict[str, Tuple[Tuple[re.Pattern, str], ...]] = {
    "FSMA 2000": (
        (re.compile(r"\b(?:section|sec|s)\.?\s*(\d+[A-Za-z]?)\b", re.I), "FSMA"),
    ),
    "RAO 2001": (
        (re.compile(r"\b(?:article|art)\.?\s*(\d+[A-Za-z]?)\b", re.I), "RAO"),
    ),
    "MLR 2017": (
        (re.compile(r"\b(?:regulation|reg)\.?\s*(\d+[A-Za-z]?)\b", re.I), "MLR"),
    ),
    "PSR 2017": (
        (re.compile(r"\b(?:regulation|reg)\.?\s*(\d+[A-Za-z]?)\b", re.I), "PSR"),
    ),
    "UK MAR": (
        (re.compile(r"\b(?:article|art)\.?\s*(\d+[A-Za-z]?)\b", re.I), "UK MAR"),
    ),
}


def _norm_handbook_num(num: str) -> str:
    """Uppercase the trailing R/G/letter suffix on FCA Handbook citations
    so 'COBS 4.2.1r' and 'COBS 4.2.1R' produce the same cite."""
    return re.sub(r"([A-Za-z])$", lambda m: m.group(1).upper(), num)


def normalise_cite(act_label: str, number: str) -> str:
    """Map (act_label, number) to the canonical short-form `cite` used by
    the graph. `act_label` is the upper-case key returned by the rule
    table or by the FCA Handbook pattern."""
    upper = act_label.upper().replace("_", " ").replace("-", " ").strip()
    if upper == "FSMA":
        return f"FSMA 2000 s.{number}"
    if upper == "RAO":
        return f"RAO 2001 art.{number}"
    if upper == "MLR":
        return f"MLR 2017 reg.{number}"
    if upper == "PSR":
        return f"PSR 2017 reg.{number}"
    if upper in ("UK MAR", "UKMAR"):
        return f"UK MAR art.{number}"
    if upper in _HANDBOOK_PREFIXES:
        return f"{upper} {_norm_handbook_num(number)}"
    return f"{upper} {number}"


def extract_from_clause(text: str, source_document: str = None) -> List[str]:
    """Return the unique set of canonical cites mentioned in `text`,
    preserving first-appearance order.

    If `source_document` is provided (e.g. 'FSMA 2000'), bare references
    like 'section 22' inside the text are interpreted as references to
    *that* Act and normalised accordingly. Without `source_document` only
    fully-qualified citations are picked up (e.g. 'FSMA 2000 s.22')."""
    if not text:
        return []
    seen: Set[str] = set()
    out: List[str] = []
    for pat, label in _STATUTORY_RULES:
        for m in pat.finditer(text):
            number = m.group(1)
            cite = normalise_cite(label, number)
            if cite not in seen:
                seen.add(cite)
                out.append(cite)
    for m in _HANDBOOK_RULE.finditer(text):
        book = m.group("book").upper()
        number = m.group("num")
        cite = normalise_cite(book, number)
        if cite not in seen:
            seen.add(cite)
            out.append(cite)
    if source_document and source_document in _CONTEXT_PATTERNS:
        for pat, label in _CONTEXT_PATTERNS[source_document]:
            for m in pat.finditer(text):
                number = m.group(1)
                cite = normalise_cite(label, number)
                if cite not in seen:
                    seen.add(cite)
                    out.append(cite)
    return out


def extract_all_by_id(provisions: Sequence[Dict]) -> List[Tuple[str, str]]:
    """For every provision, scan its text for cross-references and emit
    `(source_id, target_cite)` pairs.

    Source matched by ID (unique). Target matched by cite (may be shared
    across chunks — Cypher MERGE on the relationship pattern will resolve
    one representative).

    Self-references and references to cites absent from `provisions` are
    filtered out so the graph never grows a dangling :CITES edge.
    """
    known_cites: Set[str] = {p.get("cite", "") for p in provisions if p.get("cite")}
    seen: Set[Tuple[str, str]] = set()
    out: List[Tuple[str, str]] = []
    for p in provisions:
        src_id = p.get("id") or ""
        src_cite = p.get("cite") or ""
        text = p.get("text") or ""
        source_doc = p.get("document") or ""
        if not src_id or not text:
            continue
        for target in extract_from_clause(text, source_document=source_doc):
            if target == src_cite:
                continue
            if target not in known_cites:
                continue
            key = (src_id, target)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out
