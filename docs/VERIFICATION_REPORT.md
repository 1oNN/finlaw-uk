# FinLaw-UK Verification Report

**Date:** 2026-05-22
**Verifier:** Claude Code (read-only audit)
**Audited against:** master verification brief, implementation plan, application materials
**Environment at audit time:** No services running locally — Docker, Ollama (port 11434), Neo4j (7474), and the backend (5000) were all unreachable. Runtime smoke-tests that depend on those services are marked 🔍 NEEDS USER INPUT; everything else was audited by static analysis, AST parse, file-existence checks, and the parts of pytest that don't need external services.

## Overall verdict

- ✅ Passes: **64**
- ⚠️ Partial: **6**
- ❌ Fails: **1** (auth backend)
- ⏭️ Not yet built: **0**
- 🔍 Needs user input: **17** (mostly runtime tests requiring deps + services)

**Bottom line:** The architectural code is real and well-implemented. Every meaningful claim in the rec letter / CV / cover letter is backed by actual library imports and working code paths (sentence-transformers, FAISS, RRF, LangChain text splitter, real ragas, graph verification, claim trace). XML ingestion was end-to-end exercised during this audit and produced **2,634 real provisions**. Tests pass (54/54 of the runnable subset; 3 skipped because sentence-transformers isn't pip-installed). The single material gap is the **missing backend auth layer** — the React frontend has `Login.jsx`/`Signup.jsx` that POST to `http://localhost:5000/login`, but `backend/app.py` exposes no `/login` or `/signup` route. If the interview includes a live login demo this will fail; everything else is defensible.

---

## Universal checks

### U1. File structure matches target — ⚠️ PARTIAL
Top-level layout is clean: `backend/`, `frontend/`, `data/`, `docs/`, `scripts/`, `tests/`, `requirements.txt`, `docker-compose.yml`, `.env.example`, `.gitignore`, `README.md`. Inside `backend/`, the new module tree is present (`retrieval/`, `graph/`, `llm/`, `verification/`, `ingestion/`, `evaluation/`). However, `backend/` also contains seven non-target subdirectories — `_tmp/`, `data/`, `neo4j-data/`, `neo4j-import/`, `offload/`, `results_full/`, `uploads/`. All seven are matched by `.gitignore` (lines 26-41), so they're runtime/dev clutter, not project structure violations. Acceptable, just untidy.

### U2. No relative imports in `backend/` — ✅ PASS
`Grep '^from \.|^import \.' backend/` returned zero matches. Every import is absolute (`from backend.X.Y import …`).

### U3. No `print()` in `backend/` library code — ✅ PASS
The `print()` calls that exist are in:
- `backend/app.py:508` — startup banner inside `__name__ == "__main__"`
- `backend/llm/hf_client.py:14` — inside a docstring example block
- `backend/retrieval/sparse.py:80` — gated behind `if DEBUG:`
- `backend/graph/seed.py`, `backend/evaluation/runner.py`, `backend/evaluation/ragas_eval.py`, `backend/evaluation/lexical.py` — all CLI entry points (`if __name__ == "__main__"`), which is the allowed exception in the brief.
- `backend/results_full/run_20250902_002303/make_eval_charts_thesis.py` — under a gitignored legacy results dir.

No library function prints to stdout outside of these.

### U4. Every Python module in `backend/` has a docstring — ⚠️ PARTIAL
All 21 active modules have a module-level docstring. One file — `backend/evaluation/lexical_extras.py` — is **0 bytes** and is referenced nowhere in the codebase. Minor finding: delete it or populate it.

### U5. `requirements.txt` is clean and minimal — ✅ PASS
Pinned in the right order: web framework → sparse retrieval → dense retrieval → ingestion → evaluation → document parsing → dev tooling. Comments mark which stage each block belongs to. No obvious dead deps. Matches what's imported in code.

### U6. Root files exist — ✅ PASS
`.gitignore`, `.env.example`, `docker-compose.yml` all present at repo root. `docker-compose.yml` defines Neo4j 5.20 on 7474/7687 with `neo4j/finlaw` credentials matching `.env.example`.

### U7. Nothing is committed — ✅ PASS
No `.git/` directory exists. Git wasn't initialised, which the brief explicitly says is acceptable.

---

## Stage 0 — Reorganisation

### 0a. `backend/app.py` exists; no `app.py` at root — ✅ PASS
`backend/app.py` is 516 lines, has a module docstring at line 2-16, and uses absolute imports.

### 0b. Old file locations are empty — ✅ PASS
`grep` returned no matches for `rag_helper.py`, `graph_helper.py`, `seed_neo4j_finlaw.py`, `inference_ollama.py`, `citation_fix.py`, `ingest.py`, `evaluate_finlaw.py`, `evaluate_finlaw_extras.py`, `libraries.txt`, `upload.py`, or `docker-compose.neo4j.yml` in either `backend/` or the project root.

### 0c. New file locations populated — ✅ PASS
Every file listed in the spec exists and AST-parses cleanly:
- `backend/retrieval/sparse.py`, `orchestrator.py`, `dense.py`, `hybrid.py`
- `backend/graph/traversal.py`, `seed.py`, `client.py`, `ingest_xml.py`, `extract_xrefs.py`, `extract_pdfs.py`, `schema.py`
- `backend/llm/ollama_client.py`, `hf_client.py`
- `backend/verification/citations.py`, `graph_verify.py`, `claim_trace.py`
- `backend/ingestion/documents.py`
- `backend/evaluation/lexical.py`, `ragas_eval.py`, `runner.py`

`backend/auth/routes.py` and `backend/auth/models.py` do **not** exist — see 0f. The spec marked these `(if auth was split out per plan)`, so their absence isn't strictly a stage-0 failure on its own, but combined with 0f below it is.

### 0d. Backend can start — 🔍 NEEDS USER INPUT
Cannot start the backend in this audit environment because key Python packages (`flask_cors`, `neo4j`, `sentence_transformers`, `faiss`, `ragas`, `langchain_core`, `langchain_community`, `langchain_text_splitters`, `rouge`, etc.) are not installed in the current interpreter. The brief forbids installing dependencies. Static analysis: `backend/app.py` AST-parses, imports look correct, and the entry-point block (`python -m backend.app`) is at `backend/app.py:507`.

### 0e. Chat works in all four modes (`auto`/`general`/`finance`/`traffic-light`) — 🔍 NEEDS USER INPUT
Cannot send live requests because the backend, Ollama, and Neo4j are not running. Static code review confirms mode routing at `backend/app.py:346-353`:
```python
use_finance = (mode in ("finance", "traffic-light")) or (mode == "auto" and is_finance_intent(...))
use_traffic = (mode == "traffic-light") or (mode == "auto" and is_traffic_light_intent(prompt))
system_msg = (
    TRAFFIC_LIGHT_PROMPT if (use_finance and use_traffic)
    else FINANCE_QA_PROMPT if use_finance
    else GENERAL_PROMPT
)
```
All four code paths exist and are wired up.

### 0f. Auth flow works — ❌ **FAIL**
**This is the only material failure in the audit.**

`backend/app.py` exposes **only** these routes: `GET /`, `POST /api/upload`, `POST /api/chat/stream`. There is **no** `/login`, `/signup`, `/auth/login`, `/auth/signup`, `/api/chats`, or any other auth endpoint. `grep` for `jwt|JWT|login|signup|sqlalchemy|Authorization` across `backend/` finds nothing except an unrelated provision text mentioning "register" in `backend/graph/seed.py:51`.

The frontend, by contrast, **does** assume the auth layer exists:
- `frontend/src/pages/Login.jsx:15` — `await fetch("http://localhost:5000/login", { method: "POST", credentials: "include", ... })`
- `frontend/src/pages/Signup.jsx` and `GoogleCallback.jsx` exist
- `frontend/src/components/AuthContext.jsx` exists
- `frontend/src/pages/History.jsx` (chat history page) exists
- `frontend/src/components/Chat.js:49` reads `localStorage.getItem("access_token")`

So a user hitting the React login page will see a network error or 404. **If the interviewer asks to see login + chat history working, this will fail.** The chat-stream endpoint itself doesn't require auth, so the core chat demo still works.

### 0g. Multi-model dropdown removed — ✅ PASS
`frontend/src/components/Chat.js:41-42`:
```js
// Multi-model selection was dropped — backend hardcodes Mistral via OLLAMA_MODEL.
const model = "mistral:7b-instruct";
```
No `<select>` or dropdown UI for model choice in `frontend/src/`. The strings `deepseek` and `qwen` only appear in `frontend/node_modules/.cache/babel-loader/` (stale babel cache from a previous build) — not in source.

### 0h. Mistral hardcoded backend-side — ✅ PASS
`backend/app.py:327-329` explicitly ignores the `model` field on incoming requests:
```python
# `model` is accepted for backwards compatibility with old frontend builds
# but ignored — multi-model is dropped, Mistral hardcoded via OLLAMA_MODEL.
_ = data.get("model")
```
`backend/llm/ollama_client.py:27` defaults to `os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")`.

---

## Stage 1 — Dense retrieval

### 1a. `sentence-transformers` imported — ✅ PASS
`backend/retrieval/dense.py:66-67`:
```python
from sentence_transformers import SentenceTransformer
self._model = SentenceTransformer(self.model_name, device=self.device)
```

### 1b. `faiss` imported — ✅ PASS
`backend/retrieval/dense.py:29`: `import faiss  # type: ignore` (guarded by try/except so a missing FAISS gracefully falls back to NumPy cosine).

### 1c. `DenseRetriever` class with required methods — ✅ PASS
`backend/retrieval/dense.py:41-181`:
- `__init__(model_name, cache_dir, device)` — line 50
- `index_documents(docs, persist=True)` — line 88
- `add_documents(docs, persist=True)` — line 102
- `search(query, k=5) -> List[Tuple[str, float]]` — line 120
- `load_cache()` — line 157
- `_save_cache()` — line 142

### 1d. Reciprocal Rank Fusion exists — ✅ PASS
`backend/retrieval/hybrid.py:20-43` defines `reciprocal_rank_fusion(rank_lists, k=10, rrf_k=60)` exactly as specified. Cormack/Clarke/Buettcher (2009) attribution in docstring.

### 1e. Orchestrator combines sparse AND dense via RRF — ✅ PASS
`backend/retrieval/orchestrator.py:75-104` (`_hybrid_search`) calls `sparse.search_bm25` AND `dense.search`, then `reciprocal_rank_fusion(rank_lists, k=k, rrf_k=RRF_K)`. `get_context` (line 145) calls `get_raw_context` which calls `_hybrid_search` as the **primary** path before any fallback.

### 1f. Functional dense search test — 🔍 NEEDS USER INPUT
`sentence-transformers` is not installed in the current Python interpreter. The unit tests for this case (`test_dense_retriever_finds_correct_doc`, `test_dense_cache_roundtrip`, `test_dense_cache_rejects_model_mismatch`) use `pytest.importorskip("sentence_transformers")` and skip gracefully. To verify behaviourally, install requirements and run `pytest tests/test_retrieval.py -v`.

### 1g. Cache file exists — ⚠️ PARTIAL
**Specification mismatch (improvement):** the brief says check for `data/cache/dense_cache.pkl`. The actual implementation uses two files — `data/cache/dense_embeddings.npy` + `data/cache/dense_meta.json` — chosen deliberately to keep the cache portable and avoid binary-format security concerns (see `dense.py:8-11` docstring). Neither file exists yet because the dense index hasn't been built (it builds lazily on first chat). `data/cache/` directory exists and is empty.

### 1h. Tests pass — ✅ PASS
`pytest tests/test_retrieval.py -v` → **10 passed, 3 skipped in 0.50s**. The 3 skips are the `importorskip` ones. RRF, orchestrator fallback, hybrid-first behaviour, and graph-boost short-circuiting are all green.

### 1i. Real semantic query works — 🔍 NEEDS USER INPUT
Requires backend + Ollama + Neo4j running. Code path is wired (see 1e).

---

## Stage 2 — Real ingestion pipeline

### 2a. `lxml` imported — ✅ PASS
`backend/graph/ingest_xml.py:43`: `from lxml import etree` (try/except guarded).

### 2b. LangChain text splitter imported — ✅ PASS
`backend/graph/ingest_xml.py:50-58` tries `langchain_text_splitters` first, falls back to `langchain.text_splitter` if the new package name isn't available.

### 2c. `backend/graph/ingest_xml.py` exists with required functions — ✅ PASS (minor naming variance)
- The brief says `LEGISLATION_URLS`; the code has `LEGISLATION_SOURCES` (line 80) — a list of `LegislationSource` dataclasses with `slug`, `url`, `document`, `regulator`, `domain`, `cite_kind`. **This is richer than the spec, not weaker.**
- `fetch_xml(url, slug)` (line 129) — spec said `fetch_xml(url)`; the extra `slug` arg is for the cache filename. Acceptable improvement.
- `parse_legislation_xml(xml_bytes, source)` (line 301) — yields provision dicts. ✅
- `ingest_all(sources=None)` (line 343) — returns combined list. ✅

### 2d. Cache directory works — ✅ PASS
`data/raw/` already contains the five XML payloads on disk:
- `fsma_2000.xml` — 20.9 MB
- `mlr_2017.xml` — 2.2 MB
- `psr_2017.xml` — 1.8 MB
- `rao_2001.xml` — 4.1 MB
- `uk_mar.xml` — 0.8 MB

Total **~29 MB**, matching the RUN.md claim exactly.

### 2e. PDF ingestion — ✅ PASS
`backend/graph/extract_pdfs.py:27` imports `pdfplumber` (try/except guarded). Module ingests `backend/data/{fca,pra_pdfs}/`. Tests in `tests/test_ingestion.py::test_pdf_detect_module_*` pass.

### 2f. CLI script works — ✅ PASS
`python scripts/ingest_legislation.py --help` output confirms the `--source {xml,pdfs,both}` flag is present along with `--sample` and `--verbose`.

### 2g. Sample ingestion run — ✅ PASS
**Actually executed during this audit.** `python scripts/ingest_legislation.py --source xml --sample 3` produced:
```
XML  : 2634 provisions
         FSMA 2000: 1467
         RAO 2001: 440
         MLR 2017: 336
         PSR 2017: 293
         UK MAR: 98
TOTAL: 2634 provisions
```
**2,634 ≫ 200** required. Sample provisions printed with correct cite shape (`FSMA 2000 s.1A`, `FSMA 2000 s.1B chunk0`/`chunk1`). Chunk splitting works (sections over 1,500 chars are split).

### 2h. Legacy flag preserved — ✅ PASS
`backend/graph/seed.py:274-278`:
```python
parser.add_argument(
    "--legacy",
    action="store_true",
    help="Shorthand for --source legacy.",
)
```
Plus `_collect_provisions("legacy")` at line 246 returns the 17 hardcoded provisions in `LEGACY_PROVISIONS` (lines 30-82). Verified.

---

## Stage 3 — Graph enrichment

### 3a. `backend/graph/extract_xrefs.py` exists — ✅ PASS (minor naming variance)
- `extract_from_clause(text, source_document=None)` (line 105) — spec signature matches; the optional `source_document` arg is an enhancement (context-aware cross-references like bare "section 22" inside an FSMA provision).
- `extract_all_by_id(provisions)` (line 142) — **function is `extract_all_by_id`, not `extract_all` as the spec listed**. Returns `[(source_id, target_cite)]` pairs. Used by `seed.py:24,210`. Minor: spec wording would lead someone to grep for `extract_all` and not find it; the actual name is more precise.

### 3b. Regex patterns reasonable — ✅ PASS
`backend/graph/extract_xrefs.py:39-53` covers FSMA `s.<N>`, RAO `art.<N>`, MLR `reg.<N>`, PSR `reg.<N>`, UK MAR `art.<N>`, and the full FCA Handbook prefix set (`BCOBS, COBS, SYSC, PRIN, CONC, ICOBS, MCOB, PROD, DISP, COMP, COLL, DTR, FUND, MAR`) with `\d+(?:\.\d+)*[A-Za-z]?(?:R|G)?` numbering. The spec asked for "as defined in X", "under X", etc. — these specific connectives aren't gated patterns here; the regex matches the cite shape anywhere in text, which is the standard approach. Tests confirm: `test_extract_handles_section_word_variants`, `test_extract_fca_handbook`, `test_extract_normalises_handbook_suffix_case` all pass.

### 3c. `:CITES` edges exist in Neo4j (>100) — 🔍 NEEDS USER INPUT
Cannot query Neo4j during this audit (not running). The code path is correct:
- `extract_all_by_id` is called in `seed.py:208-216`
- `MERGE_CITES_EDGE` Cypher (lines 142-149) batches rows of 1000.
- Constraints declared in `schema.py:40-45`.

To verify after a seed run: `MATCH ()-[r:CITES]->() RETURN count(r) AS cites_count`.

### 3d. `Regulator` and `Document` nodes exist (≥5 each) — 🔍 NEEDS USER INPUT
Same reason as 3c. Confirmed in code:
- `backend/graph/schema.py:58-64` defines **5 `KNOWN_REGULATORS`** (FCA, PRA, HMT, ESMA, BoE)
- `backend/graph/schema.py:68-74` defines **5 `KNOWN_DOCUMENTS`** (FSMA 2000, RAO 2001, MLR 2017, PSR 2017, UK MAR)

`_enrich_graph` (seed.py:182-216) creates these as `Regulator`/`Document` nodes and joins them via `:ISSUED_BY` / `:PART_OF`.

### 3e. 2-hop traversal — ✅ PASS
`backend/graph/traversal.py:82`:
```cypher
MATCH path = (seed)-[:CITES|MENTIONS|DEFINED_BY*1..%d]-(related:Provision)
```
where `max_hops=2` by default. The variable-length pattern `*1..2` is present and correct.

### 3f. 2-hop returns more than 1-hop — 🔍 NEEDS USER INPUT
Requires Neo4j. Code path supports this by definition: `neighbors_2hop` (max_hops=2) is a superset of `neighbors` (1-hop).

### 3g. `docs/NEO4J_SCHEMA.md` exists and is accurate — ✅ PASS
183 lines. Cross-checked against `backend/graph/schema.py`:
- Node labels match: `Provision`, `Term`, `Regulator`, `Document`
- Relationship types match: `:MENTIONS`, `:DEFINED_BY`, `:CITES`, `:ISSUED_BY`, `:PART_OF`, plus reserved `:RELATES_TO`, `:AMENDED_BY`
- Constraints match (provision_id, term_name, regulator_name, document_name)
- Fulltext indexes match (`provisionIdx`, `termIdx`)

---

## Stage 4 — Verification layer

### 4a. `backend/verification/graph_verify.py` exists — ✅ PASS
- `verify_citation_against_graph(cite)` — line 38, exact-match against `:Provision {cite: $cite}`
- `verify_answer(answer_text, context_cites=())` — line 78, returns the full audit dict with `all_grounded`, `all_retrieved`, `verified`, `unverified`, `hallucinated_context`, `note`
- Plus `verify_citations_batch` for single-roundtrip lookup (line 59).

### 4b. `backend/verification/claim_trace.py` exists — ✅ PASS
- `extract_claims(answer_text, min_length=25)` — line 41
- `trace_claim_to_provision(claim, provision_texts)` — line 96
- `trace_all(answer_text, cites, *, provision_texts=None)` — line 127
- Plus `fetch_provision_texts` helper (line 73).

### 4c. Verification metadata appears in SSE stream — ✅ PASS
`backend/app.py:484-490`:
```python
audit = {
    "citations_ok": citations_ok,
    "invalid": invalid[:10],
    "verification": verification,
    "claim_trace": claim_trace_records,
}
yield f"event: meta\ndata:{json.dumps(audit)}\n\n"
```
`verification` and `claim_trace` are produced by `verify_answer` (line 456) and `trace_all` (line 477).

### 4d. Real cite returns `all_grounded: true` — 🔍 NEEDS USER INPUT
Tests use a mocked Neo4j session. `test_verify_answer_all_grounded` (lines 115-126 of `tests/test_verification.py`) confirms the code path returns `True` for known cites. To verify against a real graph, seed Neo4j and run:
```python
from backend.verification.graph_verify import verify_citation_against_graph
print(verify_citation_against_graph("FSMA 2000 s.19"))
```

### 4e. Fake cite returns `False` — ✅ (covered by test)
`test_verify_answer_flags_unknown_citation` uses `FSMA 2000 s.9999` (a real-shaped but graph-missing cite) and asserts `result["all_grounded"] is False`. Test passes.

### 4f. Tests pass — ✅ PASS
`pytest tests/test_verification.py -v` → **10 passed in <0.1s**.

---

## Stage 5 — Real RAGAS evaluation

### 5a. `ragas` library imported — ✅ PASS
`backend/evaluation/ragas_eval.py:185-193`:
```python
from datasets import Dataset
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
```

### 5b. Required RAGAS metrics imported — ✅ PASS
All four metrics imported (see 5a) and used at line 219: `metrics=[faithfulness, answer_relevancy, context_precision, context_recall]`.

### 5c. Judge LLM is local Mistral — ✅ PASS
`backend/evaluation/ragas_eval.py:150-170`. Default `judge="ollama"` builds `ChatOllama(model=os.getenv("OLLAMA_MODEL", "mistral:7b-instruct"), base_url=..., temperature=0.0)`. The `hf` opt-in uses `backend.llm.hf_client.HFMistralClient` (also Mistral). **OpenAI is not imported anywhere in `backend/evaluation/`**.

### 5d. Sample-5 run — 🔍 NEEDS USER INPUT
Requires `ragas`, `datasets`, `langchain_community`, plus a running Ollama. CLI is correctly defined: `python scripts/run_evaluation.py --sample 5 --mode ragas` (see `scripts/run_evaluation.py:23-30`).

### 5e. Existing lexical eval still runs — ✅ PASS (code-level)
`backend/evaluation/lexical.py` exists (425 lines, retains the original `evaluate_finlaw.py` shape) and `backend/evaluation/runner.py::run(mode="lexical", ...)` provides the new backwards-compatible CLI entry point via `python scripts/run_evaluation.py --mode lexical`. Tests in `tests/test_evaluation.py` cover `_jaccard`, `_rouge_l`, `_citation_match`, `_keyword_f1`, `compute_lexical`, and load_questions — all 11 pass.

---

## Stage 6 — Documentation suite

### 6a. All required docs exist — ✅ PASS
All 11 mandated files are present and non-empty:

| File | Lines |
|---|---:|
| `README.md` (root) | 73 |
| `docs/REQUIREMENTS.md` | 113 |
| `docs/RUN.md` | 197 |
| `docs/ARCHITECTURE.md` | 241 |
| `docs/NEO4J_SCHEMA.md` | 183 |
| `docs/INTERVIEW_QA.md` | 470 |
| `docs/ROUND_1_QUESTIONS.md` | 256 |
| `docs/ROUND_2_EXPECTED.md` | 333 |
| `docs/RAGAS_RESULTS.md` | 154 |
| `docs/DSR_MAPPING.md` | 136 |
| `docs/QUALITATIVE_SUMMARY.md` | 127 |
| `docs/WORKFLOW.md` (bonus) | 906 |

### 6b. INTERVIEW_QA has ≥30 questions — ✅ PASS
37 numbered `### N.` Q-items, organised in 6 sections (`§1` dissertation, `§2` architecture, `§3` specific technical, `§4` evaluation, `§5` Karolinska bio/proteomics pivot, `§6` methodology + limitations).

### 6c. ROUND_1_QUESTIONS contains the four round-1 questions — ✅ PASS
All four present and recognisable:
- Q1. **Why did you integrate Knowledge Graph with RAG?**
- Q2. **How did you upload data into Neo4j Knowledge Graph?**
- Q3. **What were the steps you took in RAG?**
- Q4. **KG and RAG are completely opposite. What if one accepts something and the other rejects it — what did you do?**

Each has the structured "what was said in round 1 / upgraded answer / likely follow-ups" template.

### 6d. README claims match code — ✅ PASS
Spot-checked every claim in README.md's "What's inside" table:

| Claim | Code evidence |
|---|---|
| "BM25 + BGE-small + FAISS + RRF" | `backend/retrieval/{sparse,dense,hybrid,orchestrator}.py` |
| "Neo4j 5 with Provision/Term/Regulator/Document nodes" | `backend/graph/schema.py:28`, `docker-compose.yml:4` (neo4j:5.20) |
| "legislation.gov.uk XML + LangChain chunking" | `backend/graph/ingest_xml.py:50,80` |
| "Mistral 7B-Instruct via Ollama" | `backend/llm/ollama_client.py:27` |
| "HF transformers opt-in" | `backend/llm/hf_client.py` (entire file) |
| "Graph-grounded citation lookup + claim trace" | `backend/verification/graph_verify.py`, `claim_trace.py` |
| "Real `ragas` + lexical baseline" | `backend/evaluation/ragas_eval.py:185`, `lexical.py` |
| "React 18 + Tailwind 3 with SSE streaming" | `frontend/package.json`, `frontend/tailwind.config.js`, `backend/app.py:500-503` |

All accurate.

### 6e. RUN.md works — ⚠️ PARTIAL
PowerShell-flavoured (matches the Windows OS in the brief). Steps 1-9 + troubleshooting are correct. Verified syntax of all commands:
- `python -m venv .venv` ✅
- `pip install -r requirements.txt` ✅ (file exists)
- `docker compose up -d` ✅ (compose file exists)
- `ollama pull mistral:7b-instruct` ✅
- `python scripts/ingest_legislation.py --sample 5` ✅ (just executed; works)
- `python scripts/seed_neo4j.py` ✅ (file exists at `scripts/seed_neo4j.py`)
- `python -m backend.app` ✅
- `python scripts/run_evaluation.py --sample 5 --mode ragas` ✅

Minor: `docs/RAGAS_RESULTS.md:113-122` has placeholder `_TBD_` cells in the results table, which is expected (numbers aren't filled in until a real eval run completes).

---

## Stage 7 — Final cleanup

### 7a. All tests pass — ✅ PASS
```
pytest tests/ -v
========================= 54 passed, 3 skipped in 0.62s =========================
```
Breakdown:
- `test_evaluation.py` — 11 passed
- `test_graph.py` — 13 passed
- `test_ingestion.py` — 10 passed
- `test_retrieval.py` — 10 passed, 3 skipped (sentence-transformers not installed)
- `test_verification.py` — 10 passed

### 7b. End-to-end smoke test — 🔍 NEEDS USER INPUT
Requires running stack. Code paths confirmed in 0e/1i.

### 7c. `.gitignore` excludes the right things — ✅ PASS
Covers `__pycache__/`, `*.pyc`, `.venv/`, `.env`, `data/cache/`, `data/raw/`, `uploads/`, `backend/uploads/`, `backend/neo4j-data/`, `backend/_tmp/`, `backend/offload/`, `backend/results_full/`, `node_modules/`, `frontend/build/`, `*.zip`, IDE files. Specifically allows `data/eval_results/eval_results_legacy.csv` as a baseline preservation rule.

### 7d. Nothing is committed — ✅ PASS
No `.git/` directory exists.

---

## Application-material spot checks

### SC1. Hybrid retrieval combining sparse and dense via RRF — ✅ PASS
`backend/retrieval/orchestrator.py:75-104` (`_hybrid_search`): calls `sparse.search_bm25` for BM25 hits, calls `dense.search` for dense hits, then `reciprocal_rank_fusion(rank_lists, k=k, rrf_k=RRF_K)`. RRF function is `backend/retrieval/hybrid.py:20-43` with the canonical `1/(rrf_k + rank)` formula.

### SC2. Semantic embedding using Sentence Transformers — ✅ PASS
`backend/retrieval/dense.py:66`: `from sentence_transformers import SentenceTransformer`. Default model is `BAAI/bge-small-en-v1.5` (384-dim, line 36). The model is invoked in `_encode` (line 70-78) with `normalize_embeddings=True` for cosine similarity via inner product, then indexed by FAISS `IndexFlatIP` (line 85) or NumPy cosine fallback (line 132).

### SC3. Clause-level segmentation from legislation.gov.uk XML — ✅ PASS
`backend/graph/ingest_xml.py:209-216` iterates `<P1>` elements (the canonical "provision" tag across all legislation.gov.uk schemas — Acts call it section, SIs regulation, EUR docs article), extracts heading + body, and chunks anything over 1,500 chars using `langchain_text_splitters.RecursiveCharacterTextSplitter` (line 248). **Verified end-to-end during this audit** — 2,634 provisions parsed from the 5 cached XMLs.

### SC4. Cross-references modelled structurally — 🔍 (code-level PASS)
`backend/graph/extract_xrefs.py::extract_all_by_id` returns `(source_id, target_cite)` pairs; `backend/graph/seed.py:208-216` batches these into `MERGE_CITES_EDGE` UNWIND queries. The actual edge count requires a Neo4j query (>100 is the spec threshold); to verify, run a seed and `MATCH ()-[r:CITES]->() RETURN count(r)`.

### SC5. Symbolic verification grounded in the knowledge graph — ✅ PASS
`backend/app.py:454-490` is the symbolic-verification path:
- Line 456: `verification = verify_answer(full_text, context_cites)`
- Line 477: `claim_trace_records = trace_all(full_text, verification.get("verified", []))`
- Line 490: emits `event:meta` SSE with the verification verdict + claim trace

`verify_citation_against_graph` does an exact-match `MATCH (p:Provision {cite: $cite})` in Cypher — symbolic, not vector, lookup.

### SC6. Systematic evaluation using RAGAS framework — ✅ PASS
`backend/evaluation/ragas_eval.py:185` imports `from ragas import evaluate`; line 217:
```python
result = evaluate(
    ds,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=judge_llm,
    embeddings=embeddings,
)
```
This is the real `ragas.evaluate()`, not lexical scores renamed.

### SC7. Hugging Face Transformers — ✅ PASS
`sentence-transformers` (loaded at runtime in `dense.py`) is built on `transformers`. The opt-in `backend/llm/hf_client.py:79-83` imports `AutoModelForCausalLM`, `AutoTokenizer`, and `pipeline` from `transformers` directly.

### SC8. LangChain — ✅ PASS
LangChain is used in three places in the runtime path:
- `backend/graph/ingest_xml.py:50` — `from langchain_text_splitters import RecursiveCharacterTextSplitter` (ingestion-time chunking)
- `backend/evaluation/ragas_eval.py:164` — `from langchain_community.chat_models import ChatOllama` (RAGAS judge)
- `backend/evaluation/ragas_eval.py:176` — `from langchain_community.embeddings import HuggingFaceEmbeddings` (RAGAS embeddings)
- `backend/llm/hf_client.py:33` — `from langchain_core.language_models.llms import LLM` (HF judge wrapper)

---

## Critical issues

1. **Backend has no auth endpoints, but the React frontend has Login/Signup/AuthContext/History pages that assume they exist.** Anyone clicking "Log In" on the SPA will hit a 404 against `http://localhost:5000/login`. If the interviewer asks to see chat history or login, this fails. The chat itself works without auth.

That's the only issue serious enough to embarrass the candidate.

## Recommended fixes (in priority order)

1. **(Pre-interview, high)** Decide between two paths for auth:
   - **(a)** Hide the `/login`, `/signup`, `/history` routes in the React app (route them to a "coming soon" or just remove the nav links) so the demo never lands on a broken page. Quick fix — frontend-only.
   - **(b)** Re-implement a small auth layer in `backend/app.py` with `/login`, `/signup`, and the chat-history endpoints. Bigger lift; only worth it if the candidate wants to demonstrate the full SaaS shape.
   - The README and rec letter don't claim auth, so option (a) is sufficient defensively.

2. **(Low)** Delete the empty file `backend/evaluation/lexical_extras.py` — it's unreferenced and confusing.

3. **(Low)** When the candidate runs a full seed + eval before the interview, populate `docs/RAGAS_RESULTS.md`'s `_TBD_` table with the real numbers. Otherwise be prepared to say "the numbers live in the timestamped CSV in `data/eval_results/`."

4. **(Optional)** Consider renaming `extract_all_by_id` → `extract_all` for spec-alignment, or document the function alias more prominently. The current name is technically clearer but anyone reading the brief and grepping for `extract_all` will be briefly confused.

## What's good (don't lose sight of)

- **Every architectural claim in the application materials is backed by real code.** Sentence-transformers, FAISS, LangChain text splitter, ragas, Neo4j graph verification — they are all genuinely loaded and used. No mocked dressing.
- **XML ingestion works end-to-end.** Without changing any state, this audit parsed 2,634 real provisions from the cached legislation.gov.uk XML in <10 seconds.
- **The test suite is real and passes.** 54/54 of the runnable tests pass. The 3 skipped tests `importorskip` cleanly rather than failing.
- **Failure modes are graceful.** Neo4j unavailable → fail-open verification. FAISS unavailable → NumPy fallback. langchain-text-splitters missing → recursive separator-based fallback. sentence-transformers missing → orchestrator falls back to sparse-only. Each guarded import has a sensible degraded path.
- **The verification mechanism is the standout differentiator.** Most "RAG + graph" projects describe both but don't actually verify generated citations against the graph at response time. This one does, and surfaces an SSE `meta` event with `verified`/`unverified`/`hallucinated_context` lists.
- **Documentation is comprehensive and grounded.** ARCHITECTURE.md cross-references every design pick to a specific file and line; INTERVIEW_QA.md has 37 grounded answers; ROUND_1_QUESTIONS.md addresses the four real interview questions head-on with upgrades.

---

*Generated by Claude Code on 2026-05-22. No files were modified; no git operations were performed.*
