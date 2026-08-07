# FinLaw-UK

A hybrid architecture combining retrieval-augmented generation (RAG), a Neo4j knowledge graph, and a locally served Mistral 7B model to reduce hallucination in UK financial-regulation question answering. Grounded in the FCA Handbook, PRA Rulebook, and statutory instruments from legislation.gov.uk, the system verifies every citation it produces against the knowledge graph before returning an answer.

MSc dissertation project, University of Bradford, 2025.

## Key Features

*   **Advanced Retrieval Pipeline:** Clause-level segmentation of regulatory text, Sentence Transformer embeddings (`BAAI/bge-small-en-v1.5`), and cross-encoder re-ranking.
*   **Hallucination Reduction:** Graph-grounded citation verification cross-references the Neo4j knowledge graph and flags unsupported references rather than passing them through silently.
*   **Robust Benchmarking:** Evaluated against a custom 110-item benchmark spanning 80 factual questions, 20 document tasks, and 10 case scenarios across 10 regulatory domains.
*   **Reproducibility:** Committed evaluation pipelines and result sets — every figure regenerates from data in the repository.
*   **Measured Performance:** 0.82 source accuracy and 0.81 citation quality across the 110-item benchmark, using RAGAS alongside custom citation-quality and legal-completeness metrics (`backend/results_full/run_20250902_002303/`).

## System Architecture

| Layer | Tech | Where it lives |
| :--- | :--- | :--- |
| **Hybrid retrieval** | BM25 + BGE-small + FAISS + RRF | `backend/retrieval/` |
| **Knowledge graph** | Neo4j 5 with Provision, Term, Regulator, Document nodes | `backend/graph/` |
| **Ingestion** | legislation.gov.uk XML + PDF corpus + LangChain chunking | `backend/graph/ingest_xml.py`, `extract_pdfs.py` |
| **Generator** | Mistral 7B-Instruct via Ollama (HF transformers opt-in) | `backend/llm/` |
| **Verification** | Graph-grounded citation lookup + claim trace | `backend/verification/` |
| **Evaluation** | ragas + lexical baseline | `backend/evaluation/` |
| **Frontend** | React 18 + Tailwind 3 with SSE streaming | `frontend/` |

## Documentation

**Getting started**
*   [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — hardware + software requirements
*   [docs/RUN.md](docs/RUN.md) — setup walkthrough for Windows / macOS / Linux

**Design**
*   [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system diagram, request lifecycle, where every design pick lives
*   [docs/WORKFLOW.md](docs/WORKFLOW.md) — plain-English walkthrough of the system
*   [docs/NEO4J_SCHEMA.md](docs/NEO4J_SCHEMA.md) — graph schema + example Cypher
*   [docs/DSR_MAPPING.md](docs/DSR_MAPPING.md) — Design Science Research mapping

**Evaluation**

Quantitative evaluation is complemented by a qualitative review.

*   [docs/RAGAS_RESULTS.md](docs/RAGAS_RESULTS.md) — evaluation methodology and reproduction
*   [docs/EVALUATION_DIAGNOSTICS.md](docs/EVALUATION_DIAGNOSTICS.md) — root-cause analysis of the `context_recall = 0.075` result (70 of 80 rows in `questions_80_balanced.csv` are template stubs, not a citation-format bug) and of the judge-LLM parallelism issue that makes faithfulness and recall un-measurable on a single Ollama instance
*   [docs/EVALUATION_COMPARISON.md](docs/EVALUATION_COMPARISON.md) — measured effect of the retrieval and prompt changes. `context_precision` valid-count lifts from 8/80 to 77/80 (a coverage win, not a mean win); faithfulness and `context_recall` carry a documented measurement gap
*   [docs/QUALITATIVE_SUMMARY.md](docs/QUALITATIVE_SUMMARY.md) — qualitative findings summary

## Known Limitations

*   `ragas_faithfulness` and `ragas_context_recall` are un-measurable under RAGAS's default parallel judge invocation against a single Ollama instance — see `docs/EVALUATION_DIAGNOSTICS.md §9`.
*   70 of the 80 rows in `questions_80_balanced.csv` are template stubs; `questions_10_curated.csv` is the meaningful evaluation set.
*   The Neo4j graph is missing the `:MENTIONS` relationship type, so 2-hop traversal returns fewer related citations than the schema implies.

## Acknowledgements

University of Bradford MSc Computing programme.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
