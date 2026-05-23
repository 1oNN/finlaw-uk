# Round 1 Questions — Defensible Answers

The four questions asked in the first Karolinska interview, with the
upgraded answers grounded in the current code. Each entry has:

1. **The question** as it was asked.
2. **What was said in round 1** — what the candidate actually answered
   (fill in from memory; placeholder here).
3. **The upgraded answer** — what to say in round 2 if the question
   comes up again or is followed up on.
4. **Likely follow-ups** the interviewer might press on.

> The system has materially improved between round 1 and round 2. It's
> fine — and honest — to say "since round 1 I've upgraded the system to
> X" when describing the current state.

---

## Q1. Why did you integrate Knowledge Graph with RAG?

### What was said in round 1
*(fill in from memory)*

### Upgraded answer
There are three things vector retrieval alone cannot do, and each of
them matters for a hallucination-conscious compliance system:

1. **Symbolic citation verification.** When the model writes "FSMA 2000
   s.19", I need to confirm that provision *actually exists*. With a
   vector store I'd be checking "is there a chunk near this embedding"
   — that's a soft match. With Neo4j I do `MATCH (p:Provision {cite:
   "FSMA 2000 s.19"})` — that's an exact match against a structured
   entity. Either the provision exists or it doesn't.

2. **Multi-hop traversal.** UK legislation is densely
   cross-referenced. FSMA 2000 s.19 references RAO 2001 art.5 (definition
   of regulated activity). RAO 2001 art.5 references RAO 2001 art.25,
   art.53, art.61. A user asking about the general prohibition often
   benefits from seeing the activities those references unpack into.
   `MATCH (seed)-[:CITES|MENTIONS*1..2]-(related)` returns that
   neighbourhood in one query. Vector search can't reason about
   citation chains.

3. **Typed disambiguation.** "MAR" in the FCA Handbook is the Market
   Conduct sourcebook. "UK MAR" is the retained EU Market Abuse
   Regulation. They're different documents with overlapping vocabulary.
   The graph keeps them apart by linking each Provision to its Document
   and Regulator nodes. Vector retrieval routinely conflates them.

The graph and RAG are *complementary*, not opposite (see Q4).

### Likely follow-ups
- "Couldn't you fake (1) with a metadata filter on chunks?" — Yes,
  partially, but you'd lose (2) and (3). The graph centralises the
  structural reasoning in one place.
- "Did you measure how often vector-only confuses MAR vs UK MAR?" —
  Not formally; it's qualitatively obvious in spot-checking sparse-only
  responses. An ablation study (`RAG_ENABLE_GRAPH=0`) would quantify it.

---

## Q2. How did you upload data into Neo4j Knowledge Graph?

### What was said in round 1
The thesis version used 17 hardcoded `Provision` dictionaries in
`seed_neo4j_finlaw.py`. The candidate likely described that.

### Upgraded answer
Three sources, dispatched by a single CLI:

```powershell
python scripts/seed_neo4j.py --source both   # XML + PDFs (default)
python scripts/seed_neo4j.py --source xml    # XML only
python scripts/seed_neo4j.py --source pdfs   # PDFs only
python scripts/seed_neo4j.py --legacy        # original 17 provisions (baseline)
```

**Source 1: legislation.gov.uk XML** (`backend/graph/ingest_xml.py`):
- Five primary sources: FSMA 2000, RAO 2001, MLR 2017, PSR 2017, UK MAR.
- `fetch_xml` caches each XML payload to `data/raw/<slug>.xml` so
  re-runs are offline.
- `parse_legislation_xml` walks `<P1>` elements (the canonical
  "provision" tag), pulls the title from the parent `<P1group>`, the
  number from `<Pnumber>` or the `id` attribute, and the body text via
  `itertext()`.
- Sections longer than 1500 chars are split by LangChain's
  `RecursiveCharacterTextSplitter` (chunk_size=1500, overlap=150) —
  *clause-level segmentation* in the recommendation letter's phrasing.
- Repealed sections (which legislation.gov.uk renders as ". . . . .")
  are filtered out by a non-filler character count.
- Real numbers: **2,634 provisions** parsed in the latest run.

**Source 2: FCA / PRA PDFs** (`backend/graph/extract_pdfs.py`):
- Walks `backend/data/{fca, pra_pdfs}/`. ~6 FCA Handbook PDFs + ~103
  PRA documents.
- `pdfplumber` extracts text page-by-page.
- The same chunker fragments each PDF.
- Module detection is filename-based (`COBS.pdf` → module="COBS",
  regulator="FCA"). Cites are synthetic
  (`COBS (COBS p1)`) — that's a known limitation for the cross-reference
  pass.

**Source 3: legacy 17 hardcoded provisions** — preserved as
`LEGACY_PROVISIONS` in `backend/graph/seed.py` for A/B comparison and
offline use when neither XML nor PDFs are available.

After provisions are seeded, the same script populates:
- 5 `Regulator` nodes (FCA, PRA, HMT, ESMA, BoE)
- 5 `Document` nodes (FSMA 2000, RAO 2001, MLR 2017, PSR 2017, UK MAR)
- `:ISSUED_BY` edges (Provision → Regulator) — one per provision
- `:PART_OF` edges (Provision → Document) — one per provision
- `:CITES` edges via `extract_xrefs.py` — ~2,600 in the latest run

The full pipeline takes ~5 minutes on the user's box (first run
downloads ~29 MB of XML; subsequent runs are cache-only and ~1 minute).

### Likely follow-ups
- "Why XML over PDF for legislation?" — XML has the structural markup
  (`<P1>`, `<Title>`, `<P1para>`) that lets clause-level segmentation
  work out of the box. PDF would need OCR-grade heuristics for the same
  output.
- "How do you handle amendments?" — Not yet. `:AMENDED_BY` is declared
  in the schema but unpopulated. legislation.gov.uk has effective-date
  metadata in the XML; populating that edge is on the future-work list.
- "What about the FCA Handbook directly from API rather than PDF?" —
  The FCA publishes the Handbook as HTML, not API. Scraping is doable
  but they ToS-restrict bulk download.

---

## Q3. What were the steps you took in RAG?

### What was said in round 1
The thesis version had a 5-step sparse cascade in `rag_helper.py`:
phrase regex → keyword overlap → BM25 → upload fallback → remote
legislation.gov.uk search. The candidate may have described this.

### Upgraded answer
The pipeline is now hybrid + graph + verified. Eight steps:

1. **Graph boost** — fulltext query on Neo4j's `provisionIdx` index
   returns top-6 seed provisions. `neighbors_2hop` expands via
   `:CITES|:MENTIONS|:DEFINED_BY` for related provisions.
2. **Hybrid document retrieval** —
   - BM25 (`backend/retrieval/sparse.py::search_bm25`)
   - Dense (`backend/retrieval/dense.py::DenseRetriever.search`,
     BGE-small + FAISS `IndexFlatIP`)
   - Reciprocal Rank Fusion
     (`backend/retrieval/hybrid.py::reciprocal_rank_fusion`,
     `rrf_k=60`).
3. **Fallback cascade** — if hybrid returns nothing, fall through to
   phrase → keyword → uploaded-document concat → remote
   legislation.gov.uk lookup. This is the legacy 5-step cascade
   preserved as a safety net.
4. **Prompt assembly** — graph context first (highest authority),
   document snippets second, user prompt last, under the relevant mode
   system prompt (general / finance / traffic-light).
5. **Generation** — Mistral 7B-Instruct via Ollama, streamed token by
   token. Chain-of-thought blocks (`<think>...</think>`) are suppressed
   but their elapsed time is reported via SSE meta.
6. **Post-processing** — scrub known-bad tokens, normalise near-miss
   citations (`citations.normalise_citations`), fix currency mojibake,
   append a `Source:` line if missing.
7. **Verification + claim trace** —
   `verify_answer(full_text, context_cites)` looks up every cite
   against Neo4j; `trace_all(full_text, verified_cites)` maps each
   sentence-level claim to its best-supporting cited provision.
8. **Stream out** — token frames during steps 5-6, consolidated audit
   in `event:meta` after step 7, `event:done` to close the stream.

The thesis version's 5-step *sparse* cascade is now layer 3 of this
pipeline, not the primary path.

### Likely follow-ups
- "Why this ordering, not graph last?" — Graph hits are the most
  *authoritative* (structured short-form citations), so they go first
  in the prompt. Putting them last would let document chunks (less
  precise) dominate the model's attention budget.
- "How big is your top-k?" — `TOPK=3` for the hybrid output. Graph
  boost returns top-6 seeds + up to 20 related cites from the 2-hop
  expansion. The model sees ~5-8 distinct snippets per query.
- "Why not re-ranking?" — A cross-encoder re-ranker (e.g.
  `ms-marco-MiniLM-L-6-v2`) would help precision. It's on the future-
  work list; the current pipeline doesn't have one because BGE-small +
  RRF + graph was already a meaningful jump over BM25-only.

---

## Q4. KG and RAG are completely opposite. What if one accepts something and the other rejects it — what did you do?

This is the most interesting question. The premise — "KG and RAG are
opposite" — is worth gently pushing back on.

### What was said in round 1
*(fill in from memory)*

### Upgraded answer
**They're not opposite — they're complementary.** RAG is *retrieval*;
the KG is *verification* and *expansion*. The KG and the dense
retriever index different things and answer different questions:

- The dense retriever indexes the document corpus and answers
  "*which paragraphs of text are nearest to this question?*"
- The KG indexes structured entities and answers "*does this exact cite
  refer to a real provision, and what's its neighbourhood?*"

But the question is still real: in practice the two layers can produce
results that don't agree. The system handles this in two ways:

**(a) Pre-generation: union, not intersection.**
The model sees *both* the graph hits and the document hits in its
prompt context. They're not gated by each other — if the dense
retriever surfaces a relevant paragraph the graph doesn't know about,
the model still sees it. The two layers *vote in*, they don't *veto*.
This handles the case where, say, the graph has FSMA 2000 s.21 but the
dense retriever surfaces a PRA policy statement on financial promotions
that lives in `backend/data/pra_pdfs/`. Both go to the model.

**(b) Post-generation: verification, not retraction.**
Once the model emits an answer, `verify_answer` looks up every cite in
the answer against the graph. Mismatches are *flagged* in the SSE meta
envelope and a `⚠️` footer is appended to the visible response. The
answer is not retracted — the user still sees it — because:

1. The retrieval and verification layers have different jobs.
   Retrieval is best-effort; verification is decisive.
2. A flagged citation might be the model paraphrasing legitimately
   ("section 19 of FSMA") rather than inventing. Better to tell the
   user "double-check this" than to silently delete the citation.
3. The system fails open if the graph is unavailable
   (`note: "graph_unavailable"`) — the user gets the answer with no
   warning, rather than no answer.

So the resolution rule is: **for retrieval, use the union; for
verification, use the graph as ground truth and surface conflicts to
the user.** This is the design pattern I'd carry into a biology
context too — vector search for fuzzy retrieval, structured graph
lookup for hard verification, both surfaced to the human in the loop.

### Likely follow-ups
- "Have you measured how often they disagree?" — Not formally. The
  `event:meta` envelope ships `verification.hallucinated_context` which
  reports cites that appear in the answer but not in the retrieval
  context — that's the metric to track over the 80-question eval set.
- "What if the user trusts the model more than the graph?" — The
  warning footer is opinionated. The user can override by checking
  manually. The audit trail (the consolidated meta event) gives the
  compliance team the data they need to retrain the prompt or extend
  the citation normaliser if a specific paraphrase pattern keeps
  failing.
- "Could you use the graph to *constrain* generation instead of
  verifying after?" — Constrained decoding (e.g., forcing the model to
  pick from a list of valid cites) is a possible direction. It's
  expensive at inference time and brittle when the right answer isn't
  in the candidate set. Post-hoc verification is the cheaper, more
  honest path for a research prototype.
