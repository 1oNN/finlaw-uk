# backend/run_eval_and_charts.py
# Evaluation runner with relaxed scoring, robust citation detection,
# Excel/CSV support, timestamped output folders, and logs.

import os, re, sys, json, time, argparse, logging, shutil
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from collections import Counter

import pandas as pd
import requests

# ------------------------------------------------------------------------------
# Output folders (unique per run)
# ------------------------------------------------------------------------------
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTROOT = Path("backend/results_full")
OUTDIR = OUTROOT / f"run_{RUN_TS}"
OUTDIR.mkdir(parents=True, exist_ok=True)
(OUTROOT / "latest.txt").write_text(str(OUTDIR), encoding="utf-8")

LOGFILE = OUTDIR / "eval_run.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOGFILE, encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("finlaw-eval")

# ------------------------------------------------------------------------------
# Backend endpoint
# ------------------------------------------------------------------------------
BACKEND_URL = os.environ.get("FINLAW_BACKEND", "http://127.0.0.1:5000/api/chat/stream")

# ------------------------------------------------------------------------------
# Text helpers (lenient normalisation)
# ------------------------------------------------------------------------------
STOP = set("""
a an and are as at be by for from has have if in into is it its of on or that the their there these this to was were will with within without over under may must shall should could would can
""".split())

def norm_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w£]", " ", s)  # keep words and £
    return re.sub(r"\s+", " ", s).strip()

def lemma(tok: str) -> str:
    if tok.endswith("ies") and len(tok) > 4: return tok[:-3] + "y"
    if tok.endswith("s") and len(tok) > 3 and not tok.endswith("ss"): return tok[:-1]
    if tok.endswith("ing") and len(tok) > 5: return tok[:-3]
    if tok.endswith("ed") and len(tok) > 4: return tok[:-2]
    return tok

def toks(s: str):
    s = norm_text(s)
    out = []
    for t in s.split():
        if t in STOP: continue
        out.append(lemma(t))
    return out

def jaccard(a: set, b: set) -> float:
    if not a or not b: return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def seq_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

# ------------------------------------------------------------------------------
# Terminology & synonyms
# ------------------------------------------------------------------------------
TERMS = {
    "regulated activity","authorised","authorization","authorisation","exempt","appointed representative",
    "financial promotion","fair clear not misleading","due diligence","customer due diligence","cdd","edd",
    "inside information","insider list","market abuse","consumer duty","good outcomes","fair value",
    "operational resilience","impact tolerance","important business services",
    "complaints","fos","ombudsman","fscs","deposit protection",
    "mlr","psr","rao","fsma","cobs","sysc","prin","conc","icobs","mcob","prod","disp","comp","dtr","uk mar",
}
SYN = {
    "due diligence": {"due diligence","cdd","customer due diligence"},
    "enhanced due diligence": {"enhanced due diligence","edd"},
    "consumer duty": {"consumer duty","good outcomes","fair value"},
    "inside information": {"inside information","mar","uk mar"},
    "complaint": {"complaint","complaints","fos","ombudsman"},
    "financial promotion": {"financial promotion","fair clear not misleading","cobs 4"},
    "regulated activity": {"regulated activity","fsma","rao"},
}

def expand_keywords(raw: str, gold_text: str):
    base = set()
    for k in str(raw or "").split("|"):
        k = k.strip().lower()
        if not k: continue
        base.add(k)
        if k in SYN: base |= SYN[k]
    # mine salient tokens from gold
    gtoks = [t for t in toks(gold_text) if t not in STOP]
    freq = [w for w,_ in Counter(gtoks).most_common(12)]
    base |= set(freq)
    base = {w for w in base if len(w) >= 3 and not w.isdigit()}
    return sorted(base)

def keyword_presence(answer: str, keywords: set):
    atoks = set(toks(answer))
    found = 0
    for k in keywords:
        ks = {lemma(t) for t in norm_text(k).split()}
        if ks.issubset(atoks):
            found += 1
        else:
            # fuzzy: partial hit for multi-word phrases
            if len(ks) > 1 and (ks & atoks):
                found += 0.5
    return found

def terminology_score(answer: str) -> float:
    atoks = " " + norm_text(answer) + " "
    hits = 0
    for term in TERMS:
        tk = " " + term + " "
        if term in {"mlr","psr","rao","fsma","cobs","sysc","prin","conc","icobs","mcob","prod","disp","comp","dtr","uk mar"}:
            if re.search(rf"\b{re.escape(term)}\b", atoks): hits += 1
        else:
            if term in atoks: hits += 1
    return min(1.0, hits / 8.0)  # diminishing returns

def legal_completeness_score(answer: str, gold: str, expected_keywords: str) -> float:
    keys = set(expand_keywords(expected_keywords, gold))
    if not keys:
        gtoks = [t for t in toks(gold) if len(t) >= 3]
        keys = set([w for w,_ in Counter(gtoks).most_common(10)])
    if not keys: return 0.0
    found = keyword_presence(answer, keys)
    rec = min(1.0, found / max(1, len(keys)))
    return rec

def keyword_f1(answer: str, expected_keywords: str, gold: str) -> float:
    keys = set(expand_keywords(expected_keywords, gold))
    if not keys: return 0.0
    found = keyword_presence(answer, keys)
    tp = found
    fp = max(0.0, len(toks(answer)) * 0.02 - tp * 0.1)  # soft verbosity penalty
    fn = max(0.0, len(keys) - tp)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

def semantic_similarity_score(answer: str, gold: str) -> float:
    a = " ".join(toks(answer))
    g = " ".join(toks(gold))
    if not a or not g: return 0.0
    j = jaccard(set(a.split()), set(g.split()))
    r = seq_ratio(a, g)
    # tiny boost if gold literally appears inside answer
    if g and g in a and r < 0.6:
        r = 0.6
    return max(j, r)

# ------------------------------------------------------------------------------
# Robust citation extraction & scoring
# ------------------------------------------------------------------------------
SOURCE_RE = re.compile(r"(?im)^\s*[*_]*\s*source\s*[:\-–]\s*(.+?)\s*$")
SPLIT_RE  = re.compile(r"\s*[|;,/]\s*")
CITE_NORM_MAP = {
    "principles 12": "PRIN 12",
    "principle 12": "PRIN 12",
    "principe 12": "PRIN 12",
    "mar": "UK MAR",
    "ukmar": "UK MAR",
    "mlr 27": "MLR 2017 reg.27",
    "psr 77": "PSR 2017 reg.77",
    "mlr27": "MLR 2017 reg.27",
    "psr77": "PSR 2017 reg.77",
}
ALLOW_PATTERNS = [
    r"FSMA\s*2000\s*s\.?\s*\d+[A-Za-z]?",
    r"COBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"SYSC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"PRIN\s*\d+(?:\.\d+)*",
    r"CONC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"ICOBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"MCOB\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"PROD\s*\d+(?:\.\d+)*",
    r"DISP\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"COMP\s*\d+(?:\.\d+)*",
    r"COLL\s*\d+(?:\.\d+)*",
    r"UK\s*MAR(?:\s*art\.?\s*\d+[A-Za-z]?)?",
    r"MLR\s*2017\s*reg\.?\s*\d+[A-Za-z]?",
    r"PSR\s*2017\s*reg\.?\s*\d+[A-Za-z]?",
    r"RAO\s*2001\s*art\.?\s*\d+[A-Za-z]?",
    r"DTR\s*\d+(?:\.\d+)*",
]
ALLOW_RE = re.compile("|".join(f"(?:{p})" for p in ALLOW_PATTERNS), re.I)

def _normalise_token(tok: str) -> str:
    t = tok.strip()
    t = re.sub(r"\s+", " ", t)
    low = t.lower()
    if low in CITE_NORM_MAP:
        return CITE_NORM_MAP[low]
    if re.fullmatch(r"mlr\s*reg\.?\s*27", low):
        return "MLR 2017 reg.27"
    if re.fullmatch(r"psr\s*reg\.?\s*77", low):
        return "PSR 2017 reg.77"
    if low.startswith("mar "):
        return "UK MAR " + t.split(" ",1)[1]
    if low == "mar":
        return "UK MAR"
    return t

def extract_source_line(answer: str) -> str:
    if not answer: return ""
    m = SOURCE_RE.search(answer)
    if m: return m.group(1).strip()
    m = re.search(r"(?im)^\s*[*_]*source[*_]*\s*[:\-–]\s*(.+)$", answer)
    if m: return m.group(1).strip()
    tokens = ALLOW_RE.findall(answer or "")
    if tokens:
        uniq = []
        seen = set()
        for t in tokens:
            nt = _normalise_token(t if isinstance(t, str) else " ".join(t))
            if nt.lower() not in seen:
                uniq.append(nt); seen.add(nt.lower())
        return " | ".join(uniq[:4])
    return ""

def score_citations(answer: str, citations_ok_meta, debug: dict):
    src = extract_source_line(answer)
    debug["source_line_detected"] = src or "(none)"
    if citations_ok_meta is True:
        acc = 1.0
    else:
        any_tok = bool(ALLOW_RE.search(answer or ""))
        acc = 0.85 if any_tok else 0.0

    quality = 0.0
    if src:
        parts = [p for p in SPLIT_RE.split(src) if p.strip()]
        normalised = [_normalise_token(p) for p in parts]
        valid = [p for p in normalised if ALLOW_RE.search(p)]
        if valid:
            quality = min(1.0, 0.6 + 0.1 * (len(valid) - 1))
        debug["citations_valid"] = valid
        debug["citations_all"] = normalised
    else:
        any_tok = ALLOW_RE.findall(answer or "")
        if any_tok:
            quality = 0.6
            debug["citations_valid"] = list({str(_normalise_token(t if isinstance(t,str) else ' '.join(t))) for t in any_tok})
    return acc, quality, src

# ------------------------------------------------------------------------------
# Reading CSV/XLSX with flexible headers
# ------------------------------------------------------------------------------
def _read_table(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1")
    elif ext in (".xlsx", ".xls"):
        # read first sheet
        try:
            return pd.read_excel(path, engine="openpyxl")
        except Exception:
            return pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {path}")

def read_any(path: Path) -> pd.DataFrame:
    log.info(f"Loading {path.name}")
    df = _read_table(path)
    df.columns = (
        df.columns
        .astype(str)
        .str.strip().str.lower()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace("-", "_")
    )
    def pick_alias(cols, aliases):
        for a in aliases:
            if a in cols: return a
        return None
    q_aliases = ["question","question_text","prompt","prompt_text","task","task_text","query","query_text","scenario","scenario_text","case","case_like","instruction","instructions","title","summary","description","body","content","doc_task","document_task","document_tasks"]
    qcol = pick_alias(df.columns, q_aliases)
    if not qcol:
        candidates = {}
        for c in df.columns:
            try:
                med = df[c].astype(str).str.len().median()
                if med >= 10: candidates[c]=med
            except Exception: pass
        if candidates:
            qcol = max(candidates, key=candidates.get)
        else:
            qcol="__composed__"; df[qcol]=df.astype(str).agg(" | ".join, axis=1)

    gcol = pick_alias(df.columns, ["gold_answer","reference","reference_answer","ideal_answer","target","expected","expected_output","answer_ref","label_text","solution","explanation"])
    dcol = pick_alias(df.columns, ["domain","legal_domain","finance_domain","area","topic"])
    ccol = pick_alias(df.columns, ["complexity","level","difficulty","grade"])
    kcol = pick_alias(df.columns, ["expected_keywords","keywords","key_terms"])
    ecol = pick_alias(df.columns, ["expected_citations","citations","sources"])
    comp = pick_alias(df.columns, ["compliance_class","risk_class","class","risk_level","compliance_status","label","category"])

    ren = {}
    if qcol: ren[qcol]="question"
    if gcol: ren[gcol]="gold_answer"
    if dcol: ren[dcol]="domain"
    if ccol: ren[ccol]="complexity"
    if kcol: ren[kcol]="expected_keywords"
    if ecol: ren[ecol]="expected_citations"
    if comp: ren[comp]="compliance_class"
    df = df.rename(columns=ren)

    for col, default in {
        "gold_answer": "", "domain":"unspecified", "complexity":"intermediate",
        "expected_keywords":"", "expected_citations":"", "compliance_class":""
    }.items():
        if col not in df.columns: df[col]=default

    df["domain"] = df["domain"].astype(str).str.strip().str.replace("_"," ")
    df["complexity"] = (df["complexity"].astype(str).str.strip().str.lower()
                        .replace({"adv":"advanced","hard":"advanced","mid":"intermediate","easy":"basic"}))
    df["compliance_class"] = (df["compliance_class"].astype(str).str.strip()
                              .replace({"potential issue":"Potential issue","potential_issue":"Potential issue","noncompliant":"Non-compliant","non_compliant":"Non-compliant","compliant":"Compliant"}))
    df["source_file"]=path.name
    log.info(f"Loaded {len(df)} rows from {path.name}")
    return df

def discover_files() -> list[Path]:
    root = Path("backend")
    names = ["questions_80_balanced", "scenarios_case_like", "documents_tasks"]
    found = []
    for base in names:
        for ext in (".csv",".xlsx",".xls"):
            p = root / f"{base}{ext}"
            if p.exists():
                found.append(p)
                break
    return found

# ------------------------------------------------------------------------------
# Backend call
# ------------------------------------------------------------------------------
def stream_call(prompt: str, model: str|None, filename: str|None, retries:int=2, backoff:float=1.5):
    payload = {"prompt": prompt, "mode": "finance", "model": model or "", "filename": filename or ""}
    attempt = 0
    while True:
        attempt += 1
        t0 = time.time()
        thought_ms=None; citations_ok=None; invalid=[]; answer=[]
        try:
            with requests.post(BACKEND_URL, json=payload, stream=True, timeout=360) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line: continue
                    if line.startswith("data:"):
                        data = line[5:]
                        if data.startswith("{") and '"citations_ok"' in data:
                            try:
                                meta=json.loads(data); citations_ok=bool(meta.get("citations_ok")); invalid=meta.get("invalid") or []
                            except Exception: pass
                        elif data.startswith("{") and '"thought_ms"' in data:
                            try:
                                meta=json.loads(data); thought_ms=meta.get("thought_ms")
                            except Exception: pass
                        else:
                            answer.append(data)
            latency_ms=int((time.time()-t0)*1000)
            return "".join(answer).strip(),latency_ms,thought_ms,citations_ok,invalid,""
        except Exception as e:
            err=f"{type(e).__name__}: {e}"
            log.warning(f"Call failed (attempt {attempt}): {err}")
            if attempt<=retries:
                time.sleep(backoff**(attempt-1)); continue
            return "", int((time.time()-t0)*1000), None, None, [], err

# ------------------------------------------------------------------------------
# RAGAS (optional)
# ------------------------------------------------------------------------------
def try_import_ragas():
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        return evaluate, [faithfulness, answer_relevancy, context_precision, context_recall]
    except Exception:
        return None, None

def compute_ragas_block(rows: list[dict]):
    evaluate, metrics = try_import_ragas()
    if evaluate is None:
        log.info("RAGAS not available — skipping RAGAS metrics.")
        return [{} for _ in rows]
    ds = {
        "question": [r["question"] for r in rows],
        "answer": [r.get("answer","") for r in rows],
        "contexts": [r.get("contexts", []) for r in rows],
        "ground_truth": [r.get("gold_answer","") for r in rows],
    }
    try:
        result = evaluate(ds, metrics=metrics)
        scores = result.to_pandas()
        out=[]
        for _, s in scores.iterrows():
            out.append({
                "ragas_faithfulness": float(s.get("faithfulness", float("nan"))),
                "ragas_answer_relevancy": float(s.get("answer_relevancy", float("nan"))),
                "ragas_context_precision": float(s.get("context_precision", float("nan"))),
                "ragas_context_recall": float(s.get("context_recall", float("nan"))),
            })
        log.info("RAGAS metrics computed.")
        return out
    except Exception as e:
        log.warning(f"RAGAS failed: {e}")
        return [{} for _ in rows]

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Evaluate CSV/XLSX datasets with relaxed metrics + logs + charts.")
    ap.add_argument("--sample", type=int, default=0, help="sample size per file (0 = all)")
    ap.add_argument("--model", type=str, default="", help="optional backend model id")
    args = ap.parse_args()

    start_ts=time.time()
    log.info("=== FinLaw evaluation (relaxed) started ===")
    log.info(f"Backend: {BACKEND_URL}")
    log.info(f"Run folder: {OUTDIR}")

    files = discover_files()
    if not files:
        log.error("No input datasets found next to backend/. Expected {questions_80_balanced, scenarios_case_like, documents_tasks} as .csv or .xlsx")
        raise SystemExit(2)
    log.info(f"Datasets: {', '.join(p.name for p in files)}")

    frames=[]
    for p in files:
        df=read_any(p)
        if args.sample and args.sample>0:
            df=df.sample(min(args.sample,len(df)), random_state=42).reset_index(drop=True)
            log.info(f"Sampling {len(df)} rows from {p.name}")
        frames.append(df)
    data=pd.concat(frames, ignore_index=True)
    log.info(f"Total items to evaluate: {len(data)}")

    rows=[]
    for idx, r in data.iterrows():
        q = str(r["question"]).strip()
        prompt = (
            "You are a senior UK finance-law assistant.\n"
            "Answer clearly and factually in **6–10 sentences** using precise terms (e.g., regulated activity, Consumer Duty, due diligence, inside information, PRIN 12, SYSC 10, COBS 4, MLR 2017 reg.27).\n"
            "Include thresholds/time limits where relevant (e.g., £85,000; £35; 14/30 days). "
            "End with EXACTLY one line starting with 'Source: ' followed by short-form UK citations (e.g., 'FSMA 2000 s.19 | RAO 2001 art.25 | COBS 4'). No URLs.\n\n"
            + q
        )
        if (idx+1)%10==0 or idx==0:
            log.info(f"[{idx+1}/{len(data)}] Evaluating …")

        ans, latency_ms, thought_ms, citations_ok, invalid, error = stream_call(prompt, args.model or None, None)

        debug = {}
        source_accuracy, citation_quality, source_line = score_citations(ans, citations_ok, debug)

        gold = str(r.get("gold_answer",""))
        expk = str(r.get("expected_keywords",""))

        sem_sim = semantic_similarity_score(ans, gold)
        completeness = legal_completeness_score(ans, gold, expk)
        kw_f1 = keyword_f1(ans, expk, gold)
        term_score = terminology_score(ans)

        row = {
            "id": f"{r.get('source_file','?')}-{idx+1}",
            "source_file": r.get("source_file",""),
            "domain": r.get("domain","unspecified"),
            "complexity": r.get("complexity","intermediate"),
            "compliance_class": r.get("compliance_class",""),
            "question": q,
            "gold_answer": gold,
            "expected_keywords": expk,
            "expected_citations": r.get("expected_citations",""),
            "answer": ans,
            "source_line": source_line,
            "latency_ms": latency_ms,
            "thought_ms": thought_ms if thought_ms is not None else "",
            "citations_ok": citations_ok,
            "invalid_citations": " | ".join(invalid) if invalid else "",
            "citation_debug_found": " | ".join(debug.get("citations_valid", [])) if debug.get("citations_valid") else "",
            "citation_debug_all": " | ".join(debug.get("citations_all", [])) if debug.get("citations_all") else "",
            # relaxed metrics
            "source_accuracy": source_accuracy,
            "legal_completeness": completeness,
            "semantic_similarity": sem_sim,
            "keyword_f1_score": kw_f1,
            "legal_terminology": term_score,
            "citation_quality": citation_quality,
            "error": error,
            "contexts": [],   # placeholder for RAGAS
        }
        rows.append(row)

    # Optional RAGAS
    extra = compute_ragas_block(rows)
    for r, e in zip(rows, extra): r.update(e)

    out_csv = OUTDIR/"eval_results_updated.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8")
    log.info(f"Wrote {out_csv}")

    # summary json (averages of relaxed & ragas metrics)
    df = pd.DataFrame(rows)
    avgs = {}
    for col in ["source_accuracy","legal_completeness","semantic_similarity","keyword_f1_score","legal_terminology","citation_quality",
                "ragas_faithfulness","ragas_answer_relevancy","ragas_context_precision","ragas_context_recall"]:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            avgs[col] = float(s.dropna().mean()) if s.notna().any() else None

    manifest = {
        "started_at": datetime.fromtimestamp(start_ts).isoformat(timespec="seconds"),
        "ended_at": datetime.now().isoformat(timespec="seconds"),
        "backend_url": BACKEND_URL,
        "files": [p.name for p in files],
        "run_folder": str(OUTDIR),
        "total_items": int(len(data)),
        "success_items": int((df["error"].astype(str)=="").sum()) if "error" in df else int(len(df)),
        "avg_latency_ms": int(pd.to_numeric(df["latency_ms"], errors="coerce").mean()) if "latency_ms" in df else None,
        "averages": avgs,
        "outputs": ["eval_results_updated.csv","overall_metrics.json",
                    "fig_by_compliance_class.png","fig_by_complexity.png",
                    "overall_performance.png","performance_by_domain.png",
                    "fig_compliance_distribution.png","fig_complexity_grouped.png","eval_run.log"],
    }
    with open(OUTDIR/"run_manifest.json","w",encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with open(OUTDIR/"overall_metrics.json","w",encoding="utf-8") as f:
        json.dump({k:v for k,v in avgs.items() if v is not None}, f, indent=2)
    log.info("Wrote manifest + overall_metrics.json")

    # ------------------------------------------------------------------------------
    # Build charts (calls your existing script); then copy PNGs into this run folder
    # ------------------------------------------------------------------------------
    log.info("Building charts …")
    rc = os.system("python backend/make_finance_charts.py")
    if rc != 0:
        log.warning("Chart build returned non-zero exit code (make_finance_charts.py).")
    # gather charts from default location if that script saved to OUTROOT
    generated = [
        "overall_performance.png",
        "fig_by_complexity.png",
        "performance_by_domain.png",
        "fig_by_compliance_class.png",
        "fig_compliance_distribution.png",
        "fig_complexity_grouped.png",
    ]
    for name in generated:
        src = OUTROOT / name
        if src.exists():
            shutil.copy2(src, OUTDIR / name)
    log.info("Charts (if generated) copied into the run folder.")

    log.info("=== FinLaw evaluation (relaxed) completed ===")
    log.info(f"Results: {OUTDIR}")

if __name__ == "__main__":
    main()
