"""Tests for the Stage 3 graph layer.

Covers:
    - Cross-reference regex matching (statutory + FCA Handbook patterns)
    - Citation normalisation
    - Self-reference and dangling-target filtering in `extract_all_by_id`
    - Schema constants are well-formed
    - 2-hop traversal returns the expected shape when Neo4j is unavailable
      (clean skip / empty result, no crash)
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from backend.graph.extract_xrefs import (
    extract_all_by_id,
    extract_from_clause,
    normalise_cite,
)
from backend.graph.schema import (
    KNOWN_DOCUMENTS,
    KNOWN_REGULATORS,
    NODE_LABELS,
    RELATIONSHIP_TYPES,
)


def test_extract_fsma_section():
    cites = extract_from_clause("This is subject to FSMA 2000 s.19 and FSMA s.22.")
    assert "FSMA 2000 s.19" in cites
    assert "FSMA 2000 s.22" in cites


def test_extract_handles_section_word_variants():
    cites = extract_from_clause("FSMA 2000 section 21, as well as FSMA s.27.")
    assert "FSMA 2000 s.21" in cites
    assert "FSMA 2000 s.27" in cites


def test_extract_mlr_psr_rao():
    text = (
        "See MLR 2017 reg.27 for CDD and PSR 2017 reg.77 for liability. "
        "Cross-reference: RAO 2001 art.5."
    )
    cites = extract_from_clause(text)
    assert "MLR 2017 reg.27" in cites
    assert "PSR 2017 reg.77" in cites
    assert "RAO 2001 art.5" in cites


def test_extract_uk_mar_variants():
    cites = extract_from_clause("Under UK MAR art.17 and UK-MAR article 18 …")
    assert "UK MAR art.17" in cites
    assert "UK MAR art.18" in cites


def test_extract_fca_handbook():
    cites = extract_from_clause("Refer to COBS 4.2.1R, SYSC 10, and PRIN 12.")
    assert "COBS 4.2.1R" in cites
    assert "SYSC 10" in cites
    assert "PRIN 12" in cites


def test_extract_normalises_handbook_suffix_case():
    cites = extract_from_clause("see cobs 4.2.1r — fair, clear")
    assert "COBS 4.2.1R" in cites


def test_extract_deduplicates_within_one_clause():
    cites = extract_from_clause(
        "FSMA 2000 s.19 … and then again FSMA s.19 because it is fundamental."
    )
    assert cites.count("FSMA 2000 s.19") == 1


def test_normalise_cite_all_acts():
    assert normalise_cite("FSMA", "19") == "FSMA 2000 s.19"
    assert normalise_cite("RAO", "5") == "RAO 2001 art.5"
    assert normalise_cite("MLR", "27") == "MLR 2017 reg.27"
    assert normalise_cite("PSR", "77") == "PSR 2017 reg.77"
    assert normalise_cite("UK MAR", "17") == "UK MAR art.17"
    assert normalise_cite("COBS", "4.2.1r") == "COBS 4.2.1R"


def test_extract_all_filters_self_and_unknown_targets():
    provisions = [
        {"id": "A", "cite": "FSMA 2000 s.19",
         "text": "See FSMA 2000 s.22 and an irrelevant FSMA 2000 s.19 self-ref. Also FSMA 2000 s.999."},
        {"id": "B", "cite": "FSMA 2000 s.22",
         "text": "Mentions MLR 2017 reg.27 only."},
        # No node for "MLR 2017 reg.27" exists in this provision set
    ]
    pairs = extract_all_by_id(provisions)
    pair_set = set(pairs)
    assert ("A", "FSMA 2000 s.22") in pair_set  # valid forward link
    assert ("A", "FSMA 2000 s.19") not in pair_set  # self-ref filtered
    assert ("A", "FSMA 2000 s.999") not in pair_set  # dangling target filtered
    assert ("B", "MLR 2017 reg.27") not in pair_set  # not in known set


def test_extract_all_returns_unique_pairs():
    provisions = [
        {"id": "A", "cite": "FSMA 2000 s.19", "text": "FSMA 2000 s.22 FSMA s.22"},
        {"id": "B", "cite": "FSMA 2000 s.22", "text": "(empty target)"},
    ]
    pairs = extract_all_by_id(provisions)
    # Same source/target should produce a single tuple even if cited multiple times
    assert pairs.count(("A", "FSMA 2000 s.22")) == 1


def test_schema_constants_well_formed():
    assert "Provision" in NODE_LABELS
    assert "Regulator" in NODE_LABELS
    assert "Document" in NODE_LABELS
    assert "CITES" in RELATIONSHIP_TYPES
    assert "ISSUED_BY" in RELATIONSHIP_TYPES
    assert "PART_OF" in RELATIONSHIP_TYPES
    assert any(r["name"] == "FCA" for r in KNOWN_REGULATORS)
    assert any(d["name"] == "FSMA 2000" for d in KNOWN_DOCUMENTS)


def test_neighbors_2hop_returns_empty_when_session_unavailable(monkeypatch):
    from backend.graph import traversal

    @contextmanager
    def fake_session():
        yield None

    monkeypatch.setattr(traversal, "get_session", fake_session)
    result = traversal.neighbors_2hop(["FSMA 2000 s.19"])
    assert result["related_cites"] == []
    # `must_terms` is reset to an empty list (not a set) when no session is available
    assert result["must_terms"] == []


def test_neighbors_2hop_returns_empty_for_empty_input(monkeypatch):
    from backend.graph import traversal

    result = traversal.neighbors_2hop([])
    assert result == {"must_terms": [], "related_cites": [], "hops": {}}
