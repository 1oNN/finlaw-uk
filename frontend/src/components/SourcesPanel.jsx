import React, { useState } from "react";
import {
  FiCheck,
  FiAlertTriangle,
  FiChevronDown,
  FiChevronRight,
  FiClock,
  FiFileText,
} from "react-icons/fi";
import Logo from "./Logo";

function CitationChip({ name, status }) {
  const isVerified = status === "verified";
  return (
    <li className="flex items-center gap-2 rounded-md border border-ivory-3 bg-white px-2.5 py-1.5">
      <span
        className={`grid h-5 w-5 flex-none place-items-center rounded-full ${
          isVerified
            ? "bg-verified/15 text-verified"
            : "bg-caution/15 text-caution"
        }`}
      >
        {isVerified ? <FiCheck size={11} /> : <FiAlertTriangle size={11} />}
      </span>
      <span className="font-mono text-[12px] text-ink">{name}</span>
      <span
        className={`ml-auto text-[10px] uppercase tracking-wide ${
          isVerified ? "text-verified" : "text-caution"
        }`}
      >
        {isVerified ? "verified" : "unverified"}
      </span>
    </li>
  );
}

function ClaimTraceItem({ entry, index }) {
  const [open, setOpen] = useState(index === 0);
  const claim = entry.claim || entry.text || "(claim)";
  const source = entry.source || entry.citation || "(source)";
  const chain = Array.isArray(entry.chain) ? entry.chain : [];

  return (
    <li className="rounded-md border border-ivory-3 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-2 px-3 py-2 text-left"
        aria-expanded={open}
      >
        <span className="mt-0.5 text-slate">
          {open ? <FiChevronDown size={14} /> : <FiChevronRight size={14} />}
        </span>
        <span className="flex-1 text-xs text-ink">
          <span className="line-clamp-2">{claim}</span>
          <span className="mt-1 block font-mono text-[11px] text-gold-2">
            {source}
          </span>
        </span>
      </button>
      {open && chain.length > 0 && (
        <div className="border-t border-ivory-3 px-3 py-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate">
            Chain
          </div>
          <ul className="mt-1 space-y-0.5">
            {chain.map((c, i) => (
              <li key={i} className="font-mono text-[11px] text-slate">
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
    <div className="flex h-full flex-col items-center justify-center px-6 py-10 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full bg-ivory-2">
        <Logo variant="mark" size="sm" monochrome className="text-slate/60" />
      </div>
      <p className="mt-4 text-sm font-medium text-ink">
        Sources & verification
      </p>
      <p className="mt-1 max-w-[220px] text-xs text-slate">
        Once you ask a question, each citation is checked against the
        knowledge graph and listed here with its verification state.
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

  const hasAnything =
    verified.length || unverified.length || claimTrace.length || thoughtMs;

  return (
    <aside
      className={[
        "flex h-full w-full flex-col bg-ivory-2/40",
        "border-l border-ivory-3",
        className,
      ].join(" ")}
      aria-label="Sources and verification"
    >
      <div className="border-b border-ivory-3 bg-ivory/70 px-4 py-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate">
          Sources & verification
        </div>
        <div className="mt-0.5 text-xs text-slate/80">
          Audit trail for the last answer.
        </div>
      </div>

      {!hasAnything ? (
        <Empty />
      ) : (
        <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
          {/* Status strip */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md border border-ivory-3 bg-white px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-slate">
                Mode
              </div>
              <div className="mt-0.5 font-mono text-[12px] text-ink">
                {mode || "auto"}
              </div>
            </div>
            <div className="rounded-md border border-ivory-3 bg-white px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-slate">
                <FiClock className="-mt-0.5 mr-1 inline" size={10} />
                Thought
              </div>
              <div className="mt-0.5 font-mono text-[12px] text-ink">
                {typeof thoughtMs === "number"
                  ? `${(thoughtMs / 1000).toFixed(1)} s`
                  : "—"}
              </div>
            </div>
          </div>

          {/* Citations */}
          {(verified.length > 0 || unverified.length > 0) && (
            <div>
              <div className="mb-2 flex items-baseline justify-between">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate">
                  Citations
                </h3>
                <span className="text-[10px] text-slate">
                  {verified.length} verified
                  {unverified.length
                    ? ` · ${unverified.length} unverified`
                    : ""}
                </span>
              </div>
              <ul className="space-y-1.5">
                {verified.map((c) => (
                  <CitationChip key={`v-${c}`} name={c} status="verified" />
                ))}
                {unverified.map((c) => (
                  <CitationChip key={`u-${c}`} name={c} status="unverified" />
                ))}
              </ul>
            </div>
          )}

          {/* Claim trace */}
          {claimTrace.length > 0 && (
            <div>
              <div className="mb-2 flex items-baseline justify-between">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate">
                  Claim trace
                </h3>
                <span className="text-[10px] text-slate">
                  {claimTrace.length} claims
                </span>
              </div>
              <ul className="space-y-1.5">
                {claimTrace.map((entry, i) => (
                  <ClaimTraceItem key={i} entry={entry} index={i} />
                ))}
              </ul>
            </div>
          )}

          {/* Verification summary */}
          {verification && (
            <div className="rounded-md border border-ivory-3 bg-white px-3 py-2 text-[11px] text-slate">
              <div className="flex items-center gap-1.5">
                <FiFileText size={12} aria-hidden />
                <span className="font-semibold text-ink">Verification</span>
              </div>
              <div className="mt-1">
                {verification.all_grounded ? (
                  <span className="text-verified">
                    All load-bearing claims grounded.
                  </span>
                ) : (
                  <span className="text-caution">
                    Some claims could not be verified — see unverified
                    citations above.
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
