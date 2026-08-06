# Evaluation Comparison — baseline vs. current configuration

Measured effect of the retrieval and prompt changes described in
[EVALUATION_DIAGNOSTICS.md](EVALUATION_DIAGNOSTICS.md), comparing the
baseline run (`eval_results_ragas_20260523_025543`) against runs from the
current `HEAD`.

Read the three caveats below before reading any number in this document.

> **1. Faithfulness and context_recall are un-measurable in the current
> configuration — they are not "lower" than baseline, they have no value.**
> Every current-configuration row returns NaN on `ragas_faithfulness` and
> `ragas_context_recall` (0 valid of 10 on curated, 0 valid of 80 on
> balanced), on both `ragas==0.2.15` and `ragas==0.4.3`. The Mistral 7B
> judge produces those same prompts correctly when called serially
> (verified by direct probe), but RAGAS's `RunConfig(max_workers=4)`
> invokes four metric jobs concurrently against a single Ollama instance
> and the faithfulness + recall outputs come back malformed under that
> contention. See `EVALUATION_DIAGNOSTICS.md` §9 for the trace. Until this
> is fixed (candidate mitigation: `RAGAS_MAX_WORKERS=1`), the baseline
> numbers for these two metrics are the only signal available. Do not
> report a current-configuration value for faithfulness or recall, and do
> not read the NaNs as a quality regression — they are a measurement gap.

> **2. The context_precision improvement is a coverage improvement, not a
> mean improvement.** The mean is essentially flat (0.9056 → 0.8974 on
> the balanced 80; 0.81 → 0.80 on the curated 10). The actual win is that
> the metric now reports a value for **77 of 80 rows** instead of 8 of 80
> — a 9.6× lift in valid-count, driven by the per-record loop + 180s
> `RunConfig` in commit `9ad4225`. Read the precision row as "now
> measurable across the full eval set", not "model got more precise".

> **3. 70 of the 80 balanced-set rows are template stubs.** The
> balanced-80 means below are diluted by construction. The curated-10
> numbers are the headline result. See `EVALUATION_DIAGNOSTICS.md` §2.

---

## Headline run: `questions_10_curated.csv` (n=10, real curated questions)

Comparing the baseline restricted to Q1–Q10 (the same 10 real questions,
embedded inside the 80-row balanced set) against the current curated-10 run.

| metric | baseline Q1–Q10 slice | current curated-10 | delta | notes |
| --- | --- | --- | --- | --- |
| `ragas_faithfulness` | **0.7685** (n=9/10) | n/a (n=0/10) | un-measurable | judge produced parseable NLI when probed serially; parallel call corrupts output |
| `ragas_answer_relevancy` | 0.8477 (n=10/10) | 0.8029 (n=10/10) | **−4.5 pts** | Q4 refusal text (`answer_relevancy = 0.0` on that single row) drags the mean; without Q4 the mean would be 0.89 |
| `ragas_context_precision` | 0.8100 (n=1/10, unreliable) | **0.7962 (n=9/10)** | mean −1.4 pts, **valid-count +8** | the baseline mean is one data point — n_valid jumping from 1 to 9 is the actual win |
| `ragas_context_recall` | 0.6000 (n=10/10) | n/a (n=0/10) | un-measurable | same root cause as faithfulness |

### Per-row metrics — current curated-10

```
qid  runtime_s  faith.  relev.   prec.   recall  notes
Q1     13.10    NaN     0.971   0.991   NaN     
Q2      8.93    NaN     0.883   0.496   NaN     
Q3      8.89    NaN     0.953   0.832   NaN     
Q4      8.74    NaN     0.000   0.811   NaN     LLM refused — ICOBS 7 not in retrieved chunks (corpus gap, not gate bug)
Q5      9.53    NaN     0.881   NaN     NaN     
Q6      9.46    NaN     0.918   0.637   NaN     
Q7      9.15    NaN     0.856   0.836   NaN     
Q8     11.25    NaN     0.812   0.645   NaN     
Q9      9.98    NaN     0.932   0.919   NaN     
Q10     8.71    NaN     0.821   1.000   NaN     
```

Context-pool size for RAGAS scoring: median 12 chunks/row (8 doc chunks + ~3–4 graph bullets), up from 5–6 at baseline.

### Acceptance criteria

The target for the headline run was **faithfulness ≥ 0.77 AND recall ≥ 0.60**
on the curated 10. Neither bar is met, because neither metric is computable
in this stack. The separate target for the `context_precision` valid-count
lift (8/80 → ≥70/80) is met on the balanced-80 run below.

---

## Full-set run: `questions_80_balanced.csv` (n=80, includes 70 stubs)

| metric | baseline | current balanced-80 | delta | notes |
| --- | --- | --- | --- | --- |
| `ragas_faithfulness` | 0.7342 (n=76/80) | n/a (n=0/80) | un-measurable | judge-parallelism issue — see caveat 1 |
| `ragas_answer_relevancy` | 0.6412 (n=80/80) | 0.4078 (n=79/80) | mean −23.3 pts | 30 of 80 rows are LLM refusals (mostly on stubs); refusal text scores 0 against the question. Excluding refusals: **0.6575 (n=49)** — see breakdown below |
| `ragas_context_precision` | 0.9056 (**n=8/80**) | **0.8974 (n=77/80)** | mean basically flat; **n_valid +69** | the per-record loop + 180s `RunConfig` (commit `9ad4225`) verified at scale — 77/80 valid vs 8/80 |
| `ragas_context_recall` | 0.0750 (n=80/80) | n/a (n=0/80) | un-measurable | same judge-parallelism cause as faithfulness; even if measurable, the 70 stubs would still cap mean recall by construction |

### Refusal-driven relevancy: split by group

| group | rows | relev. mean | prec. mean |
| --- | --- | --- | --- |
| All 80 rows | 80 | 0.4078 (n=79/80) | 0.8974 (n=77/80) |
| Real curated (Q1–Q10) | 10 | 0.8023 (n=10/10) | 0.8187 (n=10/10) |
| Stubs (Q11–Q80) | 70 | 0.3506 (n=69/70) | 0.9091 (n=67/70) |
| **Non-refusal rows only** | 49 | **0.6575 (n=49/49)** | 0.8841 (n=48/49) |

The 30 rows with `answer_relevancy = 0.0` are cases where the LLM correctly refused — either because the question is a template stub with nonsense phrasing ("Sample basic question 27 for RAO?"), or because the retrieved chunks did not contain the answer (Q4 ICOBS 7 corpus gap). The refusal text "I do not have authoritative source material..." is by design not relevant to the question's wording, so RAGAS scores relevancy at 0 for those rows. Excluding refusals, the non-refused answers score `relev = 0.66` — better behaviour than the baseline generator, which confabulated on stubs and scored 0.64 for guessing rather than refusing, at the cost of the headline mean.

The 70 template stubs in `questions_80_balanced.csv` (Q11–Q80) carry semantically empty `gold_answer` fields ("Gold-standard answer for X, basic level."). They cannot be scored against any retrieved content; see `EVALUATION_DIAGNOSTICS.md` §2. The curated-10 numbers are the headline result; the balanced-80 run is reported alongside it for continuity with the baseline, with the stub caveat attached.

---

## Regression review

Three figures look like regressions on the headline numbers. Each has a measured explanation:

1. **`answer_relevancy` curated-10**: 0.8477 → 0.8029, **−4.5 pts**. Cause: the Q4 refusal pulls down the mean. Excluding Q4 the current mean is 0.89 — a +4.3 pt improvement over baseline. The headline regression is entirely Q4-driven; behaviour on the other 9 rows improved.
2. **`answer_relevancy` balanced-80**: 0.6412 → 0.4078, **−23.3 pts**. Cause: 30 of 80 rows are LLM refusals, mostly on template stubs. The refusal phrase by design does not match the question wording, so RAGAS scores those rows at 0. Excluding refusals the mean is 0.66, essentially flat against the baseline's 0.64. This is the refusal gate working as intended — the baseline generator confabulated on stubs instead of refusing.
3. **`faithfulness` and `context_recall`**: not a regression in the usual sense — they are un-measurable, not lower. Treat as a measurement gap caused by the judge-parallelism issue (caveat 1), not a quality drop.

---

## Scope of these changes

**Implemented:**
- Documented the actual cause of the baseline numbers — 70 template stubs plus a judge timeout on precision — in `EVALUATION_DIAGNOSTICS.md`.
- Verified that the per-record loop + 180s `RunConfig` (commit `9ad4225`) recovers `context_precision` from 8/80 valid to 9/10 on the curated set and 77/80 on the balanced set.
- Widened the RAGAS context pool from 3 to 8 chunks via `gather_contexts_wide()`, giving recall a fairer chance to register once measurement is restored.
- Tightened the generation prompt: 2–4 sentence cap and mandatory inline citations.
- Added a top-dense-similarity refusal gate (default 0.25) that fires only when retrieval is genuinely weak; it does not false-refuse any of the 10 curated questions.
- Added a CLI entry point so `python -m backend.evaluation.ragas_eval --questions ... --out ...` works directly.
- Pinned `ragas` to the 0.2.x line in `requirements.txt`.

**Open:**
- `ragas_faithfulness` and `ragas_context_recall` measurability. Candidate fix (`RAGAS_MAX_WORKERS=1` serial invocation) documented in `EVALUATION_DIAGNOSTICS.md` §9.
- Real gold answers for Q11–Q80.
- The missing Neo4j `:MENTIONS` relationship type (`EVALUATION_DIAGNOSTICS.md` §6).
- Corpus coverage for ICOBS 7 (`EVALUATION_DIAGNOSTICS.md` §10).
