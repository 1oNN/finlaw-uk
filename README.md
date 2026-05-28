# FinLaw-UK

A graph-augmented Retrieval-Augmented Generation (RAG) chatbot for UK
financial regulation. Combines a Neo4j knowledge graph with hybrid sparse
+ dense retrieval, a locally-deployed Mistral 7B-Instruct LLM via Ollama,
and graph-grounded citation verification — served by a Flask backend and
a React frontend.


Open http://localhost:3000 and ask a question like *"What is the UK
general prohibition and when does the FSCS £85,000 limit apply?"*

For full setup details see [docs/RUN.md](docs/RUN.md).

## What's inside

| Layer | Tech | Where it lives |
|---|---|---|
| Hybrid retrieval | BM25 + BGE-small + FAISS + RRF | `backend/retrieval/` |
| Knowledge graph | Neo4j 5 with `Provision`, `Term`, `Regulator`, `Document` nodes | `backend/graph/` |
| Ingestion | legislation.gov.uk XML + PDF corpus + LangChain chunking | `backend/graph/ingest_xml.py`, `extract_pdfs.py` |
| Generator | Mistral 7B-Instruct via Ollama (HF transformers opt-in) | `backend/llm/` |
| Verification | Graph-grounded citation lookup + claim trace | `backend/verification/` |
| Evaluation | Real `ragas` + lexical baseline | `backend/evaluation/` |
| Frontend | React 18 + Tailwind 3 with SSE streaming | `frontend/` |

## Documentation

- **[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)** — hardware + software requirements
- **[docs/RUN.md](docs/RUN.md)** — setup walkthrough for Windows / macOS / Linux
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — system diagram, request lifecycle, where every design pick lives
- **[docs/NEO4J_SCHEMA.md](docs/NEO4J_SCHEMA.md)** — live graph schema + example Cypher
- **[docs/DSR_MAPPING.md](docs/DSR_MAPPING.md)** — Design Science Research mapping
- **[docs/QUALITATIVE_SUMMARY.md](docs/QUALITATIVE_SUMMARY.md)** — qualitative findings summary

## Acknowledgements

University of Bradford MSc Computing programme; thesis supervisor and
viva panel.

## License

TBD.
