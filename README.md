# FinLaw-UK

A graph-augmented Retrieval-Augmented Generation (RAG) chatbot for UK
financial regulation. Combines a Neo4j knowledge graph with hybrid sparse
+ dense retrieval, a locally-deployed Mistral 7B-Instruct LLM via Ollama,
and graph-grounded citation verification — served by a Flask backend and
a React frontend.

MSc dissertation project, University of Bradford, 2025.

## What's inside

| Layer | Tech | Where it lives |
|---|---|---|
| Hybrid retrieval | BM25 + BGE-small + FAISS + RRF | `backend/retrieval/` |
| Knowledge graph | Neo4j 5 with `Provision`, `Term`, `Regulator`, `Document` nodes | `backend/graph/` |
| Ingestion | legislation.gov.uk XML + PDF corpus + LangChain chunking | `backend/graph/ingest_xml.py`, `extract_pdfs.py` |
| Generator | Mistral 7B-Instruct via Ollama (HF transformers opt-in) | `backend/llm/` |
| Verification | Graph-grounded citation lookup + claim trace | `backend/verification/` |
| Evaluation | `ragas` + lexical baseline | `backend/evaluation/` |
| Frontend | React 18 + Tailwind 3 with SSE streaming | `frontend/` |

## Documentation

### Project docs (dissertation deliverables)

- **[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)** — hardware + software requirements
- **[docs/RUN.md](docs/RUN.md)** — setup walkthrough for Windows / macOS / Linux
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — system diagram, request lifecycle, where every design pick lives
- **[docs/NEO4J_SCHEMA.md](docs/NEO4J_SCHEMA.md)** — live graph schema + example Cypher
- **[docs/RAGAS_RESULTS.md](docs/RAGAS_RESULTS.md)** — evaluation methodology and reproduction
- **[docs/DSR_MAPPING.md](docs/DSR_MAPPING.md)** — Design Science Research mapping
- **[docs/QUALITATIVE_SUMMARY.md](docs/QUALITATIVE_SUMMARY.md)** — qualitative findings summary
- **[docs/WORKFLOW.md](docs/WORKFLOW.md)** — plain-English walkthrough of the system

### Post-submission addenda (forward-looking, not dissertation-revising)

These were produced after thesis submission to investigate and partially
remediate the headline numbers in `eval_results_ragas_20260523_025543`.
They do not change anything reported in the dissertation.

- **[DIAGNOSIS.md](DIAGNOSIS.md)** — root cause of `context_recall = 0.075` (70 of 80 question rows in `questions_80_balanced.csv` are template stubs, not a citation-format bug). Also documents the judge-LLM parallelism issue surfaced by the AFTER_FIX runs.
- **[AFTER_FIX_BEFORE_AFTER.md](AFTER_FIX_BEFORE_AFTER.md)** — partial remediation results. `context_precision` valid-count lifts from 8/80 to 77/80 (a coverage win, not a mean win); `faithfulness` and `context_recall` are literally un-measurable in the AFTER_FIX judge configuration. May 23 baseline values for those two metrics remain the only signal.

## Acknowledgements

University of Bradford MSc Computing programme; thesis supervisor and
viva panel.

## License

TBD.
