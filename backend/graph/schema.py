"""Neo4j schema constants — node labels, relationship types, indexes,
and constraints used across the seed and traversal modules.

The schema evolves stage-by-stage:

Stage 0 (legacy):
    Nodes:    Provision, Term
    Edges:    :MENTIONS (Term → Provision)
              :DEFINED_BY (Provision → Provision, one hardcoded link)
    Indexes:  provisionIdx, termIdx
    Constraints: provision_id UNIQUE, term_name UNIQUE

Stage 2 (XML + PDF ingestion):
    Adds many more Provision nodes; no schema change.

Stage 3 (graph enrichment, this stage):
    Adds nodes:    Regulator, Document
    Adds edges:    :CITES        (Provision → Provision; cross-references)
                   :ISSUED_BY    (Provision → Regulator)
                   :PART_OF      (Provision → Document)
    Reserved:      :RELATES_TO   (Provision ↔ Provision; declared, populated later)
                   :AMENDED_BY   (Provision → Provision; declared, populated later)
    Constraints:   regulator_name UNIQUE, document_name UNIQUE
"""

from __future__ import annotations

NODE_LABELS = ("Provision", "Term", "Regulator", "Document")

RELATIONSHIP_TYPES = (
    "MENTIONS",
    "DEFINED_BY",
    "CITES",
    "RELATES_TO",
    "AMENDED_BY",
    "ISSUED_BY",
    "PART_OF",
)

CONSTRAINTS = (
    "CREATE CONSTRAINT provision_id IF NOT EXISTS FOR (p:Provision) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT term_name IF NOT EXISTS FOR (t:Term) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT regulator_name IF NOT EXISTS FOR (r:Regulator) REQUIRE r.name IS UNIQUE",
    "CREATE CONSTRAINT document_name IF NOT EXISTS FOR (d:Document) REQUIRE d.name IS UNIQUE",
)

FULLTEXT_INDEXES = (
    "CALL db.index.fulltext.createNodeIndex('provisionIdx', ['Provision'], "
    "['title','text','cite','terms','module','domain'])",
    "CALL db.index.fulltext.createNodeIndex('termIdx', ['Term'], ['name'])",
)

PROVISION_FULLTEXT_INDEX = "provisionIdx"
TERM_FULLTEXT_INDEX = "termIdx"


# Known UK financial regulators — seeded as Regulator nodes during Stage 3.
KNOWN_REGULATORS = (
    {"name": "FCA", "full_name": "Financial Conduct Authority"},
    {"name": "PRA", "full_name": "Prudential Regulation Authority"},
    {"name": "HMT", "full_name": "His Majesty's Treasury"},
    {"name": "ESMA", "full_name": "European Securities and Markets Authority"},
    {"name": "BoE", "full_name": "Bank of England"},
)


# Known UK regulatory documents — seeded as Document nodes during Stage 3.
KNOWN_DOCUMENTS = (
    {"name": "FSMA 2000", "full_name": "Financial Services and Markets Act 2000", "kind": "primary"},
    {"name": "RAO 2001", "full_name": "FSMA 2000 (Regulated Activities) Order 2001", "kind": "secondary"},
    {"name": "MLR 2017", "full_name": "Money Laundering Regulations 2017", "kind": "secondary"},
    {"name": "PSR 2017", "full_name": "Payment Services Regulations 2017", "kind": "secondary"},
    {"name": "UK MAR", "full_name": "UK Market Abuse Regulation (retained)", "kind": "retained_eu"},
)
