#!/usr/bin/env python3
"""FinLaw GPT backend (Flask, SSE streaming).

Features:
    - Three chat modes: general, finance-QA, traffic-light review (Green/Yellow/Amber/Red).
    - Auto-routing on keywords (`is_finance_intent`, `is_traffic_light_intent`).
    - SSE streaming with anti-buffering headers (`X-Accel-Buffering: no`).
    - Optional graph boost: hits the Neo4j `provisionIdx` fulltext index and
      suggests a `Source:` line.
    - Strict citation post-processing: scrub bad tokens, normalise short forms,
      flag unverifiable citations to the client via SSE `meta` event.
    - File upload endpoint that ingests PDF/DOCX/TXT/XLS/XLSX/PPTX into the
      sparse retrieval index.

Run with `python -m backend.app` from the repo root.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

from backend.llm import ollama_client as llm
from backend.retrieval import session_index
from backend.retrieval.orchestrator import (
    get_context,
    get_context_and_cites,
    get_graph_boost,
)
from backend.verification.citations import normalise_citations
from backend.verification.claim_trace import trace_all
from backend.verification.graph_verify import verify_answer

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.abspath("./uploads"))
ALLOWED_EXTS = {"pdf", "docx", "txt", "md"}

STRICT_CITATIONS = bool(int(os.getenv("STRICT_CITATIONS", "1")))
CITATION_PATCH_ENABLED = bool(int(os.getenv("CITATION_PATCH_ENABLED", "1")))
GRAPH_VERIFY_ENABLED = bool(int(os.getenv("GRAPH_VERIFY_ENABLED", "1")))
CLAIM_TRACE_ENABLED = bool(int(os.getenv("CLAIM_TRACE_ENABLED", "1")))
CLAIM_TRACE_MAX_ITEMS = int(os.getenv("CLAIM_TRACE_MAX_ITEMS", "8"))

GENERAL_PROMPT = (
    "You are a helpful, friendly assistant. Answer clearly in Markdown.\n"
    "Use concise bullets when useful. If a file is provided, use it only as context."
)

SMALLTALK_PROMPT = (
    "You are FinLaw GPT. The user greeted you — they did NOT ask a question. "
    "Reply with a warm, casual 1-sentence greeting back (max 18 words). "
    "Examples of good replies:\n"
    "  • 'Hey — what's up?'\n"
    "  • 'Hi there! How can I help today?'\n"
    "  • 'Hello! What's on your mind?'\n"
    "STRICT RULES:\n"
    "  • DO NOT introduce yourself unless asked.\n"
    "  • DO NOT mention FSMA, COBS, SYSC, FCA, PRA, CRR, or any finance topic.\n"
    "  • DO NOT list what you can help with.\n"
    "  • DO NOT include a 'Source:' line."
)

FINANCE_QA_PROMPT = (
    "You are FinLaw-UK, an FCA technical specialist briefing a colleague on "
    "UK financial regulation. Answer using ONLY the context passages in "
    "this message. The register is technical-specialist, not chatbot.\n\n"
    "Format:\n"
    "1. The first sentence is the direct answer — one sentence, stating "
    "the rule's effect. Do NOT open with 'Here's a breakdown', 'In short', "
    "'Sure', or any other meta-summary.\n"
    "2. Then 2 to 4 short paragraphs of substantive explanation. Each "
    "paragraph develops one specific point. Plain prose; do not number them.\n"
    "3. Inline citations only, in parentheses with the source name. The\n"
    "   parenthetical is the ONLY acceptable form of citation. Use:\n"
    "     (FCA Handbook DISP 1.6.2R)    for DISP, COBS, MAR, SUP, SYSC, "
    "PRIN, CONC, ICOBS, MCOB, PROD, COMP, COLL, DTR.\n"
    "     (PRA Rulebook ...)            for any PRA-prefixed reference.\n"
    "     (FSMA 2000 s.19)              for FSMA / FSA 2012 / MLR 2017 / "
    "PSR 2017 / RAO 2001 / UK MAR — statutory short-form only, no source "
    "prefix needed.\n"
    "   Cite at the end of the sentence whose rule you are stating. Do NOT\n"
    "   invent citations not present in the context. Do NOT lead a sentence\n"
    "   with the rule name — e.g. NEVER write 'DISP 1.6.2R requires...' or\n"
    "   'As per **DISP 1.6.2R**, a firm must...'. Instead write the rule's\n"
    "   effect in plain English and append the parenthetical: 'A firm must\n"
    "   send a final response within eight weeks (FCA Handbook DISP 1.6.2R).'\n"
    "4. Bold is permitted ONLY inside the parenthetical citation, applied to\n"
    "   the rule code itself: '(FCA Handbook **DISP 1.6.2R**)'. Bold is\n"
    "   forbidden anywhere else. Do NOT bold rule names that appear outside\n"
    "   a parenthetical. Do NOT bold whole sentences, topic words, or\n"
    "   ordinary nouns.\n"
    "5. Use a bulleted or numbered list ONLY when the content is genuinely "
    "enumerative — a step-by-step procedure, a closed list of exceptions, "
    "a defined set of thresholds. Never bullet a single explanatory "
    "paragraph. Never bullet just to fill space.\n"
    "6. Do NOT write a 'Source:' line. Do NOT close with 'In summary', "
    "'Hope this helps', 'Let me know if', 'To summarize'. End on the last "
    "substantive sentence.\n"
    "7. No emoji. No URLs. No headings unless the answer truly spans "
    "multiple discrete topics.\n"
    "8. If the context does not contain the answer, reply EXACTLY: "
    "\"I do not have authoritative source material for this question.\"\n"
    "9. Do NOT repeat the user's question back to them. Do NOT write "
    "'Q:' or 'A:' anywhere in your reply.\n"
    "10. Use only retrieved passages that are genuinely on-point. If the "
    "context includes chunks on unrelated topics (e.g. reporting "
    "templates when the question is about authorisation), ignore those "
    "chunks rather than forcing them into the answer.\n"
    "11. Where the context covers the topic but not a specific detail "
    "(a section number, threshold, or date), flag the gap rather than "
    "guessing — e.g. \"I'm not certain of the exact section — verify "
    "against legislation.gov.uk\". A smaller, correct answer beats a "
    "padded, wrong one.\n"
    "12. Flag time-sensitivity. Rates, thresholds, and regulatory "
    "positions change; where this matters, point the user to the "
    "authoritative source (legislation.gov.uk, the FCA Handbook, the "
    "PRA Rulebook, HMRC).\n"
    "13. Explain reasoning and practical implications, not just a "
    "restatement of the rule. Cover the \"why\" and what it means in "
    "practice, not only the \"what\"."
)

FRUSTRATION_PROMPT = (
    "You are FinLaw GPT. The user sounds frustrated. "
    "Reply in EXACTLY TWO short sentences: (1) acknowledge that something seems off, "
    "(2) ask ONE clarifying question about what they were trying to find. "
    "Examples of good replies:\n"
    "  • 'Sorry, sounds like something's off — what were you trying to find?'\n"
    "  • 'Ugh, that's annoying. What were you hoping I could help with?'\n"
    "STRICT RULES:\n"
    "  • DO NOT introduce yourself.\n"
    "  • DO NOT mention FSMA, COBS, SYSC, FCA, PRA, or any finance topic.\n"
    "  • DO NOT list what you can do.\n"
    "  • DO NOT include a 'Source:' line."
)

EMPTY_PROMPT = (
    "You are FinLaw GPT. The user sent an empty or punctuation-only message. "
    "Reply with ONE short prompt-back (max 12 words). "
    "Examples:\n"
    "  • 'Did you mean to send something?'\n"
    "  • 'Hmm, looks blank — what's on your mind?'\n"
    "STRICT RULES:\n"
    "  • DO NOT introduce yourself.\n"
    "  • DO NOT mention finance, law, FSMA, COBS, or any topic.\n"
    "  • DO NOT include a 'Source:' line."
)

META_PROMPT = (
    "You are FinLaw GPT. The user is asking who or what you are. "
    "Reply in ONE friendly sentence (max 35 words): you answer UK finance-law "
    "questions (FSMA, COBS, SYSC, PRA Rulebook, CRR, etc.) and can run a "
    "traffic-light review on uploaded documents. "
    "Example: 'I'm FinLaw GPT — I help with UK finance regulation (FSMA, COBS, "
    "SYSC, PRA Rulebook) and can run traffic-light reviews on documents you upload.'\n"
    "DO NOT include a 'Source:' line."
)

TRAFFIC_LIGHT_PROMPT = (
    "You are LEGAL GPT, a senior UK finance-law reviewer.\n"
    "Produce a concise TRAFFIC-LIGHT review with exactly four sections and only bullets.\n\n"
    "## 🟢 Green Areas\n"
    "- Clear strengths or compliant items. One line each.\n\n"
    "## 🟡 Yellow Areas\n"
    "- Minor issues or clarifications needed. One line each. End with a short UK citation (e.g., '— COBS 4').\n\n"
    "## 🟠 Amber Areas\n"
    "- Material risks needing remediation. One line each with a short UK citation (e.g., '— MLR 2017 reg.27').\n\n"
    "## 🔴 Red Areas\n"
    "- Critical breaches or show-stoppers. One line each with a short UK citation (e.g., '— FSMA 2000 s.19').\n\n"
    "CITATION POLICY (STRICT): short-form UK primary sources only; no URLs."
)

app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.INFO)

def allowed_file(fn: str) -> bool:
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXTS


def _chunk_text(text: str, chunk_size: int = 1500, chunk_overlap: int = 150) -> List[str]:
    """Split text into chunks matching the corpus chunker (1500/150) so the
    session FAISS hits and the static corpus hits live on the same scale."""
    if len(text) <= chunk_size:
        return [text]
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
        except ImportError:
            return [p.strip() for p in text.split("\n\n") if p.strip()]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c.strip() for c in splitter.split_text(text) if c.strip()]


def clean_context(raw: str) -> str:
    if not raw:
        return ""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S | re.I)
    raw = re.sub(r"</?json>", "", raw, flags=re.I)
    return raw.strip()


def is_finance_intent(text: str) -> bool:
    if not text:
        return False
    kws = [
        r"\bloan\b", r"\bcredit\b", r"\bsecurity\b", r"\bcovenant",
        r"\bPRA\b", r"\bFCA\b", r"\bCRR\b", r"\bfacility\b",
        r"\bdebenture\b", r"\bcharge\b", r"\bUK finance\b",
        r"\bmifid\b", r"\bregulation\b", r"\bfsma\b", r"\bcobs\b", r"\bsysc\b",
        r"\bprin\b", r"\bconc\b", r"\bicobs\b", r"\bmortgage\b", r"\bmlr\b",
        r"\bmar\b", r"\bprod\b", r"\bdisp\b", r"\brao\b", r"\bpsr\b", r"\bdtr\b",
    ]
    return any(re.search(p, text, re.I) for p in kws)


def is_traffic_light_intent(text: str) -> bool:
    if not text:
        return False
    kws = [
        r"\btraffic[ -]?light\b", r"\bred flags?\b", r"\brisk review\b",
        r"\baudit\b", r"\bissues?\b", r"\bgreen\b.*\byellow\b.*\bamber\b.*\bred\b",
    ]
    return any(re.search(p, text, re.I) for p in kws)


_SMALLTALK_RE = re.compile(
    r"^(?:"
    r"hi|hello|hey|yo|hiya|hi there|hello there|hey there|"
    r"good\s+(?:morning|afternoon|evening|day)|"
    r"thanks|thank\s+you|cheers|ty|thx|much\s+appreciated|"
    r"bye|goodbye|see\s+you|see\s+ya|cya|later|"
    r"ok|okay|got\s+it|cool|nice|great|awesome|"
    r"how\s+are\s+you(?:\s+doing)?|how'?s\s+it\s+going|what'?s\s+up|sup|"
    r"who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|"
    r"what\s+do\s+you\s+do|what\s+is\s+this|help|introduce\s+yourself"
    r")[\s!.?,]*$",
    re.IGNORECASE,
)


def is_smalltalk_intent(text: str) -> bool:
    """Detect greetings / chitchat / meta-questions that should bypass RAG.

    Two layers: (1) explicit anchored regex for common pleasantries, and
    (2) a fallback for very short prompts (<=3 tokens) with no finance signal.
    Anchored so 'Hi, what is FSMA s.19?' is NOT treated as small-talk.
    """
    if not text:
        return False
    cleaned = text.strip().lower()
    if _SMALLTALK_RE.match(cleaned):
        return True
    tokens = re.findall(r"\w+", cleaned)
    if len(tokens) <= 3 and not is_finance_intent(text) and not is_traffic_light_intent(text):
        return True
    return False


_FRUSTRATION_RE = re.compile(
    r"\b(?:wtf|tf|wth|fml|stupid|broken|sucks?|fuck(?:ing)?|shit|damn|crap|"
    r"this\s+doesn'?t\s+work|doesn'?t\s+work|not\s+working|"
    r"hate\s+this|worst|useless|garbage|trash)\b",
    re.IGNORECASE,
)

_META_RE = re.compile(
    r"^(?:who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|"
    r"what\s+do\s+you\s+do|what\s+is\s+this|help|introduce\s+yourself)"
    r"[\s!.?,]*$",
    re.IGNORECASE,
)


def classify_intent(text: str) -> str:
    """Bucket a user message BEFORE retrieval.

    Returns one of: 'empty', 'frustration', 'meta', 'greeting', 'legal_query'.
    Order matters: frustration overrides greeting if profanity is present;
    legal_query is the default fall-through to the RAG pipeline.
    """
    if not text:
        return "empty"
    s = text.strip()
    if len(s) < 2 or re.fullmatch(r"[\s\W_]+", s):
        return "empty"
    if _FRUSTRATION_RE.search(s):
        return "frustration"
    s_lower = s.lower()
    if _META_RE.match(s_lower):
        return "meta"
    if _SMALLTALK_RE.match(s_lower):
        return "greeting"
    tokens = re.findall(r"\w+", s_lower)
    if len(tokens) <= 3 and not is_finance_intent(text) and not is_traffic_light_intent(text):
        return "greeting"
    return "legal_query"


# Per-session state, in-memory. Restart wipes; matches existing app behaviour.
# Used so the first turn for a session can mention capability, subsequent turns don't.
_SESSION_STATE: Dict[str, Dict[str, bool]] = {}


_CITE_PATTERNS = [
    r"(?:FSMA\s*2000\s*s\.?\s*\d+[A-Za-z]?)",
    r"(?:COBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G))",
    r"(?:SYSC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G))",
    r"(?:PRIN\s*\d+(?:\.\d+)*)",
    r"(?:CONC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G))",
    r"(?:ICOBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G))",
    r"(?:MCOB\s*\d+(?:\.\d+)*[A-Z]?(?:R|G))",
    r"(?:PROD\s*\d+(?:\.\d+)*)",
    r"(?:DISP\s*\d+(?:\.\d+)*[A-Z]?(?:R|G))",
    r"(?:COMP\s*\d+(?:\.\d+)*)",
    r"(?:COLL\s*\d+(?:\.\d+)*)",
    r"(?:UK\s*MAR\s*art\.?\s*\d+[A-Za-z]?)",
    r"(?:MLR\s*2017\s*reg\.?\s*\d+[A-Za-z]?)",
    r"(?:PSR\s*2017\s*reg\.?\s*\d+[A-Za-z]?)",
    r"(?:RAO\s*2001\s*art\.?\s*\d+[A-Za-z]?)",
    r"(?:DTR\s*\d+(?:\.\d+)*)",
]
_CITE_COMPILED = [re.compile(p, re.I) for p in _CITE_PATTERNS]
_BAD_TOKENS = [r"\[[0-9]+(?:†)?\]", r"https?://\S+", r"\bFCAS\b", r"\bFPM\b", r"\bPFB\b", r"\bSMDR\b"]
_BAD_COMPILED = [re.compile(p, re.I) for p in _BAD_TOKENS]


def extract_citation_candidates(text: str) -> List[str]:
    tokens = re.split(r"[;\|\n,•\-–—]+", text)
    return [t.strip() for t in tokens if t and len(t.strip()) >= 3]


def has_bad_token(s: str) -> bool:
    return any(p.search(s) for p in _BAD_COMPILED)


def matches_allowlist(s: str) -> bool:
    return any(p.search(s) for p in _CITE_COMPILED)


def find_invalid_citations(text: str) -> List[str]:
    invalid: List[str] = []
    snippets = re.findall(r"(?:^|[\(\[])([^()\[\]\n]{3,80})(?:[\)\]]|$)", text, flags=re.M)
    snippets += extract_citation_candidates(text)
    seen = set()
    for sn in snippets:
        s = " ".join(sn.split())
        if s in seen:
            continue
        seen.add(s)
        if not re.search(r"(FSMA|COBS|SYSC|PRIN|CONC|ICOBS|MCOB|PROD|DISP|COMP|COLL|UK\s*MAR|MLR|PSR|RAO|DTR)", s, re.I):
            continue
        if has_bad_token(s) or not matches_allowlist(s):
            invalid.append(s)
    uniq, u = [], set()
    for it in invalid:
        if it not in u:
            uniq.append(it)
            u.add(it)
    return uniq


def scrub_known_bad(text: str) -> str:
    text = re.sub(r"\[[0-9]+(?:†)?\]", "", text)
    text = re.sub(r"\(https?://\S+\)", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"</?sup>", "", text, flags=re.I)
    return text


def fix_currency(text: str) -> str:
    return text.replace("Â£", "£")


def patch_with_warning(text: str, invalid: List[str]) -> str:
    if not invalid:
        return text
    warn = (
        "\n\n> ⚠️ One or more citations could not be verified against UK short-forms. "
        "Please cross-check sources (FSMA 2000, FCA Handbook COBS/SYSC/PRIN/CONC/ICOBS/MCOB/PROD/DISP/COMP/COLL, "
        "PSR 2017, RAO 2001, UK MAR, DTR, MLR 2017)."
    )
    return text + warn


TL_HEADERS = [
    r"##\s*🟢\s*Green Areas", r"##\s*🟡\s*Yellow Areas",
    r"##\s*🟠\s*Amber Areas", r"##\s*🔴\s*Red Areas",
]
TL_HEADERS_RENDERED = [
    "## 🟢 Green Areas", "## 🟡 Yellow Areas",
    "## 🟠 Amber Areas", "## 🔴 Red Areas",
]


def coerce_to_traffic_light(md: str) -> str:
    text = md.strip()
    order_hits = [re.search(h, text, re.I) for h in TL_HEADERS]
    if all(order_hits) and order_hits == sorted(order_hits, key=lambda m: m.start()):
        return re.sub(r"\n{3,}", "\n\n", text)

    lines = [ln.rstrip() for ln in text.splitlines()]
    buckets: Dict[str, List[str]] = {"green": [], "yellow": [], "amber": [], "red": []}
    current = None

    def pick_bucket_for_line(ln: str):
        s = ln.lower()
        if "green" in s:
            return "green"
        if "yellow" in s:
            return "yellow"
        if "amber" in s or "orange" in s:
            return "amber"
        if "red" in s or "critical" in s or "breach" in s:
            return "red"
        return current or "yellow"

    for ln in lines:
        if re.search(TL_HEADERS[0], ln, re.I):
            current = "green"
            continue
        if re.search(TL_HEADERS[1], ln, re.I):
            current = "yellow"
            continue
        if re.search(TL_HEADERS[2], ln, re.I):
            current = "amber"
            continue
        if re.search(TL_HEADERS[3], ln, re.I):
            current = "red"
            continue
        if ln.strip().startswith("-"):
            buckets[pick_bucket_for_line(ln)].append(ln.strip())

    if not buckets["green"]:
        buckets["green"].append("- No clear strengths identified from the supplied material.")
    if not buckets["yellow"]:
        buckets["yellow"].append("- Clarifications required on scope, controls, or records — COBS 4")
    if not buckets["amber"]:
        buckets["amber"].append("- Potential non-conformity needs remediation — MLR 2017 reg.27")
    if not buckets["red"]:
        buckets["red"].append("- Critical breach / general prohibition risk — FSMA 2000 s.19")

    rebuilt = []
    rebuilt.append(TL_HEADERS_RENDERED[0]); rebuilt += buckets["green"]; rebuilt.append("")
    rebuilt.append(TL_HEADERS_RENDERED[1]); rebuilt += buckets["yellow"]; rebuilt.append("")
    rebuilt.append(TL_HEADERS_RENDERED[2]); rebuilt += buckets["amber"]; rebuilt.append("")
    rebuilt.append(TL_HEADERS_RENDERED[3]); rebuilt += buckets["red"]; rebuilt.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(rebuilt))


def bootstrap_answer(prompt: str) -> str:
    rules = [
        (r"\bgeneral prohibition\b",
         "The UK general prohibition makes it an offence to carry on a regulated activity unless authorised or an exemption applies.",
         "FSMA 2000 s.19 | RAO 2001 art.5"),
        (r"\bfinancial promotion\b|\bfair,? clear\b|\bnot misleading\b",
         "Financial promotions must be fair, clear and not misleading; restrictions apply unless approved by an authorised firm or an exemption applies.",
         "COBS 4.2.1R | COBS 4"),
        (r"\bunauthorised\b.*payment",
         "For unauthorised payments, payer liability is capped (typically £35 unless fraud/gross negligence) and the PSP must refund promptly, subject to exceptions.",
         "PSR 2017 reg.77-80"),
    ]
    for pat, body, src in rules:
        if re.search(pat, prompt, re.I):
            return f"{body}\n\nSource: {src}"
    return ""


@app.get("/")
def root():
    return "✅ FinLaw GPT backend is running."


@app.post("/api/upload")
def upload_file():
    f = request.files.get("file")
    if not f or f.filename == "":
        return jsonify({"error": "No file."}), 400
    if not allowed_file(f.filename):
        return jsonify({
            "error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTS))}."
        }), 400

    session_id = (request.form.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "Missing session_id."}), 400

    fname = secure_filename(f.filename)
    path = os.path.join(UPLOAD_FOLDER, fname)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f.save(path)

    ext = fname.rsplit(".", 1)[1].lower()
    try:
        if ext in ("txt", "md"):
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        elif ext == "pdf":
            import fitz  # PyMuPDF
            with fitz.open(path) as doc:
                text = "\n".join(page.get_text() for page in doc)
        elif ext == "docx":
            import docx
            doc = docx.Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            return jsonify({"error": f"Unsupported file type: .{ext}"}), 400
    except Exception as e:
        app.logger.warning("Extraction error for %s: %s", fname, e)
        return jsonify({"error": f"Could not extract text: {e}"}), 400

    text = clean_context(text)
    if not text.strip():
        return jsonify({"error": "No extractable text found."}), 400

    chunks = _chunk_text(text)
    indexed = session_index.add(session_id, fname, chunks)
    app.logger.info(
        "upload: file=%s session=%r chunks=%d chars=%d",
        fname, session_id[:16], indexed, len(text),
    )
    return jsonify({
        "filename": fname,
        "chunks": indexed,
        "message": "File uploaded.",
    })


@app.post("/api/chat/stream")
def chat_stream():
    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    fname = (data.get("filename") or "").strip()
    mode = (data.get("mode") or "auto").lower()
    # `model` is accepted for backwards compatibility with old frontend builds
    # but ignored — multi-model is dropped, Mistral hardcoded via OLLAMA_MODEL.
    _ = data.get("model")

    session_id = (data.get("session_id") or "").strip()
    has_session_files = bool(session_id) and session_index.has_session(session_id)

    if not prompt and not has_session_files:
        return jsonify({"error": "No prompt or file context."}), 400

    ctx = ""
    intent = classify_intent(prompt) if (mode == "auto" and not fname) else "legal_query"
    smalltalk = intent in ("empty", "frustration", "meta", "greeting")
    app.logger.info(
        "chat_stream: prompt=%r mode=%r intent=%s session=%r",
        prompt[:60], mode, intent, session_id[:16],
    )

    # Default generation options; chitchat path overrides for variety.
    gen_options: Optional[Dict[str, object]] = None

    # Populated by the retrieval branch below; the smalltalk path leaves it
    # empty. Forwarded to `verify_answer` so it can fail a citation that
    # isn't in any retrieved chunk.
    retrieved_chunk_cites: set = set()

    if smalltalk:
        gboost = {}
        use_finance = False
        use_traffic = False
        if intent == "frustration":
            system_msg = FRUSTRATION_PROMPT
        elif intent == "empty":
            system_msg = EMPTY_PROMPT
        elif intent == "meta":
            system_msg = META_PROMPT
        else:  # greeting
            system_msg = SMALLTALK_PROMPT
            if session_id:
                st = _SESSION_STATE.setdefault(session_id, {})
                first_turn = not st.get("greeted", False)
                st["greeted"] = True
                if first_turn:
                    system_msg = system_msg + (
                        "\nThis is the user's first message — end with one short clause "
                        "offering to help with UK finance regulation when they're ready."
                    )
        hint_line = ""
        gen_options = {"temperature": 0.7, "top_p": 0.9}
    else:
        query_hint = prompt if len(prompt) < 120 else prompt[:120]
        gboost = get_graph_boost(query_hint)
        if gboost.get("context_md"):
            ctx = gboost["context_md"] + (ctx or "")
        retrieved, retrieved_chunk_cites = get_context_and_cites(
            query_hint, session_id=session_id
        )
        if retrieved:
            ctx = f"{retrieved}\n" + (ctx or "")

        # Latent-bug fix: classify intent from the prompt alone, NOT prompt+ctx.
        # The retrieved corpus is entirely UK finance regulation, so concatenating
        # it would force FINANCE_QA_PROMPT for any prompt that triggered retrieval
        # (memory: finlaw-intent-router-latent-bug, 2026-05-23).
        use_finance = (mode in ("finance", "traffic-light")) or (mode == "auto" and is_finance_intent(prompt))
        use_traffic = (mode == "traffic-light") or (mode == "auto" and is_traffic_light_intent(prompt))

        system_msg = (
            TRAFFIC_LIGHT_PROMPT if (use_finance and use_traffic)
            else FINANCE_QA_PROMPT if use_finance
            else GENERAL_PROMPT
        )

        hint_bits = []
        must_terms = ", ".join(gboost.get("must_terms") or [])
        if must_terms:
            hint_bits.append(f"Use these terms where relevant: {must_terms}.")
        if gboost.get("source_line") and not use_traffic:
            hint_bits.append(f"If relevant, cite: {gboost['source_line']}.")
        hint_line = ((" ".join(hint_bits)) + "\n\n") if hint_bits else ""

        # Deterministic sampling for the legal_query path so eval runs are
        # reproducible and the model doesn't randomly drift between context-
        # grounded and hallucinated phrasings.
        gen_options = {"temperature": 0.0, "top_p": 0.9}

        # Task 4: weak-retrieval refusal — if the top dense cosine similarity
        # is below RAG_REFUSAL_THRESHOLD, skip Mistral and stream the canonical
        # refusal. Only fires on the finance/legal path; chit-chat is unaffected.
        if use_finance:
            from backend.retrieval.orchestrator import top_dense_similarity
            refusal_threshold = float(os.getenv("RAG_REFUSAL_THRESHOLD", "0.25"))
            if top_dense_similarity(query_hint) < refusal_threshold:
                def _refuse_stream():
                    yield "data:I do not have authoritative source material for this question.\n\n"
                    yield 'event: meta\ndata:{"citations_ok":true,"invalid":[],"verification":{"note":"refused_low_similarity"},"claim_trace":[]}\n\n'
                    yield "event: done\ndata:\n\n"
                resp = Response(_refuse_stream(), content_type="text/event-stream")
                resp.headers["Cache-Control"] = "no-cache"
                resp.headers["X-Accel-Buffering"] = "no"
                resp.headers["Connection"] = "keep-alive"
                return resp

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": (hint_line + (ctx or "") + prompt).strip()},
    ]

    def event_stream():
        suppress = False
        think_started = None
        sent_meta_think = False
        buffer_out: List[str] = []

        try:
            try:
                llm.ensure_model_ready(None)
            except Exception as e:
                msg = f"❌ {e}"
                yield f"data:{msg}\n\n"
                yield "event: done\ndata:\n\n"
                return

            for token in llm.generate_stream(messages, model_id=None, options=gen_options):
                if "<think>" in token:
                    suppress = True
                    think_started = time.time()
                    pre, token = token.split("<think>", 1)
                    if pre:
                        buffer_out.append(pre)
                        yield f"data:{pre}\n\n"

                if suppress and "</think>" in token:
                    end = time.time()
                    ms = int((end - (think_started or end)) * 1000)
                    think_started = None
                    suppress = False
                    sent_meta_think = True
                    _, post = token.split("</think>", 1)
                    token = post
                    yield f'event: meta\ndata:{{"thought_ms":{ms}}}\n\n'

                if not suppress and token:
                    buffer_out.append(token)
                    yield f"data:{token}\n\n"

                time.sleep(0.002)

            full_text = "".join(buffer_out)
            full_text = scrub_known_bad(full_text)
            full_text = normalise_citations(full_text)
            full_text = fix_currency(full_text)

            if len(full_text.strip()) < 80 and not use_traffic and not smalltalk:
                fallback = bootstrap_answer(prompt)
                if fallback:
                    full_text = fallback
                    yield f"data:{fallback}\n\n"

            if use_traffic:
                coerced = coerce_to_traffic_light(full_text)
                if coerced != full_text:
                    add = coerced[len(full_text):]
                    if add:
                        yield f"data:{add}\n\n"
                    full_text = coerced
            elif not smalltalk:
                if not re.search(r"(?im)^source\s*:\s*", full_text) and gboost.get("source_line"):
                    add = f"\n\nSource: {gboost['source_line']}"
                    full_text += add
                    yield f"data:{add}\n\n"

            citations_ok = True
            invalid: List[str] = []
            if STRICT_CITATIONS:
                invalid = find_invalid_citations(full_text)
                citations_ok = len(invalid) == 0

            if STRICT_CITATIONS and CITATION_PATCH_ENABLED and not citations_ok:
                patched = patch_with_warning(full_text, invalid)
                if patched != full_text:
                    tail = patched[len(full_text):]
                    if tail:
                        yield f"data:{tail}\n\n"
                    full_text = patched

            # ---- Stage 4: graph-grounded verification + claim trace -----
            verification: Dict = {"smalltalk": True} if smalltalk else {}
            claim_trace_records: List[Dict] = []
            context_cites = [
                c.strip()
                for c in (gboost.get("source_line") or "").split("|")
                if c and c.strip()
            ]
            if GRAPH_VERIFY_ENABLED and not smalltalk:
                try:
                    verification = verify_answer(
                        full_text, context_cites, retrieved_chunk_cites
                    )
                except Exception as e:
                    app.logger.warning("verify_answer failed: %s", e)
                    verification = {"note": f"error: {e}", "all_grounded": True, "all_retrieved": True}

                if (
                    not verification.get("all_grounded", True)
                    and verification.get("unverified")
                    and verification.get("note") != "graph_unavailable"
                ):
                    bad = verification["unverified"][:3]
                    warn = (
                        "\n\n> ⚠️ The following citations could not be matched against the graph: "
                        + ", ".join(f"`{c}`" for c in bad)
                        + "."
                    )
                    yield f"data:{warn}\n\n"
                    full_text += warn

            if CLAIM_TRACE_ENABLED and verification.get("verified"):
                try:
                    claim_trace_records = trace_all(
                        full_text, verification.get("verified", [])
                    )[:CLAIM_TRACE_MAX_ITEMS]
                except Exception as e:
                    app.logger.warning("trace_all failed: %s", e)
                    claim_trace_records = []

            audit = {
                "citations_ok": citations_ok,
                "invalid": invalid[:10],
                "verification": verification,
                "claim_trace": claim_trace_records,
            }
            yield f"event: meta\ndata:{json.dumps(audit)}\n\n"

            if not sent_meta_think:
                yield 'event: meta\ndata:{"thought_ms":300}\n\n'
            yield "event: done\ndata:\n\n"

        except Exception as e:
            yield f"data:❌ {str(e)}\n\n"
            yield "event: done\ndata:\n\n"

    resp = Response(event_stream(), content_type="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp


@app.post("/api/eval/stream")
def eval_stream():
    """Run the RAGAS evaluation and stream progress over SSE.

    Request body (JSON):
        sample : int   (default 5)        — first N questions; 0 / null = full 80
        mode   : str   (default 'ragas')  — 'ragas' | 'lexical' | 'both'
        judge  : str   (default 'ollama') — 'ollama' | 'hf'

    Events:
        start, loaded, phase, question, question_error, ragas_error, done.
    """
    data = request.get_json(force=True, silent=True) or {}
    sample_raw = data.get("sample")
    sample = int(sample_raw) if sample_raw not in (None, "", 0, "0") else None
    mode = (data.get("mode") or "ragas").lower()
    judge = (data.get("judge") or "ollama").lower()

    def event_stream():
        try:
            from backend.evaluation.runner import run_streaming
            for ev in run_streaming(mode=mode, sample=sample, judge=judge):
                name = ev.get("event") or "message"
                payload = json.dumps(ev.get("data") or {}, default=str)
                yield f"event: {name}\ndata: {payload}\n\n"
        except Exception as e:
            app.logger.exception("eval_stream failed")
            yield f"event: fatal\ndata: {json.dumps({'error': str(e)})}\n\n"
        yield "event: end\ndata: {}\n\n"

    resp = Response(event_stream(), content_type="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp


@app.get("/api/eval/results")
def eval_results_list():
    """List existing eval result CSVs with their timestamps."""
    out_dir = Path(os.getenv("EVAL_OUTPUT_DIR", "./data/eval_results"))
    if not out_dir.exists():
        return jsonify({"results": []})
    files = []
    for p in sorted(out_dir.glob("eval_results_*.csv"), reverse=True):
        if p.name.endswith("_summary.csv"):
            continue
        summary_p = p.with_name(p.stem + "_summary.csv")
        files.append({
            "name": p.name,
            "size": p.stat().st_size,
            "mtime": p.stat().st_mtime,
            "summary": summary_p.name if summary_p.exists() else None,
        })
    return jsonify({"results": files[:30]})


@app.get("/api/eval/results/<path:name>")
def eval_results_get(name: str):
    """Stream a specific eval CSV back as JSON rows."""
    safe = secure_filename(name)
    out_dir = Path(os.getenv("EVAL_OUTPUT_DIR", "./data/eval_results"))
    target = out_dir / safe
    if not target.exists() or not target.is_file():
        return jsonify({"error": "not found"}), 404
    try:
        import pandas as pd
        df = pd.read_csv(target)
        return jsonify({"name": safe, "rows": df.to_dict(orient="records")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(">>> FinLaw GPT backend starting …")
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        use_reloader=False,
        threaded=True,
    )
