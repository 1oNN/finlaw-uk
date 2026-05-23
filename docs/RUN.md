# Run

Step-by-step setup for getting FinLaw-UK running locally. Estimated time
on a fresh machine: **15–30 minutes**, dominated by `pip install` and the
Mistral model pull.

For prerequisites (Python, Node, Docker, Ollama versions and hardware),
see [REQUIREMENTS.md](REQUIREMENTS.md).

## 1. Clone and create a virtualenv

```powershell
git clone <repo-url> Masters_project
cd Masters_project
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

## 2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

This pulls ~1.5 GB of wheels (sentence-transformers brings in torch).
Run once per machine.

## 3. Bring up Neo4j

```powershell
docker compose up -d
```

Wait ~15 seconds for Neo4j to be ready, then open
http://localhost:7474 to confirm the Browser is responding. Default
credentials are in `docker-compose.yml`: `neo4j` / `finlaw`.

## 4. Pull the Mistral model into Ollama

```powershell
ollama pull mistral:7b-instruct
ollama list                           # confirm 'mistral:7b-instruct' is present
```

If Ollama isn't installed yet, get it from https://ollama.com.
On Windows it auto-starts; verify it's running in the system tray.

## 5. Configure environment

```powershell
Copy-Item .env.example .env           # PowerShell
# macOS / Linux:
# cp .env.example .env
```

Edit `.env` if you want to change Neo4j credentials, the Ollama model,
or the eval output directory. Defaults are sensible for local dev.

## 6. Seed Neo4j with the legislation graph

```powershell
python scripts/ingest_legislation.py --sample 5     # dry run: ~2,634 provisions, prints samples
python scripts/seed_neo4j.py                        # populates Neo4j (5-10 minutes)
```

The first invocation of `scripts/ingest_legislation.py` downloads ~29 MB
of XML from legislation.gov.uk into `data/raw/`. Subsequent runs use the
cache.

After seeding, the Neo4j Browser will show:
- ~2,750 `Provision` nodes (XML + PDFs)
- 5 `Regulator` nodes (FCA, PRA, HMT, ESMA, BoE)
- 5 `Document` nodes (FSMA 2000, RAO 2001, MLR 2017, PSR 2017, UK MAR)
- ~2,600 `:CITES` edges, ~2,634 `:ISSUED_BY`, ~2,634 `:PART_OF`

To use the legacy 17-provision baseline instead (faster, useful for A/B
comparison):

```powershell
python scripts/seed_neo4j.py --legacy
```

## 7. Start the backend

```powershell
python -m backend.app
```

You should see:

```
>>> FinLaw GPT backend starting …
 * Running on http://0.0.0.0:5000
```

The first chat after backend start is slow (~30-90 seconds) because the
dense retriever builds its FAISS index over the local document corpus on
first use. Subsequent chats reuse the cache at `data/cache/`.

Hit http://localhost:5000/ in your browser; you should see the health
check string.

## 8. Start the frontend

In a second shell:

```powershell
cd frontend
npm install                            # first time only, ~3-5 minutes
npm start
```

Open http://localhost:3000 in a browser. Pick a chat mode (`auto`,
`general`, `finance`, `traffic-light`) and ask a question.

## 9. (Optional) Run the evaluation suite

Smoke test:

```powershell
python scripts/run_evaluation.py --sample 5 --mode ragas --verbose
```

Full run (80 questions; 30 min – 2 h on CPU):

```powershell
python scripts/run_evaluation.py --mode both --verbose
```

Output lands in `data/eval_results/` as timestamped CSVs.

## 10. Common smoke-test queries

To sanity-check that the system is wired together, ask these in the chat:

| Mode | Query | Expected behaviour |
|---|---|---|
| `general` | What's a good first book on UK financial regulation? | Generic helpful answer, no citation footer |
| `finance` | What is the UK general prohibition? | 4-6 sentences citing FSMA 2000 s.19; graph hit panel in DevTools shows seed cite |
| `finance` | What's the FSCS deposit protection limit? | Mentions £85,000 and COMP 10.2 |
| `traffic-light` | Run a traffic-light review of [paste any compliance text] | Four sections: 🟢 / 🟡 / 🟠 / 🔴 |
| `auto` | What CDD checks are required under MLR 2017? | Auto-routes to finance mode; cites MLR 2017 reg.27 |

## Troubleshooting

**Backend won't start: "ImportError: attempted relative import"**
You're running `python backend/app.py` from inside `backend/`. Always run
from the repo root: `python -m backend.app`.

**Chat returns "❌ Ollama not reachable"**
- `ollama list` should respond. If not, start the Ollama service.
- Check the Ollama base URL in `.env` (`OLLAMA_BASE_URL=http://127.0.0.1:11434`).
- If on WSL2 trying to reach Windows Ollama, set the URL to
  `http://host.docker.internal:11434`.

**"Neo4j session unavailable"**
- `docker ps` should show the neo4j container as `Up`.
- The credentials in `.env` (`NEO4J_USER`, `NEO4J_PASS`) must match the
  ones in `docker-compose.yml`. Defaults are `neo4j` / `finlaw`.
- After changing the password in the Neo4j Browser, the container's
  Cypher Shell will reject the old one — restart the container.

**Frontend shows "Backend error" for every query**
- Open DevTools → Network → look at the `/api/chat/stream` request.
- 404 means the backend isn't running on the URL the frontend expects.
- CORS-related errors mean `flask-cors` isn't installed; `pip install -r requirements.txt`.

**Dense index takes forever on first query**
- Set `RAG_DEBUG=1` in `.env` and restart. You'll see per-step progress in
  the backend log.
- The index builds from `backend/data/` PDFs which total ~120 MB. On a
  cold machine the first build is 60-120 seconds.
- Once `data/cache/dense_embeddings.npy` exists, restarts are <2 seconds.

**Pytest doesn't find the package**
- Run `python -m pytest tests/` (not `pytest tests/`). The `-m` form makes
  Python add the current directory to `sys.path`.

## Stopping everything

```powershell
# Backend: Ctrl-C in its shell
# Frontend: Ctrl-C in its shell
docker compose down                    # stop Neo4j
# Ollama keeps running in the background; quit from the system tray if needed
```

Data persists in `backend/neo4j-data/` (Docker volume) and
`data/cache/` (Python). To start fresh:

```powershell
docker compose down -v                 # also drops the Neo4j volume
Remove-Item -Recurse -Force data\cache\*
```
