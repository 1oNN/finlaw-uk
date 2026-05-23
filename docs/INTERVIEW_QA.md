# Interview Preparation — Q&A

Comprehensive answers grounded in the actual code as it stands today.
Use these as starting points, not scripts; the interviewer will follow up.

> Every claim in this document is checkable. If an answer cites
> `backend/retrieval/dense.py::DenseRetriever` you can open the file
> live and walk them through it.

## §1 — About the dissertation

### 1. Tell me about your dissertation.
FinLaw-UK is a graph-augmented RAG chatbot for UK financial regulation.
The MSc submission combined a Neo4j knowledge graph of UK statutory and
regulatory provisions with a locally-deployed Mistral 7B-Instruct
generator. It was implemented as a Flask backend with a React frontend
and graded MSc with Merit by the University of Bradford. Since
submission I've upgraded the codebase so that every architectural claim
in the application materials — dense vector embeddings, LangChain
chunking, HF Transformers, real RAGAS evaluation, symbolic verification —
is literally true in the code, not just aspirational.

### 2. Why UK financial regulation specifically?
Three reasons. First, UK finance law is *structured*: FSMA 2000, the
FCA Handbook (COBS / SYSC / PRIN etc.), MLR 2017, PSR 2017, RAO 2001,
UK MAR all have machine-readable short-form citations and consistent
cross-reference patterns. That's a clean substrate for a knowledge graph.
Second, the domain has high-stakes hallucination cost — a model that
invents a citation can cause real compliance failures. Third, I had
practical exposure: I built it during the dissertation period when
RAG-with-citations was an active topic for fintech compliance teams.

### 3. What was the research question?
*Can a graph-augmented retrieval pipeline with symbolic verification
reduce citation hallucination compared to a sparse-only baseline, while
keeping the entire system locally deployable?* The "locally deployable"
constraint mattered because the target users are compliance officers
who can't send privileged material to a cloud API.

### 4. What were the contributions?
1. A hybrid architecture combining sparse + dense retrieval with a graph
   boost from Neo4j — Reciprocal Rank Fusion fuses BM25 and BGE-small
   results.
2. A clause-level ingestion pipeline that produces structured
   `Provision` nodes from legislation.gov.uk XML and FCA/PRA PDF
   sourcebooks.
3. A graph-grounded citation verification layer that catches
   model-invented short-forms before they reach the user.
4. A reproducible evaluation harness using the real `ragas` library and
   a local Mistral judge.

### 5. Why graph-augmented RAG, not just RAG?
RAG alone retrieves text. A knowledge graph layers *structure* on top:
typed entities (Provision, Term, Regulator, Document), typed
relationships (`:CITES`, `:MENTIONS`, `:ISSUED_BY`, `:PART_OF`), and
multi-hop traversal. That structure lets me do three things vector
retrieval can't:
- **Symbolic citation verification** — look up "FSMA 2000 s.19" and
  confirm a real provision node exists with that exact cite.
- **2-hop expansion** — if the seed retrieves COBS 4.2.1R, the graph
  finds related provisions transitively via `:CITES` edges in one Cypher
  query.
- **Disambiguation by regulator** — "MAR" in FCA Handbook ≠ UK MAR.
  Linking each Provision to its Regulator and Document keeps these
  apart without context engineering on the prompt side.

## §2 — System architecture

### 6. Walk me through the architecture end-to-end.
*(See [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) for the diagram.)* A
chat request hits Flask. The orchestrator queries Neo4j fulltext for
seed provisions (`get_graph_boost`) and runs hybrid retrieval over the
document corpus (`get_raw_context` → BM25 + BGE-small → RRF). Both
contexts go into the prompt with mode-specific system instructions
(general / finance / traffic-light). Mistral streams tokens via Ollama;
SSE relays them to the React frontend. After the full text is buffered,
post-processing scrubs known-bad tokens, normalises near-miss
citations, and runs Stage 4 verification: every cite in the answer is
looked up in Neo4j; mismatches get flagged in an `event:meta` event and
appended as a warning footer.

### 7. Why hybrid sparse + dense retrieval?
They fail in complementary ways. BM25 is precise on rare technical
terms ("FSCS", "Pillar 2A", "PRIN 12") because they're discriminative
tokens. Dense embeddings catch paraphrases ("financial promotion" ≈
"investment advert") that lose all overlap with BM25. RRF
(`reciprocal_rank_fusion` in `hybrid.py`) is the right fusion algorithm
because it's score-agnostic — it works on ranks, not raw similarity
scores from different scales.

### 8. Why BGE-small-en-v1.5 specifically?
Three constraints: (1) English-only since UK legislation is English-only;
(2) sentence-level granularity since I encode whole clauses; (3) small
enough to run on CPU. BGE-small is 384-dimensional, ~134 MB, top-3 on
MTEB at its size class. The bigger BGE-large would buy ~2 points on MTEB
but quadruple the memory and inference cost on a CPU. For a single-user
deployment this trade-off favours small.

### 9. Why FAISS over Pinecone / Weaviate / Qdrant?
This system is single-process and the corpus is small (~3,000
provisions plus document chunks). `IndexFlatIP` is exact (no approximate
search needed at this scale), zero-ops (no separate process), and the
on-disk format is a portable NumPy `.npy` file plus a JSON sidecar — no
opaque binary serialisation, no proprietary format, easy to inspect or
migrate. If the corpus ever grew past ~1 M vectors I'd switch to
`IndexIVFFlat` or `IndexHNSWFlat`.

### 10. Why Reciprocal Rank Fusion?
RRF (Cormack, Clarke & Buettcher 2009) sums `1 / (rrf_k + rank)`
across ranked lists. Three properties matter:
- **Score-scale agnostic** — BM25 scores and cosine scores are on
  totally different scales; sum-of-similarity fusion would be biased.
- **Robust to one bad backend** — if dense returns garbage for a query,
  its ranks 1..N dilute over the `rrf_k=60` denominator instead of
  dominating.
- **Documented and reproducible** — the literature default (`rrf_k=60`)
  is what compliance-conscious reviewers expect.

### 11. Why a knowledge graph and not just vector search?
*(See also Q5.)* Vector search retrieves the nearest neighbours of an
embedding. It can't *verify* whether a citation is real, find
*transitive* references, or scope by *regulator*. The graph is the
substrate for symbolic operations the embedding space can't express.

### 12. Why local LLM via Ollama?
- **Data sovereignty.** Compliance officers can't send privileged
  documents to OpenAI.
- **Reproducibility.** Cloud APIs change behaviour silently; a pinned
  local model doesn't.
- **Cost.** A single workstation can serve the chat for a small
  compliance team; the API rate-limits and bills.
- **Inspectability.** I can profile the generator, swap quantisation
  levels, modify the system prompt without redeploying anything.

The trade-off is quality: Mistral 7B is markedly weaker than GPT-4.
The graph and the verification layer are how I claw quality back.

### 13. How does the verification mechanism work?
Three steps, all in `backend/verification/`:
1. **Normalise** common near-miss citations via 15 regex remappings in
   `citations.py` (e.g. `COBS 4.2` → `COBS 4.2.1R`).
2. **Lookup** every extracted cite against `Provision.cite` in Neo4j
   (`graph_verify.verify_citations_batch` — one round-trip).
3. **Trace** each sentence-level claim to its best supporting cited
   provision by non-stopword token overlap (`claim_trace.trace_all`).

Results land in the SSE `event:meta` envelope as
`{verified, unverified, hallucinated_context, all_grounded, claim_trace}`.

## §3 — Specific technical

### 14. Walk me through your RAG steps in detail.
1. **Query in** — POST to `/api/chat/stream` with `{prompt, mode}`.
2. **Graph boost** — fulltext query on `provisionIdx` returns top-6
   provisions; `neighbors_2hop` expands via `:CITES|:MENTIONS|:DEFINED_BY`
   for related provisions; bullets + source line returned.
3. **Hybrid document retrieval** — BM25 over the file corpus and dense
   search over the same corpus; RRF fuses both ranked lists. Falls
   back to phrase → keyword → upload → remote if hybrid is empty.
4. **Prompt assembly** — graph bullets first (highest authority),
   document snippets second, then the user question, all under the
   relevant mode system prompt.
5. **Generation** — Ollama streams tokens; `<think>...</think>`
   reasoning blocks are suppressed but their elapsed time is reported
   in an `event:meta` frame.
6. **Post-processing** — scrub known-bad tokens, normalise citations,
   fix currency mojibake, append a `Source:` line if missing.
7. **Verification + trace** — Stage 4 audits each citation against the
   graph and traces each claim to its best-supporting provision.
8. **Emit** — SSE delivers tokens then a final `event:meta` with the
   consolidated audit JSON.

### 15. How does cross-reference extraction work?
`backend/graph/extract_xrefs.py` has two passes:
- **Statutory + handbook regex** matches fully-qualified citations
  ("FSMA 2000 s.19", "COBS 4.2.1R") anywhere in text.
- **Context-aware regex** is keyed by `source_document`: when
  processing a clause from FSMA 2000, bare "section 22" is treated as
  "FSMA 2000 s.22". This is essential because legislation cross-refers
  *internally* without repeating the act name.

Output is filtered against the known cite set so dangling edges to
non-existent provisions are never created. On the real corpus this
produces ~2,600 `:CITES` edges across 845 distinct target provisions.

### 16. What's the role of LangChain in your system?
LangChain is used in two places, both intentionally narrow:
1. **`RecursiveCharacterTextSplitter`** in `ingest_xml.py` for
   clause-level chunking when a single XML section exceeds 1500 chars.
   The brief picked LangChain *only for chunking* (pick #18 = B) — I
   didn't want a heavyweight orchestrator framework wrapping the rest
   of the pipeline.
2. **`langchain-community.ChatOllama`** wraps the local Ollama server
   as a `LangChain` LLM so the RAGAS judge interface accepts it
   directly. The graph and retrieval code does not import LangChain.

The opt-in HF judge path (`backend/llm/hf_client.py`) also subclasses
`langchain_core.language_models.llms.LLM` for the same reason.

### 17. How are chunks built — clause-level segmentation?
The XML parser walks `<P1>` elements (the canonical "provision" tag
across Acts / SIs / EUR documents on legislation.gov.uk). Each `P1`
becomes one `Provision` node. If its text exceeds 1500 characters,
`RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150,
separators=["\n\n","\n",". "," ",""])` splits it into multiple
`Provision` nodes that share the same `cite` but have unique IDs
(`FSMA2000_s19_chunk0`, `_chunk1`, …). That preserves the citation
shape but keeps each indexed unit small enough for the embedding
model.

### 18. How does the 2-hop graph traversal work?
`backend/graph/traversal.py::neighbors_2hop` runs this Cypher:
```cypher
UNWIND $cites AS c
MATCH (seed:Provision {cite: c})
MATCH path = (seed)-[:CITES|MENTIONS|DEFINED_BY*1..2]-(related:Provision)
WHERE related <> seed
WITH related, min(length(path)) AS hops
...
```
The bidirectional `*1..2` matches both 1-hop neighbours
(direct cross-references) and 2-hop (transitive cites, and the
shared-term bridge `Provision <-[:MENTIONS]- Term -[:MENTIONS]->
Provision`). I take `min(length(path))` so a provision reachable in
both 1 and 2 hops is reported with its shortest path.

### 19. What's "symbolic verification" in your system?
The recommendation letter's phrase. Concretely: every cite the model
emits is normalised to canonical short-form and looked up as a Neo4j
`Provision.cite` value. A match is "grounded" — the citation refers to
something the graph knows. A miss is `unverified` — the model invented
or misrendered the cite. The frontend receives both lists, and the
response body gets a `⚠️` footer if anything is unverified. This is
*symbolic* because we're checking against a structured graph of
discrete entities, not embedding similarity.

### 20. How do you handle the model citing a non-existent provision?
The chat doesn't abort — RAG is generative, blocking the answer would
be worse UX than flagging. Specifically:
1. Stage 0/legacy `find_invalid_citations` checks against an *allowlist*
   regex pattern (catches gross syntactic invalidity like
   "FCAS" / "FPM").
2. Stage 4 `verify_answer` checks against the *actual graph contents*
   (catches semantically invalid cites that pass the regex).
3. If either check fails, the response is appended with a clearly-
   marked warning footer, AND the `event:meta` envelope reports the
   exact list of unverified cites for downstream tooling.
4. The user sees the answer; they also see they should double-check the
   flagged cites manually.

### 21. How is chat history persisted?
In the current build it isn't — the frontend stores per-chat messages
in `localStorage` (see `Chat.js::CHAT_LIST_KEY`). The
`/api/chats/{id}/messages` endpoint and the JWT / Google-OAuth UI are
*stubs* — there's no Python backend handling them. This was an early
exploration that didn't make it into the final architecture. The
practical path forward is either (a) wire them up to a Flask+SQLAlchemy
backend, or (b) remove the stubs entirely. I went with leaving them in
since the cost is just a few unused components and they signal
infrastructure I'd build next.

## §4 — Evaluation

### 22. How did you evaluate the system?
Two tiers. The thesis reports lexical metrics (Jaccard, ROUGE-L,
BERTScore) over 80 balanced questions across 8 domains — that's the
historical baseline. After thesis submission I wired up the real
`ragas` library with a local Mistral judge for four model-based
metrics: faithfulness, answer relevancy, context precision, context
recall. Both tiers run from the same question set via
`scripts/run_evaluation.py --mode both`. Per-question CSVs land in
`data/eval_results/` with timestamps.

### 23. What are RAGAS metrics?
- **Faithfulness** — does every claim in the answer follow from the
  retrieved contexts? The judge LLM decomposes the answer into claims,
  then checks each against the contexts. High = no hallucination.
- **Answer relevancy** — does the answer actually address the
  question? Generates synthetic questions from the answer and measures
  similarity back to the original.
- **Context precision** — were the retrieved contexts relevant to the
  question? Per-position precision; higher = less noise.
- **Context recall** — did the contexts cover the ground-truth answer?
  Higher = retrieval didn't miss anything.

The faithfulness and answer-relevancy scores are the most informative
for a hallucination-conscious system; precision/recall diagnose where
the retrieval needs work.

### 24. Why is the local Mistral judge biased?
A 7B model is markedly less accurate at meta-evaluation than GPT-4.
Specifically:
- **Self-preference bias** — when the same model generates and judges,
  it tends to over-rate its own output.
- **Length bias** — short answers score lower on faithfulness because
  fewer claims = fewer chances to score well, even when the answer is
  correct.
- **Format sensitivity** — Mistral judges struggle with markdown
  bullets vs prose; absolute scores aren't comparable across answer
  formats.

Mitigation: treat scores as **relative** (system A vs B on the same
question set, judged by the same model), not absolute. For an absolute
benchmark, swap in GPT-4 as the judge (one config change in
`ragas_eval._build_judge_llm`).

### 25. What were your numbers?
The most recent run lives in `data/eval_results/` (see
[`docs/RAGAS_RESULTS.md`](RAGAS_RESULTS.md) — placeholder table). The
thesis-era lexical numbers are in
`backend/results_full/run_*/eval_results.csv`.

### 26. How does this compare to GPT-4-only RAG?
For absolute accuracy, GPT-4 with the same retrieval would almost
certainly win — it's a stronger generator and a more reliable judge.
What FinLaw-UK adds is (1) no data leaves the host, (2) the graph
verification catches a class of error GPT-4 alone can't (invented
cite), and (3) the full stack is auditable. The right comparison
isn't "FinLaw-UK beats GPT-4 on quality" — it's "FinLaw-UK matches
GPT-4 on hallucination rate while keeping data local and the
verification step explicit."

### 27. What's the baseline you measured against?
The lexical metrics in the thesis report the system against itself
(no formal baseline). Going forward, the cleanest baselines are:
- **Sparse-only (BM25)** — disable the dense retriever
  (`RAG_ENABLE_DENSE=0`) and re-run.
- **No-graph** — disable the graph boost (`RAG_ENABLE_GRAPH=0`).
- **Vanilla RAG** — use only the legacy 5-step cascade
  (revert `get_context` pre-Stage-1).

These three ablations are what I'd run to defend Stages 1 and 3
quantitatively in a paper.

## §5 — Karolinska bio/proteomics pivot

### 28. How does this transfer to biology?
The architectural pattern — structured KG + dense retrieval +
LLM-with-verification — is domain-agnostic. UK legislation has
`Provision` / `Term` / `Regulator` / `Document` nodes connected by
`:CITES`, `:MENTIONS`, `:ISSUED_BY`. Translating that to proteomics:
- `Protein` / `Proteoform` (instead of Provision)
- `Gene`, `Pathway`, `Domain` (Pfam), `GO_Term` (instead of Term)
- `:CODED_BY` / `:PARTICIPATES_IN` / `:PHOSPHORYLATES` / `:CROSS_REF_TO`
  (instead of `:CITES`)
- `Database` (UniProt / Reactome / PhosphoSitePlus / Pfam) instead of
  Document.
The retrieval side stays the same — BGE-small still encodes function
descriptions and abstracts; the graph just describes a different
substrate.

### 29. What's a proteoform?
A proteoform is a specific molecular form of a protein from a single
gene — a particular combination of splice variant, allelic variation,
PTMs, and proteolytic processing. One gene typically codes for many
proteoforms with different functions. This is exactly the kind of
*structural* information a knowledge graph captures well: gene →
[multiple] proteoforms → [each with] modification sites → [linked to]
pathways and disease associations. Top-down mass spectrometry — which
the Lehtiö group uses heavily — produces proteoform-level data that's
naturally graph-shaped.

### 30. How would knowledge graphs apply to UniProt or Reactome?
UniProt already publishes RDF dumps. Reactome publishes pathway data
in BioPAX. Both can be loaded directly into Neo4j (there are public
loaders), giving you:
- ~250k human proteins as `Protein` nodes
- Per-protein cross-references to PDB, Pfam, InterPro, GO, ChEMBL
- Pathway hierarchies in Reactome
- Disease associations from DisGeNET / OMIM
Adding cancer-specific overlays (TCGA mutations, ProteomicsDB
abundance, PhosphoSitePlus PTMs) builds the substrate for queries
like "find proteins in the same pathway as TP53 that are differentially
phosphorylated in triple-negative breast cancer". That's the kind of
multi-hop biological reasoning a vector-only system can't express.

### 31. What's the Lehtiö group's main focus?
Top-down proteomics and proteogenomics for cancer. Specifically:
identifying actionable proteoforms via mass spectrometry, integrating
proteomics with genomics to find candidate therapeutic targets, and
exploring tumour heterogeneity at the single-cell proteome level. Yanbo
Pan's recent work has emphasised the computational side — turning
multi-omic measurements into ranked target lists.

### 32. What would your first PhD project look like?
The architecture I just shipped maps onto a useful biology problem:
*a graph-augmented RAG system for proteoform-level cancer biology that
helps researchers find and verify candidate therapeutic targets.*
Concretely:
1. **Substrate** — UniProt + Reactome + PhosphoSitePlus + cancer-specific
   overlays loaded into Neo4j.
2. **Retrieval** — dense embeddings over function descriptions and
   recent abstracts (from PubMed) plus graph queries for pathway
   neighbourhoods.
3. **Verification** — every protein the LLM mentions gets looked up
   against UniProt (same idea as the citation verifier but on
   `Protein.accession` instead of `Provision.cite`); every pathway
   claim gets traced to a Reactome stable ID. No mention of a protein
   the system can't ground.
4. **Application** — interactive target-prioritisation tool. The user
   describes a phenotype; the system surfaces ranked candidate
   proteoforms with the supporting MS data, pathway context, and
   literature.

That's a 3-year project shape, with thesis-sized contributions in the
LLM + ground-truth verification interface, the proteoform-aware
embeddings, and the user evaluation with bench scientists.

## §6 — Methodology + limitations

### 33. What's Design Science Research and how did you apply it?
DSR is a research methodology for building artefacts (software,
processes, models) and rigorously evaluating them — distinct from
purely descriptive research. Six steps applied to FinLaw-UK:
1. **Problem identification** — citation hallucination in
   compliance-facing LLMs.
2. **Define objectives** — locally-deployable, hallucination-flagged
   RAG over UK financial regulation.
3. **Design + develop** — hybrid retrieval + KG + verification + Mistral.
4. **Demonstration** — working system + sample chats.
5. **Evaluation** — RAGAS + lexical metrics on 80 balanced questions.
6. **Communication** — thesis, codebase, this document.
See `docs/DSR_MAPPING.md` for the full mapping.

### 34. What are the system's limitations?
- **Mistral 7B is not GPT-4.** Absolute answer quality is below
  cloud-LLM systems on hard questions.
- **The PDF corpus is not as structured as the XML.** Cross-reference
  extraction misses on PDF-derived provisions; their cites are
  synthetic (`COBS (COBS p1)` etc.).
- **Verification is exact-match.** A model that paraphrases a cite
  ("section 19 of the FSMA") gets normalised by `citations.py` but only
  if a remapping exists for that paraphrase pattern. New paraphrases
  need new regex entries.
- **The judge LLM is biased** (Q24). RAGAS scores are relative, not
  absolute.
- **The frontend auth stubs aren't wired up.** History persistence is
  localStorage-only.
- **No evaluation on real compliance questions.** The 80-question set is
  hand-curated, not drawn from production traffic.

### 35. What would you do with another year on FinLaw-UK?
Three things, in priority order:
1. **NLI-based claim verification.** Replace the keyword-overlap claim
   trace with a real entailment model (DeBERTa-v3-mnli, ~440 MB) —
   sound rejection of unsupported claims instead of best-effort scoring.
2. **Active-learning loop for new citation patterns.** When the
   `citations.py` normaliser fails on a real cite the user provides,
   propose a new remapping rule; user accepts or rejects.
3. **Continuous evaluation in CI.** Run the smoke-5 RAGAS suite on every
   PR with regression alerts on faithfulness drop > 5%.

### 36. How did you validate the design with users?
The qualitative chapter reports interviews with [TBD by user] compliance
practitioners; semi-structured interviews focused on (a) which RAG
shortcomings frustrate them in tools they use today, (b) what
verification UI they'd trust, and (c) which jurisdictions and
sourcebooks matter most for their day-to-day work. Findings shaped
three design choices: the four chat modes, the `Source:` footer
convention, and the warning-footer behaviour for unverified cites. See
`docs/QUALITATIVE_SUMMARY.md` for the structured summary.

### 37. What did the qualitative chapter find?
*(See `docs/QUALITATIVE_SUMMARY.md` — to be filled from the thesis.)*
Headline findings the candidate should be ready to articulate:
participants prioritised *citation accuracy* over fluency, distrusted
GPT-4 outputs that lacked traceable sources, and were comfortable with
local LLM responses being slightly worse if every claim was anchored
to a verifiable source. That's the audit-first product DNA the system
is built around.
