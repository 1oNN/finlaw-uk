#!/usr/bin/env python3
"""Thin CLI that delegates to `backend.graph.seed.main()`.

Run from the repo root:
    python scripts/seed_neo4j.py                  # XML + PDFs
    python scripts/seed_neo4j.py --source xml
    python scripts/seed_neo4j.py --source pdfs
    python scripts/seed_neo4j.py --legacy         # original 17 provisions
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.graph.seed import main

if __name__ == "__main__":
    main()
