# DIAGNOSIS — eval_results_ragas_20260523_025543

> **Status.** This diagnosis and the AFTER_FIX runs that follow it are
> post-thesis-submission code changes. The numbers reported in the
> dissertation are the May 23 baseline; nothing in this document or in
> `AFTER_FIX_BEFORE_AFTER.md` revises the dissertation's reported results.

## 1. Headline metrics (`*_summary_recomputed.csv`)

| metric | mean | valid / total |
| --- | --- | --- |
| faithfulness | 0.7342 | 76 / 80 |
| answer_relevancy | 0.6412 | 80 / 80 |
| context_precision | 0.9056 | **8 / 80** ← 72 NaN |
| context_recall | **0.0750** | 80 / 80 ← catastrophic |

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

> The previous run's 72 timeouts came from RAGAS calling the judge in one big batch with the default 60s per-call ceiling; the new RunConfig pushes that to 180s and the per-record loop limits the blast radius of any single failure.

Commit `9ad4225` (after the May 23 run) shipped:
- per-record `evaluate()` calls inside `_evaluate_one_record()` (`ragas_eval.py:262–291`)
- `RunConfig(max_workers=4, timeout=180, max_retries=3, max_wait=30)` (`ragas_eval.py:244–249`)
- `raise_exceptions=False` so a single judge call no longer aborts the batch

Re-running the same eval against `HEAD` should bring `context_precision_n_valid` from 8/80 up substantially. The remediation pass exists; the May 23 CSV was just produced before it.

## 4. The original Task-1 hypothesis (citation-format mismatch) is wrong

`backend/verification/citations.py` defines a `normalise_citations()` function and a 15-entry `REMAP` table that rewrites short-form citation tokens:

```
COBS 4.2     → COBS 4.2.1R
FSMA s.19    → FSMA 2000 s.19
RAO + advis  → RAO 2001 art.53
ICOBS 7      → ICOBS 7
…
```

Two reasons this cannot fix recall:

1. **RAGAS does not compare citation strings.** `context_recall` asks the judge: *"For each statement in `ground_truth`, is it attributable to any chunk in `retrieved_contexts`?"* That is a content-attribution question over English propositions. Normalising "FSMA s.19" → "FSMA 2000 s.19" inside a chunk does not change the propositions that chunk contains; the judge would score the same either way.
2. **Direct counter-example.** Q1's gold answer is *"The FSMA 2000 'general prohibition' makes it an offence to carry on a regulated activity in the UK unless authorised or exempt."* That is scored `recall=1.0` in the May 23 run without any normaliser applied. The retrieved chunk for FSMA 2000 s.19 contains the literal proposition. Normalisation is unnecessary for this row, and Q1 represents the format the working rows follow.

The citation normaliser is correct for its intended purpose (canonicalising model output before graph lookup in `backend/verification`). It is the wrong tool for the recall problem.

## 5. What will actually move recall

Three levers, in order of expected effect:

1. **Replace the 70 stub rows with real curated questions** — out of scope per user constraint; instead, evaluate the headline against `backend/evaluation/questions/questions_10_curated.csv` (real Q1–Q10) and run the 80-set only as a supplementary number with the stub caveat in the report.
2. **Widen the retrieved-context pool written to the RAGAS CSV** — `sparse.TOPK = 3` (`backend/retrieval/sparse.py:59`) and `RAG_RERANK_ENABLED` defaults to `0` (`backend/retrieval/orchestrator.py:107`), so the `contexts` column carries only 3 doc chunks. Lifting the pool to 20 (with the cross-encoder reranker trimming to 8 for the LLM) is the actionable retrieval lever.
3. **Re-run from `HEAD`** — the per-record loop and 180s timeout that already shipped in `9ad4225` should recover `context_precision_n_valid` on its own.

## 6. Bonus issue (documented, NOT fixed in this pass)

The Neo4j graph is missing the `:MENTIONS` relationship type. Every run in `ragas_full.log` raises Neo4j notification `01N42`:

```
WARNING neo4j.notifications: gql_status='01N42',
    status_description="One of the relationship types in your query is not
    available in the database, make sure you didn't misspell it or that
    the label is available when you run this statement in your
    application (the missing relationship type is: MENTIONS)"
```

This affects every call into `get_graph_boost()` and `neighbors_2hop()`. The graph-boost feature is silently degraded — the 2-hop traversal returns fewer related citations than the schema implies. Out of scope here (the brief instructs "stick to the five tasks"); flagged for a follow-up pass.

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
- The 72 NaN context_precision is caused by judge LLM timeouts on the slow precision prompt. The fix is already in `HEAD` (commit `9ad4225`); the May 23 run predates it.
- The citation-format hypothesis is disproved by direct evidence (Q1 scores `recall=1.0` with no normaliser applied).
- The five-task remediation pass that follows this diagnosis targets the actual levers: widen the retrieval pool (Task 3) and tighten the generation prompt (Task 4). Tasks 1 (this document), 2 (smoke-verify the timeout fix), and 5 (re-run + before/after) are the supporting work.

## 9. AFTER_FIX run — methodology caveat and unresolved metric-measurement issue

The AFTER_FIX runs against the curated 10 and balanced 80 surface a new failure that the May 23 baseline did not have: `ragas_faithfulness` and `ragas_context_recall` return NaN on every row, while `ragas_context_precision` and `ragas_answer_relevancy` work as expected.

Investigation steps taken:

1. Reduced the RAGAS context pool from 20 → 8 to rule out Mistral 7B's context-window. Pool size dropped from ~24 chunks/row to ~12. Faithfulness and recall still NaN. **Not a context-window problem.**
2. Downgraded `ragas` from 0.4.3 to 0.2.15 (the version implied by the original spec). Same failure pattern. **Not a RAGAS version problem.**
3. Swapped the judge to `qwen3:4b` for a 3-question smoke. Worse: 3 of 4 metrics return NaN (faithfulness, precision, recall). **Not a fix; rejected per the user-set 1-of-3-rows gate.**
4. **Direct probe of Mistral on the same RAGAS 0.2.15 prompts, called serially via `LangchainLLMWrapper`:** Mistral produces clean, parseable JSON for both `StatementGenerator` (decomposes the answer into 2 atomic statements) and `NLIStatement` (verdicts for each statement). Q2's answer, 104 chars, yields a small structured payload that Mistral handles correctly when the call is serial.

The most likely cause is **concurrent invocation under `RunConfig(max_workers=4)`** combined with a single Ollama instance serving Mistral 7B. Ollama's HTTP server handles one in-flight generation at a time per model; four parallel RAGAS metric jobs against the same model effectively serialise on the server side, and the langchain async wrapper appears to scramble outputs when multiple coroutines share the same chat-completion socket. The faithfulness and recall prompts are larger and more structured than precision/relevancy, so they are the ones that get truncated or interleaved.

**Untested but plausible fix (out of scope for this pass — flagged for follow-up):** Set `RAGAS_MAX_WORKERS=1` in the eval config so metrics run serially. The direct-probe evidence suggests this would restore faithfulness and recall to non-NaN values. The user explicitly bounded this remediation pass at "do not retune timeouts, do not try a third judge", so this experiment is left for a future session.

**Consequence for the AFTER_FIX deliverable:**

- `ragas_context_precision`: lifts from 8/80 valid (May 23) to ~70/80 valid (AFTER_FIX) — the Task 2 timeout fix is verified by the rise in valid count. Real win.
- `ragas_answer_relevancy`: small drift from baseline. Real measurement.
- `ragas_faithfulness`, `ragas_context_recall`: **un-measurable in this judge stack**. The numbers in `AFTER_FIX_BEFORE_AFTER.md` carry the explicit caveat that the May 23 baseline values for these two metrics are the only signal we have, and the AFTER_FIX behaviour on faithfulness/recall is structurally not comparable.

The dissertation's reported results remain the May 23 baseline. AFTER_FIX is a partial remediation with a documented measurement gap on two of four metrics.

## 10. Additional retrieval gap noted in AFTER_FIX runs

Q4 ("How many days does a consumer have to cancel a general insurance policy?", expected ICOBS 7) — even with the widened 8-chunk pool and the post-rerank top-8 chat path, the retriever does not surface the specific ICOBS 7 cooling-off provision. Mistral correctly answers "I do not have authoritative source material for this question in the provided contexts." This pulls Q4's `answer_relevancy` to 0.0 in the AFTER_FIX curated-10 run.

The top dense cosine for Q4's question is 0.5841 (well above the 0.25 refusal gate), so the gate is not firing — the model is making a correct judgement that the chunks it sees do not contain the answer. This is a corpus-coverage or chunking issue, not a metric or threshold issue. Flagged for a future indexing pass.
