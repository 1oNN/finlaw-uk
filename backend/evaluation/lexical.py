"""Legacy lexical evaluator (formerly `evaluate_finlaw.py`).

Kept verbatim from the MSc submission as the *reference baseline* for
the upgraded RAGAS pipeline. Hits the chat backend over HTTP and scores
each answer with Jaccard / ROUGE-L / optional BERTScore / citation
regex allowlist matching. The pre-upgrade dissertation reported these
metrics under the (now-corrected) label "RAGAS-style"; the actual
`ragas` library lives in `backend/evaluation/ragas_eval.py`.

This file is preserved as-is so the original numbers in
`backend/results_full/run_*/` remain reproducible. New work should use
`backend/evaluation/runner.py` (see `docs/RAGAS_RESULTS.md`).
"""
import argparse, json, re, sys, time
from pathlib import Path
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ===== optional metric deps (guarded) ========================================
try:
    from rouge import Rouge
    _ROUGE = Rouge()
except Exception:
    _ROUGE = None

try:
    from bert_score import score as bertscore
    _BERT = True
except Exception:
    _BERT = False

# ============== helpers: progress ============================================
def fmt_secs(s: float) -> str:
    m, s = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h:d}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"

def progress(i, n, start_ts, title, log_every=5):
    if (i % log_every) and i != n:
        return
    elapsed = time.time() - start_ts
    rate = i / max(elapsed, 1e-6)
    eta = (n - i) / max(rate, 1e-6)
    print(f"[{title}] {i}/{n}  elapsed={fmt_secs(elapsed)}  eta≈{fmt_secs(eta)}")

# ============== citation validation (regex) ==================================
CITE_PATTERNS = [
    r"(?:FSMA\s*2000\s*s\.?\s*\d+[A-Za-z]?)",
    r"(?:COBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?)",
    r"(?:SYSC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?)",
    r"(?:PRIN\s*\d+(?:\.\d+)*)",
    r"(?:CONC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?)",
    r"(?:ICOBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?)",
    r"(?:MCOB\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?)",
    r"(?:PROD\s*\d+(?:\.\d+)*)",
    r"(?:DISP\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?)",
    r"(?:COMP\s*\d+(?:\.\d+)*)",
    r"(?:COLL\s*\d+(?:\.\d+)*)",
    r"(?:UK\s*MAR\s*art\.?\s*\d+[A-Za-z]?)",
    r"(?:MLR\s*2017\s*reg\.?\s*\d+[A-Za-z]?)",
    r"(?:PRA\s*Rulebook\s*CRR\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?)",
    r"(?:PSR\s*2017\s*reg\.?\s*\d+[A-Za-z]?)",
    r"(?:RAO\s*2001\s*art\.?\s*\d+[A-Za-z]?)",
    r"(?:RAO\s*2001\s*Sch\.?\s*\d+[A-Za-z]?)",
    r"(?:DTR\s*\d+(?:\.\d+)*)",
]
CITE_COMPILED = [re.compile(p, re.I) for p in CITE_PATTERNS]
BAD_TOKENS = [r"\[[0-9]+(?:†)?\]", r"https?://\S+", r"\bFCAS\b", r"\bFPM\b", r"\bPFB\b", r"\bSMDR\b"]
BAD_COMPILED = [re.compile(p, re.I) for p in BAD_TOKENS]

def matches_allowlist(s: str) -> bool:
    return any(p.search(s) for p in CITE_COMPILED)
def has_bad_token(s: str) -> bool:
    return any(p.search(s) for p in BAD_COMPILED)
def extract_citation_snippets(text: str):
    return [p.strip() for p in re.split(r"[;\|\n,•\-–—]+", text) if p.strip()]
def find_invalid_citations(text: str):
    invalid = []
    for sn in extract_citation_snippets(text):
        if re.search(r"(FSMA|COBS|SYSC|PRIN|CONC|ICOBS|MCOB|PROD|DISP|COMP|COLL|UK\s*MAR|MLR|PRA\s*Rulebook|PSR|RAO|DTR)", sn, re.I):
            if has_bad_token(sn) or not matches_allowlist(sn):
                invalid.append(sn)
    uniq, seen = [], set()
    for it in invalid:
        if it not in seen:
            uniq.append(it); seen.add(it)
    return uniq

def has_source_line(ans:str)->bool:
    return bool(re.search(r"^Source:\s", ans.strip(), flags=re.M))

def policy_penalty(ans:str)->float:
    p = 0.0
    if not has_source_line(ans): p += 0.5
    if "http://" in ans or "https://" in ans: p += 0.5
    return min(1.0, p)

# ============== light NLP + robust keywords =================================
_STEM_RE = re.compile(r"(ing|ed|es|s)$", re.I)
def norm_tok(t):
    t = t.lower().strip()
    t = re.sub(r"[^a-z0-9£]", "", t)
    return _STEM_RE.sub("", t)

def tokenize(s): 
    return [norm_tok(x) for x in re.findall(r"[a-z0-9£]+", s.lower())]

def jaccard(a, b):
    A, B = set(tokenize(a)), set(tokenize(b))
    if not A and not B: return 1.0
    if not A or not B:  return 0.0
    return len(A & B) / len(A | B)

def contains_phrase(tokens, phrase):
    ptoks = [norm_tok(x) for x in re.findall(r"[a-z0-9£]+", phrase.lower())]
    return all(p in tokens for p in ptoks)

SYN = {
  "impact tolerance": ["impact tolerances"],
  "consumer duty": ["duty", "prin 12"],
  "customer due diligence": ["cdd", "due diligence"],
  "enhanced due diligence": ["edd"],
  "strong customer authentication": ["sca"],
  "financial promotion": ["fair clear not misleading", "cobs 4"],
  "arranging deals": ["ra o 25","rao 25","art 25"],
  "advising on investments": ["rao 53","art 53"],
  "unauthorised payment": ["unauthorized payment"],
}

def keyword_f1(pred_text, exp_keywords_pipe):
    tokens = set(tokenize(pred_text))
    kws = [k.strip() for k in exp_keywords_pipe.split("|") if k.strip()]
    if not kws: 
        return 1.0,1.0,1.0
    hits = 0
    for k in kws:
        if contains_phrase(tokens, k):
            hits += 1; continue
        for alt in SYN.get(k.lower(), []):
            if contains_phrase(tokens, alt):
                hits += 1; break
    recall = hits/len(kws)
    precision = recall  # presence proxy
    f1 = 0.0 if precision+recall==0 else 2*precision*recall/(precision+recall)
    return precision, recall, f1

def rouge_l(hyp, ref):
    if _ROUGE is None:
        return None
    try:
        r = _ROUGE.get_scores(hyp, ref, avg=True)
        return r["rouge-l"]["f"]
    except Exception:
        return None

def bert_f1(hyp, ref, lang="en"):
    if not _BERT:
        return None
    try:
        P,R,F1 = bertscore([hyp],[ref], lang=lang, rescale_with_baseline=True)
        return float(F1[0])
    except Exception:
        return None

# ============== backend call (parse meta first) ==============================
def call_backend(url_base, question, mode="finance", model=None, timeout=120):
    url = f"{url_base.rstrip('/')}/api/chat/stream"
    payload = {"prompt": question, "mode": mode}
    if model:
        payload["model"] = model

    with requests.post(url, json=payload, stream=True, timeout=timeout) as r:
        r.raise_for_status()

        text_out = []
        citations_ok, invalid = None, []

        # Try SSE first
        for raw in r.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if raw.startswith("data:{"):
                try:
                    meta = json.loads(raw[5:])
                    if "citations_ok" in meta:
                        citations_ok = meta.get("citations_ok")
                        invalid = meta.get("invalid", []) or []
                except Exception:
                    pass
                continue
            if raw.startswith("data:"):
                text_out.append(raw[5:])
                continue

            # Fallbacks: plain JSON line or plain text
            try:
                obj = json.loads(raw)
                # common shapes: {"content": "..."} or {"message":{"content":"..."}}
                if "content" in obj and isinstance(obj["content"], str):
                    text_out.append(obj["content"])
                elif "message" in obj and isinstance(obj["message"], dict) and "content" in obj["message"]:
                    text_out.append(obj["message"]["content"])
            except Exception:
                # treat as raw text token
                text_out.append(raw)

        ans = "".join(text_out).strip()
        return ans, citations_ok, invalid


# ============== Q&A evaluation ==============================================
def evaluate_qa(questions_csv, url_base=None, model=None, out_dir="results", log_every=5, limit=None):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(questions_csv)
    if limit: df = df.head(int(limit))
    start_ts, total = time.time(), len(df)
    records = []

    for i, row in enumerate(df.itertuples(index=False), start=1):
        q, dom = row.question, row.domain
        gold, exp_kw = row.gold_answer, row.expected_keywords
        if url_base:
            ans, meta_ok, _ = call_backend(url_base, q, mode="finance", model=model)
        else:
            ans, meta_ok = gold + " (simulated)", True

        # --- metrics ---
        # semantic similarity (blend)
        sem_sim = jaccard(gold, ans)
        r_l = rouge_l(ans, gold)
        if r_l is not None:
            sem_sim = 0.7*r_l + 0.3*sem_sim
        b_f1 = bert_f1(ans, gold)
        if b_f1 is not None:
            sem_sim = 0.6*b_f1 + 0.3*(r_l or 0) + 0.1*sem_sim

        _, _, kw_f1 = keyword_f1(ans, exp_kw)

        invalid_local = find_invalid_citations(ans)
        pen = policy_penalty(ans)
        citation_quality = max(0.0, (1.0 - 0.1*len(invalid_local) - pen))
        source_accuracy = 1.0 if (meta_ok is True and not invalid_local and pen==0.0) else 0.0

        # completeness
        kws = [k for k in exp_kw.split("|") if k]
        tokens = set(tokenize(ans))
        present = 0
        for k in kws:
            if contains_phrase(tokens, k):
                present += 1
            else:
                for alt in SYN.get(k.lower(), []):
                    if contains_phrase(tokens, alt):
                        present += 1; break
        legal_completeness = present/len(kws) if kws else 1.0

        # terminology
        LEGAL_TERMS = [
            "regulated activity","authorised","exempt","financial promotion","suitability",
            "personal recommendation","conflicts of interest","operational resilience",
            "consumer duty","fair value","cooling off","cancellation","inside information",
            "insider list","customer due diligence","enhanced due diligence",
            "unauthorised payment","refund","strong customer authentication","complaint",
            "ombudsman","£85,000","impact tolerance","important business services",
            "appointed representative","arranging deals","advising on investments"
        ]
        lt_hits = 0
        for t in LEGAL_TERMS:
            if contains_phrase(tokens, t):
                lt_hits += 1
        legal_terminology = lt_hits / max(1, len(LEGAL_TERMS))

        records.append({
            "id": row.id, "domain": dom, "question": q,
            "gold_answer": gold, "model_answer": ans,
            "semantic_similarity": sem_sim,
            "keyword_f1_score": kw_f1,
            "legal_completeness": legal_completeness,
            "legal_terminology": legal_terminology,
            "citation_quality": citation_quality,
            "source_accuracy": source_accuracy,
        })
        progress(i, total, start_ts, title="Q&A", log_every=log_every)

    res_df = pd.DataFrame(records)
    (out/"eval_results.csv").parent.mkdir(parents=True, exist_ok=True)
    res_df.to_csv(out/"eval_results.csv", index=False)

    metrics = ["source_accuracy","legal_completeness","semantic_similarity","keyword_f1_score","legal_terminology","citation_quality"]
    overall = {m: float(res_df[m].mean()) for m in metrics}
    by_domain = res_df.groupby("domain")[metrics].mean().reset_index()
    (out/"overall_metrics.json").write_text(json.dumps(overall, indent=2))
    by_domain.to_csv(out/"by_domain.csv", index=False)

    # overall barh
    plt.figure(figsize=(9,5))
    y, x = list(overall.values()), list(overall.keys())
    plt.barh(x, y)
    for i,v in enumerate(y): plt.text(v+0.01, i, f"{v:.3f}")
    plt.xlabel("Score"); plt.title("Overall System Performance by Metrics"); plt.tight_layout()
    plt.savefig(out/"overall_performance.png", dpi=160); plt.close()

    # per-domain grouped bar
    plt.figure(figsize=(10,6))
    X = np.arange(len(by_domain["domain"])); width = 0.13
    for i, m in enumerate(metrics):
        plt.bar(X + i*width, by_domain[m].values, width, label=m.replace("_"," "))
    plt.xticks(X + width*2.5, by_domain["domain"], rotation=30, ha="right")
    plt.ylabel("Mean Score"); plt.title("Performance by Legal Domain"); plt.legend(); plt.tight_layout()
    plt.savefig(out/"performance_by_domain.png", dpi=160); plt.close()

    # citation audit (approx)
    invalid_counts = sum(len(find_invalid_citations(a)) for a in res_df["model_answer"])
    valid_est = len(res_df) - np.sign(invalid_counts)
    plt.figure(figsize=(5,5))
    plt.pie([valid_est, invalid_counts], labels=["Valid-ish","Invalid tokens"], autopct="%1.1f%%")
    plt.title("Citation Audit (approx.)"); plt.tight_layout()
    plt.savefig(out/"citation_audit.png", dpi=160); plt.close()

# ============== Document tasks ==============================================
def evaluate_docs(docs_csv, url_base=None, model=None, out_dir="results", log_every=5, limit=None):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(docs_csv)
    if limit: df = df.head(int(limit))
    start_ts, total = time.time(), len(df)
    recs = []
    for i, r in enumerate(df.itertuples(index=False), 1):
        prompt = (
            "You are LEGAL GPT. Read the excerpt and task, then answer in 3–5 bullets plus one 'Source:' line.\n"
            "Return the colour word (Green/Yellow/Amber/Red) once in the text.\n\n"
            f"Excerpt:\n{r.document_excerpt}\n\nTask:\n{r.task}\n"
        )
        if url_base:
            ans, meta_ok, _ = call_backend(url_base, prompt, mode="finance", model=model)
        else:
            ans, meta_ok = r.expected_issue + f" ({r.expected_risk})", True
        risk = r.expected_risk.strip().lower()
        risk_match = 1.0 if risk in ans.lower() else 0.0
        invalid_local = find_invalid_citations(ans)
        pen = policy_penalty(ans)
        citation_quality = max(0.0, (1.0 - 0.1*len(invalid_local) - pen))
        source_accuracy = 1.0 if (meta_ok is True and not invalid_local and pen==0.0) else 0.0
        recs.append({
            "id": r.id, "domain": r.domain, "risk_expected": r.expected_risk,
            "risk_found": "yes" if risk_match==1.0 else "no",
            "citation_quality": citation_quality, "source_accuracy": source_accuracy,
            "model_answer": ans
        })
        progress(i, total, start_ts, title="Docs", log_every=log_every)

    ddf = pd.DataFrame(recs)
    ddf.to_csv(out/"docs_results.csv", index=False)

    plt.figure(figsize=(6,4))
    ddf["risk_binary"] = (ddf["risk_found"]=="yes").astype(float)
    plt.bar(["Risk Match","Citation Quality","Source Accuracy"],
            [ddf["risk_binary"].mean(), ddf["citation_quality"].mean(), ddf["source_accuracy"].mean()])
    plt.title("Document Tasks – Summary Metrics"); plt.tight_layout()
    plt.savefig(out/"docs_summary.png", dpi=160); plt.close()

# ============== Case scenarios ==============================================
def evaluate_cases(cases_csv, url_base=None, model=None, out_dir="results", log_every=5, limit=None):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(cases_csv)
    if limit: df = df.head(int(limit))
    start_ts, total = time.time(), len(df)
    recs = []
    for i, r in enumerate(df.itertuples(index=False), 1):
        prompt = (
            "You are LEGAL GPT. Analyse the scenario in 4 bullets: (1) Issues, (2) Applicable rules, "
            "(3) Exceptions/conditions, (4) Conclusion. Add one 'Source:' line with short-form UK cites only.\n\n"
            f"Scenario:\n{r.scenario}\n"
        )
        if url_base:
            ans, meta_ok, _ = call_backend(url_base, prompt, mode="finance", model=model)
        else:
            ans, meta_ok = r.gold_rationale, True
        bullets = len(re.findall(r"^\s*[-•*]", ans, flags=re.M))
        structure = min(1.0, bullets/4.0)
        invalid_local = find_invalid_citations(ans)
        pen = policy_penalty(ans)
        citation_quality = max(0.0, (1.0 - 0.1*len(invalid_local) - pen))
        source_accuracy = 1.0 if (meta_ok is True and not invalid_local and pen==0.0) else 0.0
        recs.append({
            "id": r.id, "domain": r.domain, "structure_score": structure,
            "citation_quality": citation_quality, "source_accuracy": source_accuracy,
            "model_answer": ans
        })
        progress(i, total, start_ts, title="Cases", log_every=log_every)

    cdf = pd.DataFrame(recs)
    cdf.to_csv(out/"cases_results.csv", index=False)

    plt.figure(figsize=(6,4))
    plt.bar(["Structure","Citation Quality","Source Accuracy"],
            [cdf["structure_score"].mean(), cdf["citation_quality"].mean(), cdf["source_accuracy"].mean()])
    plt.title("Case Scenarios – Summary Metrics"); plt.tight_layout()
    plt.savefig(out/"cases_summary.png", dpi=160); plt.close()

# ============== CLI ==========================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="questions_120_complex.csv",
                    help="CSV for Q&A evaluation (default: questions_120_complex.csv)")
    ap.add_argument("--docs", default=None, help="Optional CSV of document tasks (e.g., documents_tasks.csv)")
    ap.add_argument("--cases", default=None, help="Optional CSV of case scenarios (e.g., scenarios_case_like.csv)")
    ap.add_argument("--backend", default=None, help="e.g., http://127.0.0.1:5000 (omit for simulated)")
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default="results")
    ap.add_argument("--log-every", type=int, default=5, help="Print progress every N items")
    ap.add_argument("--limit", type=int, default=None, help="Evaluate only the first N rows for each section")
    args = ap.parse_args()

    evaluate_qa(args.questions, url_base=args.backend, model=args.model,
                out_dir=args.out, log_every=args.log_every, limit=args.limit)
    if args.docs:
        evaluate_docs(args.docs, url_base=args.backend, model=args.model,
                      out_dir=args.out, log_every=args.log_every, limit=args.limit)
    if args.cases:
        evaluate_cases(args.cases, url_base=args.backend, model=args.model,
                       out_dir=args.out, log_every=args.log_every, limit=args.limit)

    print("Saved results to:", args.out)
