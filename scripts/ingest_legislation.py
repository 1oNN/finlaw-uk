#!/usr/bin/env python3
"""CLI: fetch + parse the configured legislation.gov.uk XML sources and
optionally include supplementary PDF excerpts. Prints a count summary and
a handful of sample provisions for sanity-checking; does NOT touch Neo4j.

Usage:
    python scripts/ingest_legislation.py                # XML + PDFs
    python scripts/ingest_legislation.py --source xml
    python scripts/ingest_legislation.py --source pdfs
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

# Make the repo root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["xml", "pdfs", "both"],
        default="both",
    )
    parser.add_argument("--sample", type=int, default=5, help="How many sample provisions to print.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    provisions = []
    if args.source in ("xml", "both"):
        from backend.graph.ingest_xml import ingest_all
        xml_prov = ingest_all()
        provisions.extend(xml_prov)
        print(f"XML  : {len(xml_prov)} provisions")
        by_doc = Counter(p["document"] for p in xml_prov)
        for doc, n in by_doc.most_common():
            print(f"         {doc}: {n}")
    if args.source in ("pdfs", "both"):
        from backend.graph.extract_pdfs import ingest_pdfs
        pdf_prov = ingest_pdfs()
        provisions.extend(pdf_prov)
        print(f"PDFs : {len(pdf_prov)} provisions")
        by_module = Counter(p["module"] for p in pdf_prov)
        for mod, n in by_module.most_common():
            print(f"         {mod}: {n}")

    print(f"TOTAL: {len(provisions)} provisions")
    print()
    print(f"--- {args.sample} sample provisions ---")
    for p in provisions[: args.sample]:
        text = p["text"]
        snippet = text[:160] + ("…" if len(text) > 160 else "")
        print(f"\n[{p['cite']}]  {p['title']}")
        print(f"  id:       {p['id']}")
        print(f"  document: {p['document']} / regulator={p['regulator']} / domain={p['domain']}")
        print(f"  text:     {snippet}")


if __name__ == "__main__":
    main()
