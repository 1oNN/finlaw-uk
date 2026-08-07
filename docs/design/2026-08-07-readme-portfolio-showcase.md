# Design — README as portfolio showcase

**Date:** 2026-08-07
**Goal:** Rebuild `README.md` as the primary artifact a hiring manager or PhD
supervisor reads, and raise the surrounding repo to match.

## Problem

The current README is a competent internal index: a tech table, a documentation
list, and a known-limitations section. It describes the implementation but never
states the contribution, shows nothing of the running system, and buries the
strongest empirical asset in the repo — a four-arm retrieval ablation sitting in
`data/eval_results/ablation.csv` that no reader will ever find.

Three concrete gaps:

1. **No hook.** "A graph-augmented RAG chatbot for UK financial regulation"
   describes what was built, not why it matters or what is novel about it.
2. **No evidence.** Zero screenshots, zero charts. A RAG system that streams
   grounded answers with verified citations is invisible as plain text.
3. **No repo signals.** `License: TBD`, no CI, no social preview. Each is a
   small negative signal to the exact audience this project is being shown to.

## Audience

Two readers, in priority order:

- **AIML hiring managers** skimming for 15–30 seconds, looking for: does this
  person ship real systems, do they measure things, can they reason about
  failure.
- **PhD supervisors / admissions readers** reading for 5 minutes, looking for:
  methodological rigour, honest treatment of negative results, controlled
  comparison.

Both are served by the same document if the top third is skimmable and the
middle third rewards depth. The design below assumes no reader runs the code.

## Decisions taken

| Decision | Choice | Rationale |
|---|---|---|
| Interactivity | README-only, richly built | Renders identically on GitHub web, mobile, and in search previews. No build step to rot. |
| Charts | Committed SVGs, light + dark variants | GitHub supports `<picture>` + `prefers-color-scheme`. Reproducible from a script. |
| Demo assets | Real screenshots + streaming GIF | Nothing else conveys a live grounded answer. |
| Evaluation framing | Two-tier: measurable wins first, integrity section below | Skimmers see competence; close readers see rigour. Omitting the gap entirely would be caught. |
| Hero framing | Trust / verification angle | The verification loop and refusal gate are the genuine differentiators. |
| Repo polish | LICENSE + CI + social preview + metadata | Each is a cheap, durable credibility signal. |

## Positioning

Hero line:

> A retrieval system for UK financial regulation that can prove its citations
> exist — and refuses to answer when it can't.

Supported by three claims, each of which the codebase actually backs:

1. **Graph-verified citations.** `backend/verification/graph_verify.py` resolves
   every citation in a generated answer against Neo4j. Citations with no
   corresponding `Provision` node are flagged to the user rather than passed
   through silently.
2. **Refuses over guesses.** A top-dense-similarity gate (default 0.25) declines
   to answer when retrieval is weak. The evaluation quantifies exactly what this
   costs and why it is the correct trade.
3. **Fully local.** Mistral 7B-Instruct via Ollama, FAISS on disk, Neo4j in
   Docker. No query about a client's regulatory exposure leaves the machine —
   which is the actual deployment constraint in regulated finance.

The MSc credential moves to a single line under the badge row. It is a
credential, not the frame.

## Document structure

```
Hero            wordmark · tagline · badge row · three-claim bullets
Demo            streaming GIF; screenshots of sources panel + verification
Problem         4 sentences — a fabricated statutory cite is a compliance incident
Architecture    Mermaid flowchart + Mermaid request-lifecycle sequence
Under the hood  <details> per subsystem: retrieval · graph · verification
Results         Chart 1 domain coverage (n=110, hero) · Chart 2 ablation
                Chart 3 measurability · Chart 4 refusal
                Measurement integrity — the gap, root cause, candidate fix
Tech stack      layer / tech / where it lives
Quickstart      <details> per OS
Repo map · Testing · Limitations · Docs index · License
```

Ordering principle: every section above "Tech stack" answers *why should I care*;
everything below answers *how do I use it*. Skimmers never reach the second half,
which is fine — it is not written for them.

## Charts

One generator script, `scripts/make_readme_charts.py`, reads from
`data/eval_results/` and writes SVG pairs to `docs/assets/`. Committed output,
committed script. A reviewer can rerun it and reproduce every figure — that
reproducibility is itself the research signal, independent of the numbers.

Rendering uses `<picture>` with `media="(prefers-color-scheme: dark)"` so figures
are legible in both GitHub themes. Palette anchors to the app's navy tokens so
README and product read as one system.

### Chart 1 — Coverage across regulatory domains (hero)

Source: `backend/results_full/run_20250902_002303/eval_results.csv` (n=110).

This run was missed in the first pass of this spec and is the strongest
quantitative asset in the repository. Composition: 80 factual questions + 20
document tasks + 10 case scenarios = 110 items, spanning ten regulatory domains
(PSR, UK MAR, DISP each 12; ICOBS, MLR, RAO, PRIN each 11; FSMA, COMP, COBS each
10) and three complexity tiers (25 basic, 55 intermediate, 30 advanced).

**`source_accuracy` and `citation_quality` are excluded from this chart and from
the README.** They are not correctness measures.
`scripts/run_eval_and_charts.py::score_citations` awards a flat `0.85` whenever
the answer contains any string matching the citation regex, verified or not:

```python
acc = 0.85 if any_tok else 0.0
```

103 of the 110 rows sit at exactly 0.85, 4 at 0.00, 3 at 1.00 — which is the
whole of the 0.8232 mean. `citation_quality` is built the same way
(`0.6 + 0.1` per regex hit), putting 67 rows on exactly 0.9. Both collapse under
a minute of reading, and the generating script is committed, so neither may
appear as a result.

Note also that `backend/evaluation/lexical.py` defines these metrics
differently (line 244 additionally requires `meta_ok is True`) and did not
produce this CSV — its `evaluate_qa` emits 10 columns and names one
`model_answer`, while the CSV carries 25 including `answer` and `latency_ms`.
Two evaluators, two definitions. Always confirm which one wrote a results file.

Usable figures from this run: `semantic_similarity` 0.6724,
`legal_completeness` 0.6818, `keyword_f1_score` 0.6806, latency median 5 768 ms
/ p90 5 977 ms. These are computed against gold answers and are defensible.

Rendering: domain × complexity heatmap on `legal_completeness`, with a marginal
bar for per-domain n so no reader mistakes a 10-item cell for a large sample.
The chart carries breadth of regulatory coverage, which no other figure conveys.

The honest headline from this run is the **graph-verified citation rate of
3/110**. It is stated plainly as the finding that motivated the citation
normaliser, re-ranker and refusal gate built afterwards. There is no matching
"after" measurement at this scale — that gap is named as further work rather
than filled with an estimate.

### Chart 2 — Retrieval ablation

Source: `data/eval_results/ablation.csv` (four arms, n=10 each).

| arm | recall | faithfulness | relevancy | precision | s/q |
|---|---|---|---|---|---|
| `4a-rrf-baseline` | 0.60 | 0.5833 | 0.2774 | 0.8267 | 7.50 |
| `4a-dense-only` | 0.70 | 0.6500 | 0.0973 | 0.7195 | 8.00 |
| `4a-bm25-only` | 0.70 | 0.5217 | 0.2818 | 0.8258 | 8.28 |
| `4b-rrf-rerank` | 0.60 | 0.6333 | 0.1919 | 0.8400 | 10.21 |

Grouped bars across the four quality metrics, with seconds-per-question on a
paired panel so the latency cost of reranking is visible next to its quality
effect. This is a controlled comparison holding the question set fixed while
varying one retrieval component — the most defensible empirical claim in the
project, and currently invisible to any reader.

Honest reading to state in prose: no arm dominates. Reranking buys precision
(0.8267 → 0.8400) and faithfulness at a 36% latency cost; dense-only wins recall
but collapses on relevancy. The README says this plainly rather than declaring a
winner.

### Chart 3 — Measurability lift

Slope chart, `context_precision` valid rows: 8/80 → 77/80 on the balanced set,
1/10 → 9/10 on the curated set. Annotated so the axis reads as *rows the metric
could be computed for*, not *score*.

The mean is flat (0.9056 → 0.8974). The win is coverage, driven by the
per-record loop and 180 s `RunConfig` in commit `9ad4225`. Labelling this as a
coverage win rather than a quality win is the point of including it.

### Chart 4 — Refusal-gate trade-off

Grouped bars, `answer_relevancy` by row group:

| group | rows | relevancy |
|---|---|---|
| All 80 | 80 | 0.4078 |
| Real curated Q1–Q10 | 10 | 0.8023 |
| Template stubs Q11–Q80 | 70 | 0.3506 |
| Non-refusal rows only | 49 | 0.6575 |

This chart exists to explain a 23-point headline drop. Thirty of eighty rows are
correct refusals; RAGAS scores a refusal at 0 relevancy by construction because
the refusal text does not echo the question. Excluding refusals the mean is
0.6575 against a baseline of 0.6412 — the baseline scored higher on the headline
by confabulating on nonsense questions. The chart turns the worst-looking number
in the project into its most defensible design decision.

### Measurement integrity section

Immediately below the charts, not hidden in a `<details>`:

- `ragas_faithfulness` and `ragas_context_recall` return NaN on every current
  row, on both `ragas==0.2.15` and `0.4.3`.
- They are **un-measurable, not degraded**. The Mistral judge produces correct
  NLI output under serial probing; `RunConfig(max_workers=4)` against a single
  Ollama instance corrupts it.
- Candidate mitigation `RAGAS_MAX_WORKERS=1` is documented and untested.
- 70 of 80 balanced-set rows are template stubs with semantically empty gold
  answers; the curated 10 is the headline set.

Stating this above the fold is a deliberate choice. A reader who finds it
themselves in a linked doc trusts the rest of the numbers less, not more.

## Demo capture

Sequence, with the cold-start hazard handled first:

1. `docker compose up -d` — Neo4j.
2. Start Ollama; **pre-warm `mistral:7b-instruct` with a throwaway generation.**
   Cold first-byte latency through Werkzeug SSE has been observed above 200 s;
   recording before warm-up would produce a GIF of a spinner.
3. Start Flask backend and React frontend.
4. Playwright Chromium (`npx playwright install chromium`) drives a real
   question from the curated set — one whose citations verify cleanly.
5. Screenshot every ~350 ms through the stream.
6. Pillow assembles an optimised GIF: ~800 px wide, target < 5 MB, final frame
   held ~2 s so the completed answer is readable.

`ffmpeg` is absent and not required — Pillow 12.2 writes animated GIFs directly.

Stills to capture alongside: sources panel with graph-derived citations, and the
verification state on an answer.

**Fallback:** if the stack will not come up cleanly, ship static PNGs and note
the GIF as outstanding. The README must not block on a live demo.

## Repo polish

**LICENSE** — MIT, replacing `License: TBD`.

**CI** — `.github/workflows/ci.yml`, pytest on push and PR.

Correcting an assumption made while scoping: no Neo4j service container is
needed. `tests/conftest.py` sets `RAG_ENABLE_GRAPH=0` and `RAG_ENABLE_REMOTE=0`
and redirects `RAG_DATA_DIR` to an empty temp dir before backend import; the
graph and verification tests monkeypatch `get_session`; the evaluation tests
avoid Ollama by design. The suite is already hermetic. CI runs it whole, with no
services and no flake — strictly better coverage than a partial run with a
container. The dense tests are the only network touch (BGE model fetch) and
already skip gracefully when unavailable.

The README states what the badge covers rather than letting a green tick imply
more than it does.

**Social preview** — 1280×640 PNG, generated programmatically in the app's navy
palette, so a link in an application or on LinkedIn renders as a designed card.

**Repo metadata** — About blurb and topics via `gh`. This is an outward-facing
change to a public repository: exact text is shown and confirmed before it is
applied.

## Work already completed

A cleanup pass on the existing README shipped ahead of the rebuild, because the
defects were live on a public repository:

- Removed four stray citation markers left in the prose.
- Added the MIT `LICENSE` file the README was already pointing at.
- Restored the clickable documentation links.
- Dropped two unsupported claims: FRC standards (absent from the corpus, which
  holds FCA, PRA and legislation.gov.uk material only) and feature-attribution
  interpretability analysis (no such code exists). Also dropped "against a
  standalone LLM baseline" — `eval_results.csv` has no baseline arm, so the
  110-item run is a single-system evaluation, not a comparison.
- Attributed the 0.82 / 0.81 figures to their source directory.

The rebuild starts from this cleaned state.

## Constraints

- No claim in the README that the evaluation data does not support. Where a
  number is weak, the README says so and explains why.
- Every quantitative figure is traceable to a committed file under
  `data/eval_results/` or `docs/`.
- Charts are generated, never hand-drawn, so figures cannot drift from the data
  they claim to represent.

## Out of scope

- GitHub Pages microsite.
- Fixing `RAGAS_MAX_WORKERS=1` or re-running the evaluation. This pass documents
  results; it does not generate new ones.
- The missing `:MENTIONS` relationship type.
- Refactoring backend or frontend code.

## Success criteria

1. A reader understands what the system does and why it is unusual within 15
   seconds of the top of the page.
2. Every chart is regenerable from committed data by one committed script.
3. Every quantitative claim traces to a file in `data/eval_results/` or `docs/`.
4. The ablation study is visible and correctly interpreted.
5. The evaluation gap is disclosed on the main page, not only in a linked doc.
6. CI badge is green and its coverage is stated accurately.
7. No `TBD` remains in the README.
