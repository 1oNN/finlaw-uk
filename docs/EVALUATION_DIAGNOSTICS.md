# Evaluation Diagnostics — baseline run `20260523_025543`

Root-cause analysis of the two anomalies in the baseline RAGAS run
(`eval_results_ragas_20260523_025543`): a `context_recall` mean of 0.075
and `context_precision` returning NaN on 72 of 80 rows. Sections 1–8
diagnose the baseline run; sections 9–10 cover issues surfaced by the
follow-up runs described in [EVALUATION_COMPARISON.md](EVALUATION_COMPARISON.md).

## 1. Headline metrics (`*_summary_recomputed.csv`)

| metric | mean | valid / total |
| --- | --- | --- |
| faithfulness | 0.7342 | 76 / 80 |
| answer_relevancy | 0.6412 | 80 / 80 |
| context_precision | 0.9056 | **8 / 80** ← 72 NaN |
| context_recall | **0.0750** | 80 / 80 |

Two surface failures: (a) context_recall collapses to 0.075, (b) context_precision is NaN on 72 of 80 rows. The rest of this document explains both.

## 2. Root cause #1 — 70 of 80 question rows are template stubs

`backend/evaluation/questions/questions_80_balanced.csv` is the input to this run. Auditing its content reveals that only the first 10 rows are real curated questions; rows 11–80 are template stubs whose `question` and `gold_answer` fields are placeholders, not real evaluation content.

Examples (verbatim from the CSV):

```
Q11,FSMA,basic,Sample basic question 11 for FSMA?,"Gold-standard answer for FSMA, basic level.",FSMA 2000 s.19,…
Q14,ICOBS,basic,Sample basic question 14 for ICOBS?,"Gold-standard answer for ICOBS, basic level.",ICOBS 7,…
Q20,DISP,basic,Sample basic question 20 for DISP?,"Gold-standard answer for DISP, basic level.",DISP 1.6,…
Q41,FSMA,intermediate,Sample intermediate question 41 for FSMA?,"Gold-standard answer for FSMA, intermediate level.",FSMA 2000 s.19,…
```

Q41–Q50 are also flagged `is_placeholder=True, gt_in_corpus=False` in `eval_results_ragas_20260523_025543_diagnose_recall.csv`, confirming the placeholder status was already noted for that decile.

RAGAS `context_recall` asks the judge LLM to decompose `ground_truth` into atomic statements and check each one against the retrieved contexts. The string `"Gold-standard answer for FSMA, basic level."` is not an attributable factual claim — there is no proposition in the corpus that could ground it. Recall for every stub row is therefore 0 by construction.

### 2a. Quantitative confirmation

Splitting the 80 rows into the real-curated subset (Q1–Q10) and the stub subset (Q11–Q80) gives:

| group | rows | mean context_recall |
| --- | --- | --- |
| real (Q1–Q10) | 10 | **0.60** |
| stub (Q11–Q80) | 70 | **0.00** |

Weighted average: (10 × 0.60 + 70 × 0.00) / 80 = **0.075**. That is exactly the headline number. The 0.075 mean recall is the arithmetic consequence of mixing 10 working rows with 70 unscorable ones — not a retrieval failure.

### 2b. Counter-evidence: the retriever works on real questions

| qid | question | recall | retrieved chunk excerpt |
| --- | --- | --- | --- |
| Q1 | What is the 'general prohibition' in UK financial services? | **1.00** | "**FSMA 2000 s.19** — The general prohibition. … No person may carry on a regulated activity in the United Kingdom … unless he is — (a) an authorised person; or (b) an exempt person." |
| Q2 | What is the FSCS deposit protection limit per individual? | **1.00** | "**FSMA 2000 s.224D** … FSCS manager may decline to act … " (plus s.1C consumer protection objective) |

Both real questions score `recall=1.0` with no citation normaliser applied, because the retrieved chunks contain the propositions the gold answer asserts.

## 3. Root cause #2 — context_precision NaN is a judge LLM timeout, not missing data

The 72 NaN values for `ragas_context_precision` are not caused by missing `reference` data. Evidence:

- `backend/evaluation/ragas_eval.py:115` reads the CSV's `gold_answer` column into `record.ground_truth` for every row, including stubs.
- `backend/evaluation/ragas_eval.py:272` passes `record.ground_truth` as the RAGAS `reference` field.
- Real rows (Q1, Q2) have full data — question, answer, contexts, reference — and STILL show `ragas_context_precision = NaN`.

NaN distribution across the split:

| group | rows | NaN on context_precision |
| --- | --- | --- |
| real (Q1–Q10) | 10 | **9** |
| stub (Q11–Q80) | 70 | **63** |

The NaN rate is uniform (~90%) across both groups. That rules out data-quality and ground_truth-shape causes. The only remaining explanation is metric-computation failure at the judge level. `backend/evaluation/ragas_eval.py:182–185` documents this directly:

> RAGAS called the judge in one big batch under the default 60s per-call ceiling; the current `RunConfig` pushes that to 180s and the per-record loop limits the blast radius of any single failure.

Commit `9ad4225` ships:
- per-record `evaluate()` calls inside `_evaluate_one_record()` (`ragas_eval.py:262–291`)
- `RunConfig(max_workers=4, timeout=180, max_retries=3, max_wait=30)` (`ragas_eval.py:244–249`)
- `raise_exceptions=False` so a single judge call no longer aborts the batch

The baseline CSV predates that commit. Re-running the same eval against `HEAD` should bring `context_precision_n_valid` from 8/80 up substantially — confirmed in [EVALUATION_COMPARISON.md](EVALUATION_COMPARISON.md).

## 4. The citation-format hypothesis is wrong

`backend/verification/citations.py` defines a `normalise_citations()` function and a 15-entry `REMAP` table that rewrites short-form citation tokens:

```
COBS 4.2     → COBS 4.2.1R
FSMA s.19    → FSMA 2000 s.19
RAO + advis  → RAO 2001 art.53
ICOBS 7      → ICOBS 7
…
```

A plausible first hypothesis is that recall collapses because the retrieved chunks and the gold answers spell citations differently. Two reasons that cannot be the cause:

1. **RAGAS does not compare citation strings.** `context_recall` asks the judge: *"For each statement in `ground_truth`, is it attributable to any chunk in `retrieved_contexts`?"* That is a content-attribution question over English propositions. Normalising "FSMA s.19" → "FSMA 2000 s.19" inside a chunk does not change the propositions that chunk contains; the judge would score the same either way.
2. **Direct counter-example.** Q1's gold answer is *"The FSMA 2000 'general prohibition' makes it an offence to carry on a regulated activity in the UK unless authorised or exempt."* That is scored `recall=1.0` in the baseline run without any normaliser applied. The retrieved chunk for FSMA 2000 s.19 contains the literal proposition. Normalisation is unnecessary for this row, and Q1 represents the format the working rows follow.

The citation normaliser is correct for its intended purpose (canonicalising model output before graph lookup in `backend/verification`). It is the wrong tool for the recall problem.

## 5. What will actually move recall

Three levers, in order of expected effect:

1. **Replace the 70 stub rows with real curated questions.** Until that work is done, evaluate the headline against `backend/evaluation/questions/questions_10_curated.csv` (real Q1–Q10) and treat the 80-row set as a supplementary number carrying the stub caveat.
2. **Widen the retrieved-context pool written to the RAGAS CSV.** `sparse.TOPK` (`backend/retrieval/sparse.py:59`) and `RAG_RERANK_ENABLED` (`backend/retrieval/orchestrator.py:107`) together determine how many doc chunks reach the `contexts` column. Lifting the candidate pool to 20, with the cross-encoder reranker trimming to 8 for the LLM, is the actionable retrieval lever.
3. **Re-run from `HEAD`.** The per-record loop and 180s timeout in `9ad4225` should recover `context_precision_n_valid` on their own.

## 6. Secondary issue — missing `:MENTIONS` relationship type

The Neo4j graph is missing the `:MENTIONS` relationship type. Every run in `ragas_full.log` raises Neo4j notification `01N42`:

```
WARNING neo4j.notifications: gql_status='01N42',
    status_description="One of the relationship types in your query is not
    available in the database, make sure you didn't misspell it or that
    the label is available when you run this statement in your
    application (the missing relationship type is: MENTIONS)"
```

This affects every call into `get_graph_boost()` and `neighbors_2hop()`. The graph-boost feature is silently degraded — the 2-hop traversal returns fewer related citations than the schema implies. Tracked as open work; not addressed here.

## 7. Row-by-row evidence

Pulled directly from `eval_results_ragas_20260523_025543.csv`:

| qid | domain | question (first ~50 chars) | recall | f. | a.r. | c.p. | type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 | FSMA | What is the 'general prohibition' in UK financial… | **1.00** | 1.00 | 0.80 | NaN | real |
| Q2 | COMP | What is the FSCS deposit protection limit per ind… | **1.00** | 1.00 | 0.91 | NaN | real |
| Q11 | FSMA | Sample basic question 11 for FSMA? | 0.00 | 0.00 | 0.66 | NaN | **stub** |
| Q14 | ICOBS | Sample basic question 14 for ICOBS? | 0.00 | 1.00 | 0.69 | NaN | **stub** |
| Q20 | DISP | Sample basic question 20 for DISP? | 0.00 | 1.00 | 0.56 | NaN | **stub** |
| Q41 | FSMA | Sample intermediate question 41 for FSMA? | 0.00 | 1.00 | 0.57 | NaN | **stub** + placeholder-flagged |
| Q50 | DISP | Sample intermediate question 50 for DISP? | 0.00 | 0.88 | 0.54 | NaN | **stub** + placeholder-flagged |

The pattern is unambiguous: every real row gets non-zero recall, every stub row gets zero recall, and the NaN on context_precision is independent of both.

## 8. Conclusion

- The 0.075 mean recall is caused by 70 unscorable stub rows. The retriever works on real questions.
- The 72 NaN context_precision values are caused by judge LLM timeouts on the slow precision prompt. The fix is in `HEAD` (commit `9ad4225`); the baseline run predates it.
- The citation-format hypothesis is disproved by direct evidence (Q1 scores `recall=1.0` with no normaliser applied).
- The actionable levers are widening the retrieval pool and tightening the generation prompt. Both are implemented and measured in [EVALUATION_COMPARISON.md](EVALUATION_COMPARISON.md).

## 9. Judge parallelism — faithfulness and recall are un-measurable in the current stack

Runs of the current configuration against the curated 10 and balanced 80 surface a failure the baseline run did not have: `ragas_faithfulness` and `ragas_context_recall` return NaN on every row, while `ragas_context_precision` and `ragas_answer_relevancy` work as expected.

Investigation steps taken:

1. Reduced the RAGAS context pool from 20 → 8 to rule out Mistral 7B's context-window. Pool size dropped from ~24 chunks/row to ~12. Faithfulness and recall still NaN. **Not a context-window problem.**
2. Downgraded `ragas` from 0.4.3 to 0.2.15. Same failure pattern. **Not a RAGAS version problem.** This is the reason `requirements.txt` pins `ragas>=0.2,<0.3` — the pin is for reproducibility against the documented behaviour, not a workaround.
3. Swapped the judge to `qwen3:4b` for a 3-question smoke. Worse: 3 of 4 metrics return NaN (faithfulness, precision, recall). Rejected.
4. **Direct probe of Mistral on the same RAGAS 0.2.15 prompts, called serially via `LangchainLLMWrapper`:** Mistral produces clean, parseable JSON for both `StatementGenerator` (decomposes the answer into 2 atomic statements) and `NLIStatement` (verdicts for each statement). Q2's answer, 104 chars, yields a small structured payload that Mistral handles correctly when the call is serial.

The most likely cause is **concurrent invocation under `RunConfig(max_workers=4)`** combined with a single Ollama instance serving Mistral 7B. Ollama's HTTP server handles one in-flight generation at a time per model; four parallel RAGAS metric jobs against the same model effectively serialise on the server side, and the langchain async wrapper appears to scramble outputs when multiple coroutines share the same chat-completion socket. The faithfulness and recall prompts are larger and more structured than precision/relevancy, so they are the ones that get truncated or interleaved.

**Candidate fix, untested:** set `RAGAS_MAX_WORKERS=1` in the eval config so metrics run serially. The direct-probe evidence suggests this would restore faithfulness and recall to non-NaN values. Tracked as open work.

**Consequences for the metrics:**

- `ragas_context_precision`: lifts from 8/80 valid to ~70/80 valid — the timeout fix is verified by the rise in valid count.
- `ragas_answer_relevancy`: small drift from baseline. Real measurement.
- `ragas_faithfulness`, `ragas_context_recall`: **un-measurable in this judge stack**. The baseline values for these two metrics are the only signal available, and current behaviour on them is structurally not comparable.

## 10. Retrieval gap on Q4 (ICOBS 7)

Q4 ("How many days does a consumer have to cancel a general insurance policy?", expected ICOBS 7) — even with the widened 8-chunk pool and the post-rerank top-8 chat path, the retriever does not surface the specific ICOBS 7 cooling-off provision. Mistral correctly answers "I do not have authoritative source material for this question in the provided contexts." This pulls Q4's `answer_relevancy` to 0.0 in the curated-10 run.

The top dense cosine for Q4's question is 0.5841 (well above the 0.25 refusal gate), so the gate is not firing — the model is making a correct judgement that the chunks it sees do not contain the answer. This is a corpus-coverage or chunking issue, not a metric or threshold issue. Tracked for a future indexing pass.
