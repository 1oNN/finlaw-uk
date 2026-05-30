"""Live smoke test for the post-polish FinLaw-UK backend.

Hits the running Flask server at 127.0.0.1:5000 with eight test prompts and
prints, for each one, the intent label inferred from the server log AND the
shape of the assistant's response.

Pattern checks per response:
    - no 'Q:' line
    - no 'A:' line prefix
    - no '^Source:' footer
    - paren-style inline cite '(FCA Handbook ...)' or '(PRA Rulebook ...)'
      or '(FSMA ...)' on regulatory answers
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:5000"

import os
_RERUN = os.environ.get("SMOKE_RERUN") == "1"

_ALL_CASES = [
    # (label,           prompt,                                                 expected_intent_hint)
    ("META_NAME",       "What's your name?",                                    "meta"),
    ("META_MODEL",      "what model are you?",                                  "meta"),
    ("META_WORK",       "how do you work?",                                     "meta"),
    ("GREETING",        "hi",                                                   "greeting"),
    ("OUT_OF_SCOPE_1",  "What's the law on UK speeding tickets?",               "out_of_scope"),
    ("OUT_OF_SCOPE_2",  "Tell me a joke",                                       "out_of_scope"),
    ("REGULATORY_DISP", "What is the deadline for handling a DISP complaint?",  "regulatory_question"),
    ("REGULATORY_SYSC", "What does SYSC 4.1.1R require?",                       "regulatory_question"),
    ("REGULATORY_PLAIN", "What is the deadline for handling a complaint about a current account?", "regulatory_question"),
]

if _RERUN:
    CASES = [c for c in _ALL_CASES if c[0] in ("REGULATORY_DISP", "REGULATORY_PLAIN", "REGULATORY_SYSC")]
else:
    CASES = _ALL_CASES

QA_LEAK = re.compile(r"(?m)^\s*\*{0,2}\s*(Q|A)\s*[:]\s")
SOURCE_FOOTER = re.compile(r"(?im)^\s*\*{0,2}\s*Source\s*:")
INLINE_PAREN_CITE = re.compile(r"\((?:FCA Handbook|PRA Rulebook|FSMA|RAO|MLR|PSR|UK MAR|FSA)\b[^)]*\)", re.I)
# An actual citation token (chapter.section.rule) — distinct from just naming
# the FCA Handbook as a source category. Used to flag rule-recitation in
# responses where it should NOT appear (meta / greeting / out_of_scope).
SPECIFIC_CITATION = re.compile(
    r"\b(?:DISP|COBS|SYSC|PRIN|CONC|ICOBS|MCOB|PROD|COMP|COLL|DTR|MAR)\s+\d+(?:\.\d+)+",
    re.I,
)
FSMA_SECTION = re.compile(r"\bFSMA\s*2000\s*s\.?\s*\d", re.I)


def stream_chat(prompt: str) -> tuple[str, dict]:
    """POST to /api/chat/stream, accumulate token data, return (body, meta)."""
    payload = {"prompt": prompt, "mode": "auto"}
    body_parts: list[str] = []
    meta: dict = {}
    with requests.post(f"{BASE}/api/chat/stream", json=payload, stream=True, timeout=240) as r:
        r.raise_for_status()
        event = None
        for raw in r.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            if raw.startswith("event:"):
                event = raw.split(":", 1)[1].strip()
                continue
            if raw.startswith("data:"):
                payload_part = raw[5:]
                if event == "meta":
                    try:
                        meta.update(json.loads(payload_part))
                    except Exception:
                        pass
                    event = None
                    continue
                if event == "done":
                    break
                body_parts.append(payload_part)
                event = None
    return "".join(body_parts), meta


def check(label: str, prompt: str, body: str, expected_hint: str) -> list[str]:
    problems: list[str] = []
    if QA_LEAK.search(body):
        problems.append("Q/A_LEAKAGE")
    if SOURCE_FOOTER.search(body):
        problems.append("SOURCE_FOOTER_LEFTOVER")
    if expected_hint == "regulatory_question":
        if not INLINE_PAREN_CITE.search(body):
            problems.append("MISSING_INLINE_PAREN_CITE")
        if len(body.strip()) < 80:
            problems.append("ANSWER_TOO_SHORT")
    if expected_hint == "meta":
        # The META_PROMPT explicitly allows the assistant to name its sources
        # (FCA Handbook, PRA Rulebook, UK statutes) — that's identity, not
        # rule recitation. We only flag if it actually CITES a specific rule,
        # e.g. 'DISP 1.6.2R' or 'FSMA 2000 s.19'.
        if SPECIFIC_CITATION.search(body) or FSMA_SECTION.search(body):
            problems.append("META_RECITED_SPECIFIC_RULE")
        if "source:" in body.lower():
            problems.append("META_HAS_SOURCE_LINE")
    if expected_hint == "out_of_scope":
        if SPECIFIC_CITATION.search(body) or FSMA_SECTION.search(body):
            problems.append("OOS_RECITED_SPECIFIC_RULE")
    if expected_hint == "greeting":
        if SPECIFIC_CITATION.search(body) or FSMA_SECTION.search(body):
            problems.append("GREETING_RECITED_SPECIFIC_RULE")
    return problems


def main() -> int:
    print(f"\nLive smoke test against {BASE}\n{'=' * 78}")
    results = []
    for label, prompt, expected in CASES:
        t0 = time.time()
        try:
            body, meta = stream_chat(prompt)
        except Exception as e:
            print(f"\n[{label}]  prompt={prompt!r}")
            print(f"  ERROR: {e}")
            results.append((label, "ERROR", [str(e)]))
            continue
        dt = time.time() - t0
        problems = check(label, prompt, body, expected)
        verdict = "PASS" if not problems else "FAIL"
        print(f"\n[{label}]  expected={expected}  {verdict}  {dt:.1f}s")
        print(f"  prompt: {prompt!r}")
        print(f"  body:   {body.strip()[:380].replace(chr(10), ' ⏎ ')}")
        if problems:
            print(f"  [FAIL] problems: {problems}")
        else:
            print(f"  [ok] no leakage, shape ok")
        results.append((label, verdict, problems))

    print(f"\n{'=' * 78}")
    passed = sum(1 for _, v, _ in results if v == "PASS")
    failed = len(results) - passed
    print(f"Summary: {passed} pass, {failed} fail (of {len(results)})")
    for label, v, problems in results:
        if v != "PASS":
            print(f"   - {label:18s} {v}: {problems}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
