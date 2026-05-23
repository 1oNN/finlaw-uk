# FinLaw-UK

A graph-augmented Retrieval-Augmented Generation (RAG) chatbot for UK
financial regulation. Combines a Neo4j knowledge graph with hybrid sparse
+ dense retrieval, a locally-deployed Mistral 7B-Instruct LLM via Ollama,
and graph-grounded citation verification — served by a Flask backend and
a React frontend.

> MSc dissertation project (University of Bradford, 2025). The codebase
> has been upgraded post-submission so that every architectural claim in
> the application materials — dense vector embeddings, LangChain, HF
> Transformers, real RAGAS evaluation, symbolic verification — is
> literally true in the code.

## Quickstart

```bash
# 1. Clone + venv
python -m venv .venv
.venv\Scripts\Activate.ps1            # Windows; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 2. Bring up Neo4j and Ollama
docker compose up -d                  # Neo4j on 7474/7687
ollama pull mistral:7b-instruct       # ~4 GB

# 3. Seed the graph (XML + supplementary PDFs)
python scripts/seed_neo4j.py

# 4. Run the backend + frontend
python -m backend.app                 # Flask on :5000
cd frontend && npm install && npm start   # React on :3000
```

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
- **[docs/RAGAS_RESULTS.md](docs/RAGAS_RESULTS.md)** — evaluation methodology and reproduction
- **[docs/INTERVIEW_QA.md](docs/INTERVIEW_QA.md)** — interview prep (30+ Q&A)
- **[docs/ROUND_1_QUESTIONS.md](docs/ROUND_1_QUESTIONS.md)** — defensible answers to the four round-1 questions
- **[docs/ROUND_2_EXPECTED.md](docs/ROUND_2_EXPECTED.md)** — anticipated round-2 deep dives, including the bio/proteomics pivot
- **[docs/DSR_MAPPING.md](docs/DSR_MAPPING.md)** — Design Science Research mapping
- **[docs/QUALITATIVE_SUMMARY.md](docs/QUALITATIVE_SUMMARY.md)** — qualitative findings summary

## Acknowledgements

University of Bradford MSc Computing programme; thesis supervisor and
viva panel.

## License

TBD.
