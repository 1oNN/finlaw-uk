# Requirements

What you need installed and how much disk / RAM the project asks for.

## Operating system

- **Windows 10 / 11** with WSL2 enabled (this is the primary development OS), **or**
- **macOS 12+**, **or**
- **Linux** (Ubuntu 22.04 or comparable)

## Python

- **Python 3.11.x** (tested) or **3.12.x** (tested). 3.10 may work but is not exercised.
- `pip` and `venv` available.

```powershell
python --version       # should report 3.11.x or 3.12.x
```

Create and activate a virtualenv before installing anything:

```powershell
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

## Node.js (frontend)

- **Node 18 LTS or newer**, with `npm`.
- Verified with Node 20.

```powershell
node --version         # v18.x.x or higher
npm --version
```

## Docker

- **Docker Desktop** (Windows / macOS) with the WSL2 backend, **or** Docker Engine on Linux.
- The daemon must be running before any Neo4j operations.
- Ports **7474** (Neo4j Browser) and **7687** (Bolt) must be free on the host.

## Ollama

Install **natively** (not in Docker). https://ollama.com.

- Service running on `127.0.0.1:11434`.
- One model pulled:
  ```bash
  ollama pull mistral:7b-instruct
  ```
- Verify with `ollama list`.

## Hardware

| Resource | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| Disk free | 20 GB | 40 GB |
| CPU | 4 cores | 8 cores |
| GPU | not required | optional (CUDA accelerates Stages 1 + 5) |

**Why these numbers.** Mistral 7B in Ollama uses ~4-5 GB resident; BGE-small uses ~600 MB; Neo4j 2-4 GB; the dev environment + browser + node take the rest. The 20 GB disk minimum accounts for model downloads — see breakdown below.

If you opt into the HF transformers Mistral judge for RAGAS (Stage 5), add another ~14 GB of disk and another ~14 GB resident during eval runs. Default Ollama judge avoids that cost.

## Cumulative download budget

These appear over the first run of each stage:

| Source | Size | Triggered by |
|---|---:|---|
| `mistral:7b-instruct` via Ollama | ~4.1 GB | first chat |
| `BAAI/bge-small-en-v1.5` via sentence-transformers | ~134 MB | first dense retrieval (Stage 1) |
| `legislation.gov.uk` XML cache (5 docs) | ~29 MB | first `scripts/ingest_legislation.py` (Stage 2) |
| `pdfplumber` lazy font tables | small | first PDF ingestion (Stage 2) |
| Python wheels + Node packages | ~1.5 GB | `pip install` + `npm install` |
| **(Optional, Stage 5)** `mistralai/Mistral-7B-Instruct-v0.2` via HF | ~14 GB | only if `RAGAS_JUDGE=hf` |
| **(Optional)** `cross-encoder/ms-marco-MiniLM-L-6-v2`, NLI models, etc. | varies | future stages |

## Python dependencies

Top-level `requirements.txt` is the source of truth. Highlights:

- Web: `flask`, `flask-cors`, `werkzeug`
- Retrieval: `neo4j`, `rank-bm25`, `requests`, `sentence-transformers`, `faiss-cpu`
- Ingestion: `lxml`, `langchain-text-splitters`, `pdfplumber`, `PyPDF2`, `pdfminer.six`, `python-docx`, `openpyxl`, `python-pptx`, `pandas`
- Evaluation: `numpy`, `matplotlib`, `rouge`, `ragas`, `datasets`, `langchain-core`, `langchain-community`
- Dev: `python-dotenv`, `pytest`

Install all of it with `pip install -r requirements.txt`. The first install takes 5-15 minutes depending on network and whether wheels are available for your platform.

## Frontend dependencies

`frontend/package.json` is the source of truth. React 18 + Tailwind 3 + Axios + react-markdown.

```powershell
cd frontend
npm install
```

## Troubleshooting checklist

- **"Ollama not reachable"** — `ollama list` should respond. If not, start the Ollama service. On Windows it auto-starts at login; verify it's running in the system tray.
- **"Model 'mistral:7b-instruct' is not installed"** — run `ollama pull mistral:7b-instruct`.
- **Neo4j connection refused** — `docker ps` should show the neo4j container as `Up`. If not, `docker compose up -d` in the repo root.
- **Port 5000 already in use** — change `PORT` in `.env` or kill the offending process (`netstat -ano | findstr 5000` on Windows).
- **`ModuleNotFoundError`** — make sure the venv is activated (`Activate.ps1` on Windows; `source .venv/bin/activate` elsewhere) and `pip install -r requirements.txt` ran cleanly.
- **FAISS install fails on macOS Apple Silicon** — install with `pip install faiss-cpu==1.7.4` or build from source.
- **`backend.app` import error** — run from the repo root, not from inside `backend/`. The package layout requires the working directory to contain the `backend/` folder.
