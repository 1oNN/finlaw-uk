"""Citation normaliser — maps common near-miss UK regulatory citations into
their strict short-form. Used by the chat post-processing step and (from
Stage 3 onward) by the graph-grounded verifier to canonicalise citations
before lookup."""

from __future__ import annotations

import re

REMAP = [
    (re.compile(r"\bCOBS\s+4\.2\b", re.I), "COBS 4.2.1R"),
    (re.compile(r"\bCOBS\s+9A\b", re.I), "COBS 9A.2"),
    (re.compile(r"\bFSCS\b.*£\s*85[, ]?000", re.I), "COMP 10.2"),
    (re.compile(r"\bFSMA\b.*(general\s+prohibition|s\.?19)", re.I), "FSMA 2000 s.19"),
    (re.compile(r"\bRAO\b.*(advis|arrang)", re.I), "RAO 2001 art.53"),
    (re.compile(r"\bRAO\b.*art\.?\s*25\b", re.I), "RAO 2001 art.25"),
    (re.compile(r"\bMLR\s*2017.*(CDD|due diligence|reg\.?\s*27)", re.I), "MLR 2017 reg.27"),
    (re.compile(r"\bMLR\s*2017.*(HRTC|high[- ]?risk|reg\.?\s*33)", re.I), "MLR 2017 reg.33"),
    (re.compile(r"\bPSR\s*2017.*(unauthorised|unauthorized|reg\.?\s*77)", re.I), "PSR 2017 reg.77"),
    (re.compile(r"\bPSR\s*2017.*reg\.?\s*7[8-9]\b", re.I), "PSR 2017 reg.78"),
    (re.compile(r"\bUK\s*MAR.*(inside information|art\.?\s*17)", re.I), "UK MAR art.17"),
    (re.compile(r"\bUK\s*MAR.*(insider list|art\.?\s*18)", re.I), "UK MAR art.18"),
    (re.compile(r"\bDTR\s*2\b", re.I), "DTR 2"),
    (re.compile(r"\bPROD\s*4\b", re.I), "PROD 4"),
    (re.compile(r"\bICOBS\s*7\b", re.I), "ICOBS 7"),
]


def normalise_citations(text: str) -> str:
    out = text
    for pat, repl in REMAP:
        out = pat.sub(repl, out)
    out = re.sub(r"[ \t]+", " ", out)
    return out
