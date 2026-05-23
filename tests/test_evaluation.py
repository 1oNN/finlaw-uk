"""Tests for the Stage 5 evaluation runner.

Covers the cheap pure-Python pieces — question loading, lexical metrics,
LexicalScores dataclass. Anything that requires a running Ollama server
or the `ragas` library is skipped here and exercised end-to-end by
`python scripts/run_evaluation.py --sample 5 --mode ragas`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.evaluation.ragas_eval import EvalRecord, load_questions
from backend.evaluation.runner import (
    LexicalScores,
    _citation_match,
    _jaccard,
    _keyword_f1,
    _rouge_l,
    compute_lexical,
)


def test_jaccard_basic():
    assert _jaccard("a b c", "b c d") == pytest.approx(2 / 4, abs=1e-6)
    assert _jaccard("", "") == 0.0
    assert _jaccard("same words", "same words") == pytest.approx(1.0)


def test_rouge_l_returns_zero_for_empty():
    assert _rouge_l("", "anything") == 0.0
    assert _rouge_l("anything", "") == 0.0


def test_rouge_l_high_for_near_identical():
    score = _rouge_l(
        "the general prohibition is at FSMA s.19",
        "the general prohibition is at FSMA s.19",
    )
    assert score > 0.9


def test_citation_match_counts_expected_cites():
    answer = "Source: FSMA 2000 s.19 | COBS 4.2.1R"
    expected = "FSMA 2000 s.19|COBS 4.2.1R|MLR 2017 reg.27"
    score = _citation_match(answer, expected)
    assert score == pytest.approx(2 / 3)


def test_citation_match_empty_expected():
    assert _citation_match("anything", "") == 0.0


def test_keyword_f1_counts_token_hits():
    answer = "Customer due diligence is mandatory for relevant persons."
    expected = "due diligence|customer|mandatory|cdd"
    score = _keyword_f1(answer, expected)
    # 'due', 'diligence', 'customer', 'mandatory' are present → some F1
    assert score > 0.0


def test_keyword_f1_empty_expected_is_zero():
    assert _keyword_f1("anything", "") == 0.0


def test_compute_lexical_assembles_all_four():
    rec = EvalRecord(
        qid="q1",
        domain="FSMA",
        complexity="basic",
        question="What is the general prohibition?",
        ground_truth="The general prohibition makes it an offence to carry on a regulated activity unless authorised or exempt.",
        expected_citations="FSMA 2000 s.19|RAO 2001 art.5",
        answer="The general prohibition (FSMA 2000 s.19) makes it an offence to carry on a regulated activity unless authorised or exempt.",
    )
    scores = compute_lexical(rec, expected_keywords="general|prohibition|regulated|authorised")
    assert isinstance(scores, LexicalScores)
    assert scores.jaccard > 0.5
    assert scores.rouge_l > 0.5
    assert scores.citation_match == pytest.approx(0.5)  # only FSMA s.19, not RAO art.5
    assert scores.keyword_f1 > 0.0


def test_load_questions_smoke(tmp_path):
    csv = tmp_path / "q.csv"
    csv.write_text(
        "id,domain,complexity,question,gold_answer,expected_citations,expected_keywords\n"
        "q1,FSMA,basic,What is X?,Answer X.,FSMA 2000 s.19,foo|bar\n"
        "q2,AML,intermediate,What is Y?,Answer Y.,MLR 2017 reg.27,baz\n",
        encoding="utf-8",
    )
    records = load_questions(csv)
    assert len(records) == 2
    assert records[0].qid == "q1"
    assert records[0].domain == "FSMA"
    assert records[1].ground_truth == "Answer Y."


def test_load_questions_sample(tmp_path):
    csv = tmp_path / "q.csv"
    rows = ["id,domain,complexity,question,gold_answer,expected_citations,expected_keywords"]
    for i in range(5):
        rows.append(f"q{i},FSMA,basic,Q{i}?,Answer{i}.,FSMA 2000 s.{i},kw{i}")
    csv.write_text("\n".join(rows), encoding="utf-8")
    records = load_questions(csv, sample=3)
    assert len(records) == 3
    assert records[0].qid == "q0"
    assert records[2].qid == "q2"


def test_eval_record_defaults():
    r = EvalRecord(
        qid="x",
        domain="d",
        complexity="c",
        question="?",
        ground_truth="!",
        expected_citations="",
    )
    assert r.answer == ""
    assert r.contexts == []
    assert r.runtime_s == 0.0
    assert r.ragas_faithfulness is None
