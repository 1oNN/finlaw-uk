"""Neo4j driver singleton.

Provides a process-wide lazily-initialised Neo4j driver, plus a session
context manager. Centralises connection configuration that used to be
duplicated across the seed script, the traversal helper, and the retrieval
orchestrator's graph boost.

Environment:
    NEO4J_URI  (default: bolt://127.0.0.1:7687)
    NEO4J_USER (default: neo4j)
    NEO4J_PASS (default: finlaw)
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

try:
    from neo4j import GraphDatabase, Driver, Session
except Exception:
    GraphDatabase = None  # type: ignore
    Driver = object  # type: ignore
    Session = object  # type: ignore


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "finlaw")

_DRIVER: Optional["Driver"] = None


def get_driver() -> Optional["Driver"]:
    """Return the lazy-initialised driver, or None if the neo4j package
    is unavailable or the server cannot be reached at import time. Callers
    must check for None and fall back gracefully."""
    global _DRIVER
    if _DRIVER is not None:
        return _DRIVER
    if GraphDatabase is None:
        return None
    try:
        _DRIVER = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        return _DRIVER
    except Exception:
        return None


@contextmanager
def get_session() -> Iterator[Optional["Session"]]:
    """Context manager yielding a Neo4j session, or None if the driver
    is unavailable. Callers should handle the None case."""
    driver = get_driver()
    if driver is None:
        yield None
        return
    session = driver.session()
    try:
        yield session
    finally:
        try:
            session.close()
        except Exception:
            pass


def close_driver() -> None:
    """Close the driver if it was opened. Safe to call multiple times."""
    global _DRIVER
    if _DRIVER is not None:
        try:
            _DRIVER.close()
        except Exception:
            pass
        _DRIVER = None
