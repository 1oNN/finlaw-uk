import { useEffect, useRef, useState } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { FiPlay, FiSquare, FiFile, FiChevronDown, FiChevronRight } from "react-icons/fi";

const API_BASE = "http://localhost:5000";

const PHASE_LABEL = {
  pipeline: "Running RAG pipeline",
  lexical: "Computing lexical metrics",
  ragas_judge: "RAGAS judge (Mistral)",
};

function fmtScore(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const n = typeof v === "string" ? Number(v) : v;
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(3);
}

function MetricCard({ label, value, n }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-text">{fmtScore(value)}</div>
      {typeof n === "number" && (
        <div className="mt-1 text-xs text-muted">n={n}</div>
      )}
    </div>
  );
}

function PerQuestionRow({ row }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-border bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-panel"
      >
        <div className="pt-1 text-muted">
          {open ? <FiChevronDown /> : <FiChevronRight />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-panel px-2 py-0.5 text-xs text-muted">
              {row.qid}
            </span>
            <span className="text-xs text-muted">{row.domain}</span>
            <span className="text-xs text-muted">·</span>
            <span className="text-xs text-muted">{row.complexity}</span>
            <span className="ml-auto text-xs text-muted">{row.runtime_s}s</span>
          </div>
          <div className="mt-1 truncate text-sm text-text">{row.question}</div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <span className="text-muted">faith</span>
            <span className="font-mono">{fmtScore(row.ragas_faithfulness)}</span>
            <span className="text-muted">rel</span>
            <span className="font-mono">{fmtScore(row.ragas_answer_relevancy)}</span>
            <span className="text-muted">ctx_p</span>
            <span className="font-mono">{fmtScore(row.ragas_context_precision)}</span>
            <span className="text-muted">ctx_r</span>
            <span className="font-mono">{fmtScore(row.ragas_context_recall)}</span>
            {row.lex_citation_match !== undefined && row.lex_citation_match !== null && (
              <>
                <span className="text-muted">cite</span>
                <span className="font-mono">{fmtScore(row.lex_citation_match)}</span>
              </>
            )}
            {row.error && (
              <span className="text-risk-red">{row.error}</span>
            )}
          </div>
        </div>
      </button>
      {open && (
        <div className="space-y-3 border-t border-border p-4 text-sm">
          <div>
            <div className="mb-1 text-xs uppercase tracking-wider text-muted">Ground truth</div>
            <div className="whitespace-pre-wrap text-text">{row.ground_truth || "—"}</div>
          </div>
          <div>
            <div className="mb-1 text-xs uppercase tracking-wider text-muted">Model answer</div>
            <div className="whitespace-pre-wrap rounded-md bg-panel p-3 font-mono text-xs leading-5 text-text">
              {row.answer || "(empty)"}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function EvalPage() {
  const [sample, setSample] = useState("5");
  const [mode, setMode] = useState("ragas");
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState(null);
  const [progress, setProgress] = useState({ i: 0, total: 0 });
  const [feed, setFeed] = useState([]);
  const [perQuestion, setPerQuestion] = useState([]);
  const [summary, setSummary] = useState(null);
  const [csvPath, setCsvPath] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [pastRuns, setPastRuns] = useState([]);
  const abortRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/eval/results`)
      .then((r) => r.json())
      .then((d) => setPastRuns(d.results || []))
      .catch(() => {});
  }, [running]);

  function appendFeed(line) {
    setFeed((f) => [...f, line]);
  }

  async function startRun(e) {
    e.preventDefault();
    if (running) return;
    setRunning(true);
    setFeed([]);
    setPerQuestion([]);
    setSummary(null);
    setCsvPath(null);
    setErrorMsg("");
    setPhase("starting");
    setProgress({ i: 0, total: Number(sample) || 0 });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch(`${API_BASE}/api/eval/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample: sample === "all" ? 0 : Number(sample),
          mode,
        }),
        signal: controller.signal,
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop();
        for (const frame of frames) {
          let name = "message";
          let dataStr = "";
          for (const line of frame.split("\n")) {
            if (line.startsWith("event:")) name = line.slice(6).trim();
            else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
          }
          if (!dataStr) continue;
          let data;
          try {
            data = JSON.parse(dataStr);
          } catch (err) {
            continue;
          }
          if (name === "start") {
            appendFeed(`▶ start · mode=${data.mode} · sample=${data.sample ?? "all"}`);
          } else if (name === "loaded") {
            setProgress((p) => ({ ...p, total: data.total }));
            appendFeed(`✓ loaded ${data.total} questions`);
          } else if (name === "phase") {
            setPhase(data.phase);
            appendFeed(`— phase: ${PHASE_LABEL[data.phase] || data.phase}`);
          } else if (name === "question") {
            setProgress({ i: data.i, total: data.total });
            appendFeed(`[${data.i}/${data.total}] ${data.qid} · ${data.runtime_s}s`);
          } else if (name === "question_error") {
            appendFeed(`[${data.i}/${data.total}] ${data.qid} ERROR: ${data.error}`);
          } else if (name === "ragas_error") {
            appendFeed(`⚠ RAGAS judge failed: ${data.error}`);
            setErrorMsg(`RAGAS judge: ${data.error}`);
          } else if (name === "done") {
            setSummary(data.summary || null);
            setPerQuestion(data.per_question || []);
            setCsvPath(data.csv_path || null);
            setPhase("done");
            appendFeed(`✓ done · CSV at ${data.csv_path}`);
          } else if (name === "fatal") {
            setErrorMsg(data.error || "unknown fatal error");
            appendFeed(`✗ fatal: ${data.error}`);
          } else if (name === "end") {
            // stream end marker
          }
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        setErrorMsg(err.message || String(err));
        appendFeed(`✗ ${err.message || err}`);
      } else {
        appendFeed("⏹ stopped");
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  function stopRun() {
    if (abortRef.current) abortRef.current.abort();
  }

  async function loadPast(name) {
    try {
      const r = await fetch(`${API_BASE}/api/eval/results/${encodeURIComponent(name)}`);
      const d = await r.json();
      if (d.rows) {
        setPerQuestion(d.rows.map((row) => ({
          qid: row.qid,
          domain: row.domain,
          complexity: row.complexity,
          question: row.question,
          ground_truth: row.ground_truth,
          answer: row.answer,
          runtime_s: row.runtime_s,
          error: row.error,
          ragas_faithfulness: row.ragas_faithfulness,
          ragas_answer_relevancy: row.ragas_answer_relevancy,
          ragas_context_precision: row.ragas_context_precision,
          ragas_context_recall: row.ragas_context_recall,
          lex_citation_match: row.lex_citation_match,
        })));
        setCsvPath(name);
        setSummary(null);
      }
    } catch (e) {
      setErrorMsg(`load failed: ${e.message || e}`);
    }
  }

  const pct = progress.total > 0 ? Math.min(100, Math.round((progress.i / progress.total) * 100)) : 0;
  const mFaith = summary?.ragas_faithfulness_mean;
  const mRel = summary?.ragas_answer_relevancy_mean;
  const mCtxP = summary?.ragas_context_precision_mean;
  const mCtxR = summary?.ragas_context_recall_mean;

  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <Header />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold">RAGAS Evaluation</h1>
          <p className="mt-1 text-sm text-muted">
            Run the FinLaw-UK pipeline against the 80-question ground truth set and score
            faithfulness, answer relevancy, context precision, context recall.
          </p>
        </div>

        <form onSubmit={startRun} className="mb-6 flex flex-wrap items-end gap-4 rounded-xl border border-border bg-surface p-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Sample size</span>
            <select
              value={sample}
              onChange={(e) => setSample(e.target.value)}
              disabled={running}
              className="rounded-md border border-border bg-panel px-3 py-2 text-text"
            >
              <option value="5">5 (smoke, ~30s)</option>
              <option value="10">10 (~1-2 min)</option>
              <option value="20">20 (~3-5 min)</option>
              <option value="40">40 (~10-15 min)</option>
              <option value="all">All 80 (~30-90 min)</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Mode</span>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              disabled={running}
              className="rounded-md border border-border bg-panel px-3 py-2 text-text"
            >
              <option value="ragas">RAGAS only</option>
              <option value="lexical">Lexical only</option>
              <option value="both">Both (lexical + RAGAS)</option>
            </select>
          </label>
          <div className="flex gap-2">
            {!running ? (
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 font-medium text-white hover:bg-accent-hover"
              >
                <FiPlay /> Run evaluation
              </button>
            ) : (
              <button
                type="button"
                onClick={stopRun}
                className="inline-flex items-center gap-2 rounded-md bg-risk-red px-4 py-2 font-medium text-white"
              >
                <FiSquare /> Stop
              </button>
            )}
          </div>
        </form>

        {(running || phase) && (
          <div className="mb-6 rounded-xl border border-border bg-surface p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted">
                {phase === "done" ? "Done" : PHASE_LABEL[phase] || phase || "Starting"}
              </span>
              <span className="text-muted">
                {progress.i}/{progress.total} · {pct}%
              </span>
            </div>
            <div className="mt-2 h-2 w-full rounded-full bg-panel">
              <div
                className="h-2 rounded-full bg-accent transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <pre className="mt-3 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-md bg-panel p-3 text-xs leading-5 text-muted">
              {feed.join("\n")}
            </pre>
          </div>
        )}

        {errorMsg && (
          <div className="mb-6 rounded-xl border border-risk-red bg-surface p-4 text-sm text-risk-red">
            {errorMsg}
          </div>
        )}

        {summary && (
          <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard label="Faithfulness" value={mFaith} n={summary.ragas_faithfulness_n} />
            <MetricCard label="Answer Relevancy" value={mRel} n={summary.ragas_answer_relevancy_n} />
            <MetricCard label="Context Precision" value={mCtxP} n={summary.ragas_context_precision_n} />
            <MetricCard label="Context Recall" value={mCtxR} n={summary.ragas_context_recall_n} />
          </div>
        )}

        {summary && (
          <div className="mb-6 rounded-xl border border-border bg-surface p-4 text-sm">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div>
                <div className="text-xs uppercase tracking-wider text-muted">Questions</div>
                <div className="text-lg font-semibold">{summary.questions}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-muted">Errors</div>
                <div className="text-lg font-semibold">{summary.errors}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-muted">Total runtime</div>
                <div className="text-lg font-semibold">{summary.runtime_total_s}s</div>
              </div>
              {csvPath && (
                <div className="col-span-2 md:col-span-1">
                  <div className="text-xs uppercase tracking-wider text-muted">CSV</div>
                  <div className="truncate text-xs">{csvPath}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {perQuestion.length > 0 && (
          <div className="mb-8 space-y-2">
            <h2 className="text-lg font-semibold">Per-question results</h2>
            {perQuestion.map((row) => (
              <PerQuestionRow key={row.qid || row.question} row={row} />
            ))}
          </div>
        )}

        {pastRuns.length > 0 && (
          <div className="mb-8">
            <h2 className="mb-3 text-lg font-semibold">Past runs</h2>
            <ul className="space-y-1 text-sm">
              {pastRuns.map((r) => (
                <li key={r.name}>
                  <button
                    type="button"
                    onClick={() => loadPast(r.name)}
                    className="inline-flex items-center gap-2 rounded-md px-2 py-1 hover:bg-surface"
                  >
                    <FiFile className="text-muted" />
                    <span className="font-mono text-xs">{r.name}</span>
                    <span className="text-xs text-muted">
                      {(r.size / 1024).toFixed(1)} KB
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
