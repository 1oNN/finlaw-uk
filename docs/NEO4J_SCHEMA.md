# Neo4j Schema — FinLaw-UK

This document describes the live graph schema after Stage 3 enrichment. It
is the source of truth for queries written against the FinLaw-UK Neo4j
instance.

The schema evolved across the upgrade in three layers:

| Stage | Adds |
|---|---|
| **0** | `Provision`, `Term` nodes; `:MENTIONS`, `:DEFINED_BY` edges; constraints + fulltext indexes |
| **2** | More `Provision` nodes (XML + PDF ingestion); no schema change |
| **3** | `Regulator`, `Document` nodes; `:CITES`, `:ISSUED_BY`, `:PART_OF` edges |

Stage 4 (verification) reads from this schema; Stages 5–7 don't modify it.

## Node labels

### `Provision`
A single section / regulation / article from a UK financial-regulation source.

| Property | Type | Notes |
|---|---|---|
| `id` | string | Globally unique. Pattern: `<DOC><KIND><NUMBER>` (e.g. `FSMA2000_s19`, `MLR2017_reg27`) or `PDF_<slug>_c<chunk>` for PDF-sourced provisions. Constraint: UNIQUE. |
| `cite` | string | Canonical short citation (e.g. `FSMA 2000 s.19`, `MLR 2017 reg.27`, `COBS 4.2.1R`). NOT unique — multiple chunks of the same section share a cite. |
| `title` | string | Section / regulation heading. |
| `text` | string | Full text (or one chunk if > 1500 chars). |
| `module` | string | Regulator code or FCA Handbook book (`FSMA`, `FCA`, `HMT`, `ESMA`, `COBS`, etc.). |
| `domain` | string | Coarse topic tag (`FSMA`, `AML`, `Payments`, `Market`, `Conduct`, ...). |
| `threshold` | string | Optional — present on a handful of legacy provisions only (e.g. `£85,000`). |
| `deadline` | string | Optional — same as above (e.g. `14/30 days`). |

### `Term`
A normalised keyword that appears in one or more provisions. Used for term-based traversal and rough topic clustering.

| Property | Type | Notes |
|---|---|---|
| `name` | string | Lowercased term. Constraint: UNIQUE. |

### `Regulator`
A UK financial regulator. Five seeded nodes after Stage 3:

| Property | Type | Notes |
|---|---|---|
| `name` | string | Short code (`FCA`, `PRA`, `HMT`, `ESMA`, `BoE`). Constraint: UNIQUE. |
| `full_name` | string | E.g. "Financial Conduct Authority". |

### `Document`
A regulatory document. Five seeded nodes after Stage 3 (one per legislation source):

| Property | Type | Notes |
|---|---|---|
| `name` | string | Short citation key (`FSMA 2000`, `MLR 2017`, `PSR 2017`, `RAO 2001`, `UK MAR`). Constraint: UNIQUE. |
| `full_name` | string | Long title. |
| `kind` | string | `primary` / `secondary` / `retained_eu`. |

## Relationship types

| Type | From → To | Direction | Stage | Meaning |
|---|---|:---:|:---:|---|
| `:MENTIONS` | `Term → Provision` | directed | 0 | Term appears in this provision. |
| `:DEFINED_BY` | `Provision → Provision` | directed | 0 | Source defines a concept via target. (Legacy: one hardcoded edge from `FSMA 2000 s.19` to `RAO 2001 art.5`.) |
| `:CITES` | `Provision → Provision` | directed | 3 | Source provision references target by short-form citation in its text. |
| `:ISSUED_BY` | `Provision → Regulator` | directed | 3 | Source provision was issued by this regulator. |
| `:PART_OF` | `Provision → Document` | directed | 3 | Source provision belongs to this document. |
| `:RELATES_TO` | `Provision ↔ Provision` | undirected (reserved) | reserved | Declared in schema for future enrichment; not yet populated. |
| `:AMENDED_BY` | `Provision → Provision` | directed (reserved) | reserved | Reserved for future amendment-history modelling. |

## Indexes and constraints

```cypher
-- Uniqueness constraints
CREATE CONSTRAINT provision_id IF NOT EXISTS FOR (p:Provision) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT term_name IF NOT EXISTS FOR (t:Term) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT regulator_name IF NOT EXISTS FOR (r:Regulator) REQUIRE r.name IS UNIQUE;
CREATE CONSTRAINT document_name IF NOT EXISTS FOR (d:Document) REQUIRE d.name IS UNIQUE;

-- Fulltext indexes (created via the legacy `db.index.fulltext.createNodeIndex` API
-- so the existing seed code path keeps working; Neo4j 5+ also supports
-- `CREATE FULLTEXT INDEX`).
CALL db.index.fulltext.createNodeIndex('provisionIdx', ['Provision'],
    ['title','text','cite','terms','module','domain']);
CALL db.index.fulltext.createNodeIndex('termIdx', ['Term'], ['name']);
```

## Example queries

### Find provisions matching a question (entry point for `get_graph_boost`)

```cypher
CALL db.index.fulltext.queryNodes('provisionIdx',
  'consumer duty OR fair value OR good outcomes') YIELD node, score
RETURN node.cite AS cite, node.title AS title, score
ORDER BY score DESC LIMIT 6;
```

### 2-hop expansion from a seed cite

```cypher
MATCH (seed:Provision {cite: 'FSMA 2000 s.19'})
MATCH path = (seed)-[:CITES|MENTIONS|DEFINED_BY*1..2]-(related:Provision)
WHERE related <> seed
WITH related, min(length(path)) AS hops
RETURN related.cite AS cite, related.title AS title, hops
ORDER BY hops ASC LIMIT 20;
```

### Provisions issued by a specific regulator

```cypher
MATCH (p:Provision)-[:ISSUED_BY]->(r:Regulator {name: 'FCA'})
RETURN p.cite, p.title LIMIT 20;
```

### Cross-reference count per document

```cypher
MATCH (a:Provision)-[:PART_OF]->(d:Document)
MATCH (a)-[:CITES]->(b:Provision)
RETURN d.name AS document, count(*) AS cites_out
ORDER BY cites_out DESC;
```

### "Most-cited" provisions across the entire corpus

```cypher
MATCH ()-[r:CITES]->(p:Provision)
RETURN p.cite, p.title, count(r) AS times_cited
ORDER BY times_cited DESC LIMIT 15;
```

### Find the shortest citation path between two provisions

```cypher
MATCH p = shortestPath(
  (a:Provision {cite: 'FSMA 2000 s.19'})-[:CITES*..6]-(b:Provision {cite: 'RAO 2001 art.25'})
)
RETURN [n IN nodes(p) | n.cite] AS path;
```

### Term-bridge: provisions sharing a term

```cypher
MATCH (t:Term {name: 'consumer duty'})
MATCH (t)-[:MENTIONS]->(p:Provision)
RETURN p.cite, p.title LIMIT 20;
```

### Sanity-check counts after a seed run

```cypher
MATCH (p:Provision) RETURN count(p) AS provisions;
MATCH (t:Term) RETURN count(t) AS terms;
MATCH (r:Regulator) RETURN count(r) AS regulators;
MATCH (d:Document) RETURN count(d) AS documents;
MATCH ()-[c:CITES]->() RETURN count(c) AS cites_edges;
MATCH ()-[i:ISSUED_BY]->() RETURN count(i) AS issued_by_edges;
MATCH ()-[pt:PART_OF]->() RETURN count(pt) AS part_of_edges;
```

## Expected counts after `python scripts/seed_neo4j.py` (XML + PDFs)

These numbers come from a representative run against legislation.gov.uk as
of mid-2026; small fluctuations are expected as the source XML evolves.

| Entity | Count |
|---|---:|
| `Provision` | ~2,750 (XML 2,634 + PDFs 120+) |
| `Term` | ~100 (legacy terms only — Stage 3 doesn't add Terms) |
| `Regulator` | 5 (FCA, PRA, HMT, ESMA, BoE) |
| `Document` | 5 (FSMA 2000, MLR 2017, PSR 2017, RAO 2001, UK MAR) |
| `:CITES` | ~2,600 |
| `:ISSUED_BY` | ~2,634 (one per XML provision; PDF provisions only if regulator matches) |
| `:PART_OF` | ~2,634 (one per XML provision) |

## Verification flow (Stage 4)

After a chat response is generated, the post-processor extracts every
citation from the model output and looks each up against `Provision.cite`.
A citation that the graph can match is "grounded"; one that can't is
flagged as `unverified`. This mechanism is what the dissertation calls
"symbolic verification" — Stage 4 wires it into the SSE stream so the
frontend receives the audit alongside the answer.
