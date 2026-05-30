import React, { useState } from "react";
import { FiCheck, FiAlertTriangle, FiChevronDown, FiChevronRight } from "react-icons/fi";

// Render the labelled rule code in editorial style — small-caps source
// prefix, oxblood-underlined code. Handles the new paren-cite vocabulary
// from the backend ((FCA Handbook DISP 1.6.2R), (PRA Rulebook ...),
// (FSMA 2000 s.19)) and falls back to plain monospace for unknown shapes.
function FootnoteLabel({ raw }) {
  if (!raw) return null;
  const m = raw
    .replace(/^[\s(]+|[\s)]+$/g, "")
    .match(
      /^(FCA Handbook|PRA Rulebook|FSMA(?:\s+2000)?|FSA\s+2012|MLR\s+2017|PSR\s+2017|RAO\s+2001|UK\s+MAR)\s+(.+)$/
    );
  if (!m) {
    return <span className="font-mono text-[0.86rem] text-ink">{raw}</span>;
  }
  const source = m[1].trim();
  const code = m[2].trim();
  const isStatutory = !/^(FCA Handbook|PRA Rulebook)$/.test(source);
  if (isStatutory) {
    return (
      <span className="cite">
        <span className="code">{source} {code}</span>
      </span>
    );
  }
  return (
    <span className="cite">
      <span className="smallcaps">{source}&nbsp;</span>
      <span className="code">{code}</span>
    </span>
  );
}

function FootnoteItem({ n, raw, status, index, total }) {
  const verified = status === "verified";
  return (
    <li
      className={[
        "py-3 text-[0.92rem] leading-relaxed text-ink-soft",
        index === 0 ? "" : "border-t border-[var(--rule)]",
      ].join(" ")}
    >
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[0.78rem] font-semibold text-accent">
          {n}.
        </span>
        <FootnoteLabel raw={raw} />
        <span
          className={[
            "ml-auto inline-flex items-center gap-1 text-[0.66rem] uppercase tracking-[0.12em]",
            verified ? "text-verified" : "text-caution",
          ].join(" ")}
          title={verified ? "Matched in the knowledge graph" : "Not matched in the graph"}
        >
          {verified ? <FiCheck size={11} aria-hidden /> : <FiAlertTriangle size={11} aria-hidden />}
          {verified ? "verified" : "unverified"}
        </span>
      </div>
      {total > 1 && index === total - 1 && (
        <span className="sr-only">End of footnotes.</span>
      )}
    </li>
  );
}

function ClaimTraceItem({ entry, index }) {
  const [open, setOpen] = useState(index === 0);
  const claim = entry.claim || entry.text || "(claim)";
  const source = entry.source || entry.citation || "(source)";
  const chain = Array.isArray(entry.chain) ? entry.chain : [];

  return (
    <li className="border-t border-[var(--rule)] py-2.5 first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-1.5 text-left"
        aria-expanded={open}
      >
        <span className="mt-0.5 flex-none text-ink-mute">
          {open ? <FiChevronDown size={12} /> : <FiChevronRight size={12} />}
        </span>
        <span className="flex-1 text-[0.86rem] leading-snug text-ink">
          <span className="line-clamp-2">{claim}</span>
          <span className="mt-0.5 block">
            <FootnoteLabel raw={source} />
          </span>
        </span>
      </button>
      {open && chain.length > 0 && (
        <div className="mt-2 pl-5 text-[0.78rem] text-ink-mute">
          <div className="smallcaps-fallback pb-0.5">Chain</div>
          <ul className="m-0 list-none p-0">
            {chain.map((c, i) => (
              <li key={i} className="font-mono">
                {typeof c === "string" ? c : JSON.stringify(c)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

function Empty() {
  return (
    <div className="flex h-full flex-col px-5 py-7">
      <div className="smallcaps-fallback pb-2 text-ink-mute">
        Footnotes
      </div>
      <p className="font-display text-[0.95rem] italic leading-snug text-ink-soft">
        Each citation in the answer will appear here, numbered to its
        inline marker, with its verification state against the FinLaw
        knowledge graph.
      </p>
    </div>
  );
}

export default function SourcesPanel({ meta, mode, className = "" }) {
  const verification = meta?.verification || null;
  const verified = verification?.verified || [];
  const unverified = verification?.unverified || meta?.invalid || [];
  const claimTrace = Array.isArray(meta?.claim_trace) ? meta.claim_trace : [];
  const thoughtMs = meta?.thought_ms;

  const allCites = [
    ...verified.map((c) => ({ raw: c, status: "verified" })),
    ...unverified.map((c) => ({ raw: c, status: "unverified" })),
  ];
  const hasAnything =
    allCites.length || claimTrace.length || typeof thoughtMs === "number";

  return (
    <aside
      className={[
        "flex h-full w-full flex-col border-l border-[var(--rule)] bg-paper",
        className,
      ].join(" ")}
      aria-label="Footnotes"
    >
      {!hasAnything ? (
        <Empty />
      ) : (
        <div className="flex-1 overflow-y-auto px-5 py-5">
          <div className="flex items-baseline justify-between gap-3">
            <div className="smallcaps-fallback text-ink-mute">
              Footnotes
            </div>
            <span className="text-[0.7rem] text-ink-mute">
              {mode || "auto"}
              {typeof thoughtMs === "number"
                ? ` · ${(thoughtMs / 1000).toFixed(1)}s`
                : ""}
            </span>
          </div>

          {allCites.length > 0 && (
            <ol className="m-0 mt-3 list-none p-0">
              {allCites.map((c, i) => (
                <FootnoteItem
                  key={`${c.status}-${c.raw}-${i}`}
                  n={i + 1}
                  raw={c.raw}
                  status={c.status}
                  index={i}
                  total={allCites.length}
                />
              ))}
            </ol>
          )}

          {claimTrace.length > 0 && (
            <section className="mt-7">
              <div className="smallcaps-fallback pb-1 text-ink-mute">
                Claim trace
              </div>
              <ul className="m-0 list-none p-0">
                {claimTrace.map((entry, i) => (
                  <ClaimTraceItem key={i} entry={entry} index={i} />
                ))}
              </ul>
            </section>
          )}

          {verification && (
            <section className="mt-7 border-t border-[var(--rule)] pt-3 text-[0.82rem] text-ink-soft">
              {verification.all_grounded ? (
                <span className="text-verified">
                  All load-bearing claims matched in the graph.
                </span>
              ) : (
                <span className="text-caution">
                  Some citations could not be matched against the graph —
                  see the unverified entries above.
                </span>
              )}
            </section>
          )}

          <div className="mt-7 border-t border-[var(--rule)] pt-3 text-[0.78rem] leading-relaxed text-ink-mute">
            Verified entries match a node in the FCA Handbook, PRA
            Rulebook, or a UK statutory instrument held in the knowledge
            graph.
          </div>
        </div>
      )}
    </aside>
  );
}
