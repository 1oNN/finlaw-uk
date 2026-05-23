"""Neo4j seeder.

Three sources:
    --source xml     : legislation.gov.uk XML (Stage 2 primary)
    --source pdfs    : on-disk FCA/PRA PDFs under backend/data/ (Stage 2 supplementary)
    --source both    : XML + PDFs (default)
    --source legacy  : the original 17 hardcoded provisions (Stage 0 baseline,
                       kept for A/B comparison and for offline use)

The schema is the same in all cases — `Provision` and `Term` nodes with a
`:MENTIONS` edge from each Term to its Provision, plus the legacy
`:DEFINED_BY` edge between `FSMA 2000 s.19` and `RAO 2001 art.5`. Stage 3
extends the graph with `:CITES`, `:RELATES_TO`, `Regulator`, `Document`
nodes.
"""

from __future__ import annotations

import argparse
import logging
from typing import Dict, List

from backend.graph.client import get_session
from backend.graph.extract_xrefs import extract_all_by_id
from backend.graph.schema import KNOWN_DOCUMENTS, KNOWN_REGULATORS

log = logging.getLogger(__name__)


LEGACY_PROVISIONS: List[Dict] = [
    {"id": "FSMA19", "cite": "FSMA 2000 s.19", "title": "General prohibition",
     "text": "Offence to carry on a regulated activity in the UK unless authorised or exempt.",
     "module": "FSMA", "domain": "FSMA", "terms": "regulated activity|authorised|exempt", "threshold": "", "deadline": ""},
    {"id": "RAO5", "cite": "RAO 2001 art.5", "title": "Meaning of regulated activities",
     "text": "Defines regulated activity and exemptions context.",
     "module": "RAO", "domain": "FSMA", "terms": "regulated activity|exemption", "threshold": "", "deadline": ""},
    {"id": "RAO25", "cite": "RAO 2001 art.25", "title": "Arranging deals",
     "text": "Arranging, bringing about or making arrangements with a view to transactions.",
     "module": "RAO", "domain": "MiFID", "terms": "arranging deals|intermediation", "threshold": "", "deadline": ""},
    {"id": "RAO53", "cite": "RAO 2001 art.53", "title": "Advising on investments",
     "text": "Giving advice on investments/personal recommendations.",
     "module": "RAO", "domain": "MiFID", "terms": "personal recommendation|advice", "threshold": "", "deadline": ""},
    {"id": "COBS4", "cite": "COBS 4.2.1R", "title": "Financial promotions—fair, clear & not misleading",
     "text": "A firm must ensure a communication or a financial promotion is fair, clear and not misleading.",
     "module": "FCA", "domain": "Conduct", "terms": "financial promotion|fair clear not misleading", "threshold": "", "deadline": ""},
    {"id": "PRIN12", "cite": "PRIN 12", "title": "Consumer Duty",
     "text": "Act in good faith; avoid foreseeable harm; enable good outcomes; fair value.",
     "module": "FCA", "domain": "Conduct", "terms": "Consumer Duty|fair value|good outcomes", "threshold": "", "deadline": ""},
    {"id": "SYSC10", "cite": "SYSC 10", "title": "Conflicts of interest",
     "text": "Identify, prevent, manage, and disclose conflicts; maintain policies and records.",
     "module": "FCA", "domain": "Governance", "terms": "conflicts of interest|register|policy", "threshold": "", "deadline": ""},
    {"id": "ICOBS7", "cite": "ICOBS 7", "title": "Cancellation rights (insurance)",
     "text": "Cooling-off rights: typically 14 days; 30 days for pure protection/life.",
     "module": "FCA", "domain": "Insurance", "terms": "cancellation|cooling off", "threshold": "", "deadline": "14/30 days"},
    {"id": "COMP10_2", "cite": "COMP 10.2", "title": "FSCS deposit protection",
     "text": "£85,000 per person per firm for eligible deposits; joint accounts handled separately.",
     "module": "FCA", "domain": "Prudential", "terms": "FSCS|deposit protection", "threshold": "£85,000", "deadline": ""},
    {"id": "MLR27", "cite": "MLR 2017 reg.27", "title": "Customer due diligence",
     "text": "Identify and verify customer & beneficial owner; ongoing monitoring obligations.",
     "module": "HMT", "domain": "AML", "terms": "CDD|due diligence|beneficial owner", "threshold": "", "deadline": ""},
    {"id": "MLR33", "cite": "MLR 2017 reg.33", "title": "Enhanced due diligence",
     "text": "EDD for high-risk third countries and other specified triggers.",
     "module": "HMT", "domain": "AML", "terms": "EDD|high risk third countries|HRTC", "threshold": "", "deadline": ""},
    {"id": "PSR77", "cite": "PSR 2017 reg.77-80", "title": "Unauthorised payment liability & refund",
     "text": "Payer liability is capped unless fraud/gross negligence; PSP must refund promptly; SCA rules apply.",
     "module": "HMT", "domain": "Payments", "terms": "unauthorised payment|SCA|refund", "threshold": "£35", "deadline": ""},
    {"id": "UKMAR17", "cite": "UK MAR art.17", "title": "Disclose inside information",
     "text": "Issuers disclose inside information as soon as possible; delay permitted subject to conditions.",
     "module": "ESMA", "domain": "Market", "terms": "inside information|disclosure|delay", "threshold": "", "deadline": ""},
    {"id": "UKMAR18", "cite": "UK MAR art.18", "title": "Insider lists",
     "text": "Maintain and provide insider lists to the FCA on request.",
     "module": "ESMA", "domain": "Market", "terms": "insider list|issuer|FCA request", "threshold": "", "deadline": ""},
    {"id": "DTR2", "cite": "DTR 2", "title": "Disclosure rules",
     "text": "Periodic and ongoing disclosure framework aligned with market abuse regime.",
     "module": "FCA", "domain": "Market", "terms": "disclosure|issuer", "threshold": "", "deadline": ""},
    {"id": "SYSC15A", "cite": "SYSC 15A", "title": "Operational resilience",
     "text": "Identify important business services; set impact tolerances; mapping and scenario testing.",
     "module": "FCA", "domain": "Ops", "terms": "operational resilience|impact tolerance|IBS", "threshold": "", "deadline": ""},
    {"id": "PROD4", "cite": "PROD 4", "title": "Product governance",
     "text": "Target market; distribution; fair value across the product lifecycle.",
     "module": "FCA", "domain": "Conduct", "terms": "product governance|fair value", "threshold": "", "deadline": ""},
]

SCHEMA_CYPHER = [
    "CREATE CONSTRAINT provision_id IF NOT EXISTS FOR (p:Provision) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT term_name IF NOT EXISTS FOR (t:Term) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT regulator_name IF NOT EXISTS FOR (r:Regulator) REQUIRE r.name IS UNIQUE",
    "CREATE CONSTRAINT document_name IF NOT EXISTS FOR (d:Document) REQUIRE d.name IS UNIQUE",
    "CALL db.index.fulltext.createNodeIndex('provisionIdx', ['Provision'], ['title','text','cite','terms','module','domain'])",
    "CALL db.index.fulltext.createNodeIndex('termIdx', ['Term'], ['name'])",
]

MERGE_PROVISION = """
MERGE (p:Provision {id: $id})
SET p.cite = $cite, p.title = $title, p.text = $text,
    p.module = $module, p.domain = $domain,
    p.threshold = $threshold, p.deadline = $deadline
"""

MERGE_TERM_REL = """
UNWIND $terms AS t
WITH trim(toLower(t)) AS name
WHERE name <> ''
MERGE (term:Term {name: name})
WITH term
MATCH (p:Provision {id: $id})
MERGE (term)-[:MENTIONS]->(p)
"""

LINKS_CYPHER = """
MATCH (a:Provision {cite:'FSMA 2000 s.19'}), (b:Provision {cite:'RAO 2001 art.5'})
MERGE (a)-[:DEFINED_BY]->(b);
"""

MERGE_REGULATOR = """
MERGE (r:Regulator {name: $name})
SET r.full_name = $full_name
"""

MERGE_DOCUMENT = """
MERGE (d:Document {name: $name})
SET d.full_name = $full_name, d.kind = $kind
"""

MERGE_PROVISION_REGULATOR = """
UNWIND $rows AS row
MATCH (p:Provision {id: row.id})
MATCH (r:Regulator {name: row.regulator})
MERGE (p)-[:ISSUED_BY]->(r)
"""

MERGE_PROVISION_DOCUMENT = """
UNWIND $rows AS row
MATCH (p:Provision {id: row.id})
MATCH (d:Document {name: row.document})
MERGE (p)-[:PART_OF]->(d)
"""

# Source matched by id (unique). Target matched by cite — head() picks one
# representative chunk so we don't create N×M edges when both endpoints have
# been split across multiple chunks.
MERGE_CITES_EDGE = """
UNWIND $rows AS row
MATCH (a:Provision {id: row.source_id})
MATCH (b:Provision {cite: row.target_cite})
WITH a, head(collect(b)) AS rep
WHERE rep IS NOT NULL
MERGE (a)-[:CITES]->(rep)
"""


def seed_provisions(provisions: List[Dict], enrich: bool = True) -> None:
    """Seed the base provision graph. If `enrich=True`, also populate
    Regulator + Document nodes, :ISSUED_BY / :PART_OF edges, and :CITES
    cross-references (Stage 3 enrichment)."""
    with get_session() as sess:
        if sess is None:
            raise RuntimeError(
                "Neo4j session unavailable — check NEO4J_URI / credentials and that the server is running."
            )
        for c in SCHEMA_CYPHER:
            try:
                sess.run(c).consume()
            except Exception:
                pass
        for row in provisions:
            sess.run(MERGE_PROVISION, **row).consume()
            terms = [t.strip() for t in (row.get("terms", "") or "").split("|")]
            sess.run(MERGE_TERM_REL, id=row["id"], terms=terms).consume()
        # Legacy defined-by edge (only meaningful if the two legacy cites are present)
        try:
            sess.run(LINKS_CYPHER).consume()
        except Exception:
            pass

        if enrich:
            _enrich_graph(sess, provisions)

        _print_summary(sess)


def _enrich_graph(sess, provisions: List[Dict]) -> None:
    """Stage 3: Regulator/Document nodes + :ISSUED_BY/:PART_OF/:CITES edges."""
    for r in KNOWN_REGULATORS:
        sess.run(MERGE_REGULATOR, **r).consume()
    for d in KNOWN_DOCUMENTS:
        sess.run(MERGE_DOCUMENT, **d).consume()

    known_regulator_names = {r["name"] for r in KNOWN_REGULATORS}
    known_document_names = {d["name"] for d in KNOWN_DOCUMENTS}

    regulator_rows = [
        {"id": p["id"], "regulator": (p.get("regulator") or p.get("module") or "").strip()}
        for p in provisions
        if (p.get("regulator") or p.get("module") or "").strip() in known_regulator_names
    ]
    if regulator_rows:
        sess.run(MERGE_PROVISION_REGULATOR, rows=regulator_rows).consume()

    document_rows = [
        {"id": p["id"], "document": (p.get("document") or "").strip()}
        for p in provisions
        if (p.get("document") or "").strip() in known_document_names
    ]
    if document_rows:
        sess.run(MERGE_PROVISION_DOCUMENT, rows=document_rows).consume()

    cite_rows = [
        {"source_id": src, "target_cite": tgt}
        for src, tgt in extract_all_by_id(provisions)
    ]
    if cite_rows:
        # Run in chunks so a very large pair list doesn't blow query limits.
        chunk_size = 1000
        for i in range(0, len(cite_rows), chunk_size):
            sess.run(MERGE_CITES_EDGE, rows=cite_rows[i : i + chunk_size]).consume()


def _print_summary(sess) -> None:
    nprov = sess.run("MATCH (p:Provision) RETURN count(p) AS n").single()["n"]
    nterm = sess.run("MATCH (t:Term) RETURN count(t) AS n").single()["n"]
    nreg = sess.run("MATCH (r:Regulator) RETURN count(r) AS n").single()["n"]
    ndoc = sess.run("MATCH (d:Document) RETURN count(d) AS n").single()["n"]
    n_cites = sess.run("MATCH ()-[r:CITES]->() RETURN count(r) AS n").single()["n"]
    n_iss = sess.run("MATCH ()-[r:ISSUED_BY]->() RETURN count(r) AS n").single()["n"]
    n_part = sess.run("MATCH ()-[r:PART_OF]->() RETURN count(r) AS n").single()["n"]
    print(
        f"Seed complete. Provisions={nprov}  Terms={nterm}  Regulators={nreg}  Documents={ndoc}"
    )
    print(f"  Edges: :CITES={n_cites}  :ISSUED_BY={n_iss}  :PART_OF={n_part}")

    sample = sess.run(
        """
        CALL db.index.fulltext.queryNodes('provisionIdx', $q) YIELD node, score
        RETURN node.cite AS cite, node.title AS title, score
        ORDER BY score DESC LIMIT 5
        """,
        q="consumer duty OR regulated activity OR due diligence",
    ).data()
    print("Sample fulltext hits:")
    for s in sample:
        print(f"  {s['cite']}: {s['title']} (score {s['score']:.3f})")


def _collect_provisions(source: str) -> List[Dict]:
    if source == "legacy":
        print(f"Source: legacy ({len(LEGACY_PROVISIONS)} hardcoded provisions)")
        return list(LEGACY_PROVISIONS)

    out: List[Dict] = []
    if source in ("xml", "both"):
        from backend.graph.ingest_xml import ingest_all
        xml_prov = ingest_all()
        print(f"Source: XML — {len(xml_prov)} provisions")
        out.extend(xml_prov)
    if source in ("pdfs", "both"):
        from backend.graph.extract_pdfs import ingest_pdfs
        pdf_prov = ingest_pdfs()
        print(f"Source: PDFs — {len(pdf_prov)} provisions")
        out.extend(pdf_prov)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Neo4j with UK finance-regulation provisions."
    )
    parser.add_argument(
        "--source",
        choices=["xml", "pdfs", "both", "legacy"],
        default="both",
        help="Provision source. Default: both (XML + PDFs).",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Shorthand for --source legacy.",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip Stage 3 enrichment (Regulator/Document nodes, :CITES, :ISSUED_BY, :PART_OF).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    source = "legacy" if args.legacy else args.source

    from backend.graph.client import NEO4J_URI, NEO4J_USER
    print(f"Connecting to {NEO4J_URI} as {NEO4J_USER} …")
    provisions = _collect_provisions(source)
    if not provisions:
        print("No provisions collected — aborting.")
        return
    print(f"Seeding {len(provisions)} total provisions (enrich={not args.no_enrich}) …")
    seed_provisions(provisions, enrich=not args.no_enrich)


if __name__ == "__main__":
    main()
