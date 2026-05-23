"""Tests for the Stage 4 verification layer.

Covers:
    - extract_claims skipping rules
    - trace_claim_to_provision overlap scoring
    - verify_answer happy path with a mocked graph
    - verify_answer 'all_grounded=False' when the graph rejects a cite
    - verify_answer fail-open when the graph is unavailable
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, List

import pytest

from backend.verification import claim_trace, graph_verify
from backend.verification.claim_trace import (
    extract_claims,
    trace_claim_to_provision,
)
from backend.verification.graph_verify import verify_answer


# ---------- claim_trace ----------

def test_extract_claims_skips_headers_and_source():
    answer = (
        "## A header\n"
        "The general prohibition makes it an offence to carry on a regulated activity unless authorised.\n"
        "Financial promotions must be fair, clear and not misleading.\n"
        "Source: FSMA 2000 s.19 | COBS 4.2.1R\n"
        "> A warning blockquote.\n"
        "- A bullet that is also a complete sentence with a verb."
    )
    claims = extract_claims(answer)
    assert any("general prohibition" in c.lower() for c in claims)
    assert any("financial promotions must be fair" in c.lower() for c in claims)
    assert not any(c.lower().startswith("source") for c in claims)
    assert not any(c.startswith("##") for c in claims)
    assert not any(c.startswith(">") for c in claims)


def test_extract_claims_drops_short_fragments():
    answer = "Short.\nA second sentence that is plainly long enough to count as a claim."
    claims = extract_claims(answer, min_length=25)
    assert len(claims) == 1
    assert "long enough" in claims[0]


def test_trace_claim_to_provision_picks_best_overlap():
    provision_texts = {
        "FSMA 2000 s.19": "general prohibition offence regulated activity authorised exempt person",
        "COBS 4.2.1R": "financial promotion fair clear not misleading communication",
    }
    claim = "The general prohibition makes it an offence to carry on a regulated activity."
    match = trace_claim_to_provision(claim, provision_texts)
    assert match is not None
    assert match["cite"] == "FSMA 2000 s.19"
    assert match["score"] >= 3


def test_trace_claim_returns_none_when_no_overlap():
    match = trace_claim_to_provision(
        "totally unrelated topic about gardening tools",
        {"FSMA 2000 s.19": "general prohibition regulated activity"},
    )
    assert match is None


# ---------- verify_answer ----------

class _FakeSession:
    """Tiny in-memory stub that pretends to be a Neo4j session for the
    two queries graph_verify actually issues."""

    def __init__(self, known_cites: List[str]):
        self.known = set(known_cites)

    def run(self, cypher, **params):
        if "UNWIND $cites" in cypher:
            return _FakeRunResult(
                [{"cite": c} for c in params["cites"] if c in self.known]
            )
        if cypher.strip().startswith("MATCH (p:Provision {cite: $cite})"):
            single = {"id": "stub"} if params.get("cite") in self.known else None
            return _FakeRunResult([], single=single)
        return _FakeRunResult([])

    def close(self):
        pass


class _FakeRunResult:
    def __init__(self, rows, single=None):
        self._rows = rows
        self._single = single

    def __iter__(self):
        return iter(self._rows)

    def data(self):
        return list(self._rows)

    def single(self):
        return self._single


@contextmanager
def _fake_session_ctx(known):
    yield _FakeSession(known)


def test_verify_answer_all_grounded(monkeypatch):
    known = ["FSMA 2000 s.19", "COBS 4.2.1R"]
    monkeypatch.setattr(graph_verify, "get_session", lambda: _fake_session_ctx(known))

    answer = (
        "The general prohibition is at FSMA 2000 s.19. "
        "Financial promotions are governed by COBS 4.2.1R."
    )
    result = verify_answer(answer, context_cites=known)
    assert result["all_grounded"] is True
    assert set(result["verified"]) == {"FSMA 2000 s.19", "COBS 4.2.1R"}
    assert result["unverified"] == []


def test_verify_answer_flags_unknown_citation(monkeypatch):
    known = ["FSMA 2000 s.19"]
    monkeypatch.setattr(graph_verify, "get_session", lambda: _fake_session_ctx(known))

    answer = "Refer to FSMA 2000 s.19 and to FAKEREG 99.99."
    result = verify_answer(answer, context_cites=known)
    # FSMA 2000 s.19 matches; FAKEREG 99.99 does not match any pattern at all,
    # so it shouldn't even be extracted. But UK MAR-style would. Try a real
    # short-form that nonetheless isn't in the graph:
    answer = "Refer to FSMA 2000 s.19 and FSMA 2000 s.9999."
    result = verify_answer(answer, context_cites=known)
    assert result["all_grounded"] is False
    assert "FSMA 2000 s.19" in result["verified"]
    assert "FSMA 2000 s.9999" in result["unverified"]


def test_verify_answer_flags_hallucinated_context(monkeypatch):
    known = ["FSMA 2000 s.19", "COBS 4.2.1R"]
    monkeypatch.setattr(graph_verify, "get_session", lambda: _fake_session_ctx(known))

    # Both citations exist in the graph, but COBS 4.2.1R was never retrieved.
    answer = "FSMA 2000 s.19 and COBS 4.2.1R both apply."
    result = verify_answer(answer, context_cites=["FSMA 2000 s.19"])
    assert result["all_grounded"] is True
    assert result["all_retrieved"] is False
    assert "COBS 4.2.1R" in result["hallucinated_context"]


def test_verify_answer_no_citations_in_text():
    result = verify_answer("This answer mentions nothing legal at all.")
    assert result["all_grounded"] is True
    assert result["all_retrieved"] is True
    assert result["verified"] == []
    assert result["unverified"] == []
    assert result["note"] == "no_citations"


def test_verify_answer_graph_unavailable_fails_open(monkeypatch):
    @contextmanager
    def no_session():
        yield None

    monkeypatch.setattr(graph_verify, "get_session", no_session)
    result = verify_answer("FSMA 2000 s.19 applies.", context_cites=["FSMA 2000 s.19"])
    assert result["all_grounded"] is True
    assert result["note"] == "graph_unavailable"


# ---------- trace_all wiring ----------

def test_trace_all_uses_provided_provision_texts():
    answer = "The general prohibition makes it an offence to carry on a regulated activity unless authorised."
    provision_texts = {
        "FSMA 2000 s.19": "general prohibition offence regulated activity authorised exempt",
        "COBS 4.2.1R": "financial promotion fair clear not misleading",
    }
    records = claim_trace.trace_all(
        answer, cites=list(provision_texts), provision_texts=provision_texts
    )
    assert records
    best = records[0]["best_match"]
    assert best is not None
    assert best["cite"] == "FSMA 2000 s.19"
