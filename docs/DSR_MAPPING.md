# Design Science Research Mapping — FinLaw-UK

The dissertation follows the Peffers et al. (2007) Design Science
Research Methodology (DSRM) — a six-step framework for building and
evaluating IT artefacts. This document maps each step to the concrete
artefact produced.

## DSRM, applied

### Step 1 — Problem identification and motivation
**Problem.** General-purpose LLMs hallucinate when answering UK
financial-regulation questions. Citations to non-existent provisions,
mis-attribution between regulators (FCA vs PRA vs HMT), and silent
substitution of similar-sounding short-forms (e.g. "COBS 4.2" instead
of "COBS 4.2.1R") all undermine the utility of LLM-based compliance
tools.

**Motivation.** Compliance teams cannot trust an LLM whose citations
they have to manually verify on every answer. They also cannot send
privileged material to cloud APIs. There is a gap for a *locally-
deployable, citation-verified* RAG system over UK financial law.

### Step 2 — Define the objectives for a solution
The artefact must:

1. Run entirely on commodity hardware (no cloud API dependencies).
2. Use a structured knowledge graph as the source of ground truth for
   citations.
3. Combine sparse and dense retrieval (so paraphrased questions still
   surface the right legislation).
4. Flag any citation the model emits that does not exist in the graph.
5. Be evaluable against an established RAG metric framework (RAGAS).
6. Expose the architecture for inspection — every step (retrieval,
   graph traversal, verification) is open to the user via the SSE
   `event:meta` audit stream.

### Step 3 — Design and development
Six modular subsystems, each implemented as an importable Python
package:

| Subsystem | Module | Responsibility |
|---|---|---|
| Retrieval | `backend/retrieval/` | Sparse (BM25) + dense (BGE-small + FAISS) + RRF fusion + 5-step fallback cascade |
| Knowledge graph | `backend/graph/` | Neo4j schema, XML + PDF ingestion, cross-reference extraction, 2-hop traversal |
| LLM | `backend/llm/` | Ollama HTTP client (chat path), HF Mistral client (RAGAS judge path) |
| Verification | `backend/verification/` | Citation normalisation, graph-grounded lookup, claim-to-provision trace |
| Ingestion (uploads) | `backend/ingestion/` | Per-format parsers feeding the sparse index |
| Evaluation | `backend/evaluation/` | Lexical metrics (legacy) + RAGAS metrics + combined runner + CSV output |

The design pattern across subsystems is the same: an importable
function-or-class API, environment-driven configuration, graceful
fallback when an external dependency (Neo4j, Ollama, sentence-
transformers) is unavailable. This makes the system testable in
isolation — each stage's tests run without the full stack present.

### Step 4 — Demonstration
The artefact is demonstrated through:

- A working end-to-end chat at `http://localhost:3000`, supporting four
  modes (general / finance / traffic-light / auto).
- A scripted evaluation pass (`python scripts/run_evaluation.py --mode
  both`) that produces a timestamped CSV with per-question scores.
- A SSE `event:meta` envelope on every chat that exposes the
  verification audit, claim trace, citation invalidity list, and
  chain-of-thought elapsed time.

Reviewers can trace any single sentence of any answer back to a
specific `Provision.cite` in Neo4j (or see it flagged as unverified).

### Step 5 — Evaluation
Two metric families, run on the same 80-question balanced set
(`questions_80_balanced.csv`, 8 domains × 10 questions each):

**Lexical (the thesis baseline)**
- Jaccard token overlap (answer vs ground truth)
- ROUGE-L F1 (longest common subsequence)
- Citation match (fraction of expected pipe-separated cites in answer)
- Keyword F1 (token-level F1 vs expected keywords)

**Model-based (RAGAS, added post-thesis)**
- Faithfulness — claims supported by retrieved contexts
- Answer relevancy — answer addresses the question
- Context precision — retrieved contexts were relevant
- Context recall — retrieved contexts covered the ground truth

The local Mistral judge has known biases, which is why both metric
families are reported — lexical for absolute similarity, RAGAS for
relative answer quality.

User validation: the qualitative chapter reports semi-structured
interviews with compliance practitioners (see `QUALITATIVE_SUMMARY.md`)
on RAG shortcomings, verification UI trust, and sourcebook coverage
priorities.

### Step 6 — Communication
- **Thesis** (submitted at University of Bradford, 2025).
- **Codebase** — this repository.
- **Documentation** — `README.md`, `ARCHITECTURE.md`, `RUN.md`,
  `RAGAS_RESULTS.md`, this document.

## Why DSR (and not, say, action research)?

DSR fits because the contribution is an *artefact* (working software
with measurable properties), not a description of a phenomenon or a
field study. The artefact's value is testable: run the evaluation,
inspect the metrics, ablate components and re-evaluate. Action
research, by contrast, would focus on the *process* of changing
compliance practice — a different question.

DSR also makes the iteration loop explicit: each design cycle refines
the artefact based on the evaluation gap surfaced in the previous
iteration — a clean DSR narrative of problem → design → demonstration
→ re-evaluation.

## Limitations of the DSR framing

- **No external comparison.** A real DSR study would benchmark
  FinLaw-UK against an alternative artefact (e.g. cloud LLM with the
  same retrieval). The thesis evaluates the system against itself.
- **Single-developer validation.** DSR usually calls for triangulation
  across multiple developers / reviewers building or critiquing the
  artefact. The qualitative chapter partially addresses this through
  user interviews, but not at the code-architecture level.
- **Evaluation is offline.** No longitudinal study of users adopting
  the artefact in real compliance workflows.

Each is a reasonable boundary for an MSc dissertation; each is
explicitly something the PhD project would extend.
