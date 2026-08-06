# RAGAS Evaluation — Methodology & Results

This document explains how FinLaw-UK is evaluated, what the four RAGAS
metrics measure, and how to reproduce a run. Concrete numbers from the
most recent run live in `data/eval_results/` (the CSVs are gitignored by
default; commit them if you want to track scores in version control).

## Methodology

### Inputs
- **Question set:** `backend/evaluation/questions/questions_80_balanced.csv`
  — 80 questions across 8 UK financial-regulation domains, each tagged with
  difficulty (`basic`/`intermediate`/`advanced`), a gold answer, the
  expected citation(s), and a small set of expected keywords. The
  distribution is balanced 10/domain so per-domain scores are comparable.
- **Generator:** local Mistral 7B-Instruct via Ollama, served by
  `backend.llm.ollama_client.generate_stream`. The system prompt is the
  same finance-Q&A prompt used by the production chat backend.
- **Retrieval contexts (`contexts` field):** every snippet shown to the
  generator on each question — graph hits from `get_graph_boost` + sparse
  hits from `get_raw_context`, flat-concatenated. See
  `backend.retrieval.orchestrator.gather_contexts` for the canonical
  definition.

### RAGAS metrics
All four are computed by the `ragas` library (pinned to `ragas>=0.2,<0.3`
in `requirements.txt` — see `EVALUATION_DIAGNOSTICS.md` §9 for the pin
rationale) with a local Mistral judge (Ollama by default; HF transformers
opt-in via `--judge hf`):

| Metric | What it measures |
|---|---|
| **Faithfulness** | Does every claim in the answer follow from the retrieved contexts? Catches hallucinations. |
| **Answer relevancy** | Does the answer actually address the question? Catches off-topic drift. |
| **Context precision** | Of the retrieved contexts, what fraction were relevant to the question? Diagnoses noisy retrieval. |
| **Context recall** | Of the gold-answer's facts, what fraction were covered by the retrieved contexts? Diagnoses gaps in retrieval. |

Embeddings (needed for context_precision / context_recall) reuse
`BAAI/bge-small-en-v1.5` — the same encoder the dense retriever indexes
the corpus with, so the embedding space is consistent.

### Lexical baseline
The evaluation layer also ships lexical metrics — Jaccard token overlap,
ROUGE-L (via the `rouge` library, falling back to `difflib`), citation
match (fraction of `expected_citations` appearing in the answer), and a
keyword F1 against `expected_keywords`. They measure surface similarity
rather than answer quality, and are kept as a reference baseline; the
RAGAS scores are the headline.

### Judge LLM choice
Default: **Ollama (Mistral 7B-Instruct)** — same model the chat backend
uses, no extra download. Significantly faster than HF on CPU because
Ollama serves a quantised build.

Opt-in: **HF transformers (Mistral 7B-Instruct-v0.2)** — set
`RAGAS_JUDGE=hf` or pass `--judge hf`. Triggers a one-time ~14 GB
download into `~/.cache/huggingface/`. Slower than Ollama on most
hardware; useful for reproducing scores without an Ollama daemon.

## Reproduction

```powershell
# 1. Make sure the chat backend's deps are installed (Stages 0–4 + RAGAS).
pip install -r requirements.txt

# 2. Make sure the local Mistral is running.
ollama list   # should include mistral:7b-instruct
ollama pull mistral:7b-instruct   # if not present

# 3. (Optional but recommended) seed Neo4j with the rich provision graph,
#    so retrieval can use the structured citations graph enrichment produces.
docker compose up -d
python scripts/seed_neo4j.py

# 4. Smoke run with 5 questions.
python scripts/run_evaluation.py --sample 5 --mode ragas --verbose

# 5. Full run (80 questions; ~30 minutes to ~3 hours depending on hardware).
python scripts/run_evaluation.py --mode both --verbose
```

The output CSVs land in `data/eval_results/`:
- `eval_results_<mode>_<timestamp>.csv` — one row per question with all metrics, contexts, runtime, errors.
- `eval_results_<mode>_<timestamp>_summary.csv` — single row of mean metric scores + question count + total runtime.

## Expected runtimes (Ollama judge, CPU)

| Stage | Per-question cost | 80-question total |
|---|---:|---:|
| RAG generation (Mistral via Ollama) | ~5–15 s | ~10–20 min |
| RAGAS faithfulness | ~3–8 s | ~5–10 min |
| RAGAS answer_relevancy | ~3–8 s | ~5–10 min |
| RAGAS context_precision | ~3–8 s | ~5–10 min |
| RAGAS context_recall | ~3–8 s | ~5–10 min |
| **Total (both)** | ~20–50 s | **~30 min – ~2 h** |

HF judge is roughly 2-4× slower per RAGAS call (no quantisation).

## Current results

Numbers from the most recent run are intentionally not hardcoded here —
they live in the timestamped CSV in `data/eval_results/`. To see the
latest:

```powershell
Get-ChildItem data\eval_results\eval_results_*_summary.csv |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
  Get-Content
```

Reference figures from the two runs analysed in
[EVALUATION_COMPARISON.md](EVALUATION_COMPARISON.md) — the curated-10 set
is the meaningful headline, since 70 of the 80 balanced rows are template
stubs:

| Metric | curated-10 | balanced-80 |
|---|---:|---:|
| faithfulness | not measurable | not measurable |
| answer_relevancy | 0.8029 (n=10/10) | 0.4078 (n=79/80) |
| context_precision | 0.7962 (n=9/10) | 0.8974 (n=77/80) |
| context_recall | not measurable | not measurable |

## Lexical vs. model-based metrics

The lexical metrics in `backend/evaluation/lexical.py` measure surface
similarity between the answer and the gold answer. They are cheap and
deterministic, but they are an imperfect proxy for answer quality: a
correct answer phrased differently from the gold answer scores poorly,
and a fluent hallucination that reuses the gold answer's vocabulary
scores well.

The RAGAS metrics in this document score the system on faithfulness,
answer relevancy, context precision and context recall directly, using a
local Mistral judge. The two families are not comparable to each other —
they measure different things. Both are reported: lexical for absolute
similarity, RAGAS for answer quality.

## Known limitations

- **RAGAS depends on the judge's calibration.** A 7B model is markedly
  less accurate as a judge than GPT-4. Treat the scores as relative
  (system A vs system B) rather than absolute.
- **`context_recall` is sensitive to ground-truth phrasing.** A correct
  answer worded differently from the gold answer can score low. Spot-check
  individual rows in the CSV before reading too much into per-question scores.
- **Each RAGAS metric issues ~3-5 LLM calls per question** for
  decomposition / scoring. On CPU this is the dominant cost.
- **The chat history feature** (`/api/chats/{id}/messages`) is not
  exercised by the eval — questions are evaluated stateless.
- **Judge parallelism.** RAGAS's default `RunConfig(max_workers=4)` runs
  the four metric jobs concurrently against the same Ollama instance.
  Ollama serialises per-model requests internally, but the langchain
  async wrapper appears to interleave or truncate outputs when several
  coroutines share the same chat-completion socket. The faithfulness
  (`n_l_i_statement_prompt`) and recall
  (`context_recall_classification_prompt`) prompts are the most heavily
  affected — both return NaN consistently even though Mistral handles
  them correctly when called serially. Candidate mitigation, untested:
  `RAGAS_MAX_WORKERS=1` in the eval env. See
  `EVALUATION_DIAGNOSTICS.md` §9 for the full investigation.
- **70 of the 80 balanced-set rows are template stubs**, so the
  balanced-80 means are diluted by construction. Use
  `questions_10_curated.csv` for the headline. See
  `EVALUATION_DIAGNOSTICS.md` §2.

## Related documents

- [EVALUATION_DIAGNOSTICS.md](EVALUATION_DIAGNOSTICS.md) — root-cause
  analysis of the `context_recall = 0.075` result and the
  judge-parallelism issue.
- [EVALUATION_COMPARISON.md](EVALUATION_COMPARISON.md) — measured effect
  of the retrieval and prompt changes. The `context_precision` n_valid
  lift is real (1/10 → 9/10 on curated, 8/80 → 77/80 on balanced);
  faithfulness and context_recall carry a documented measurement gap.
