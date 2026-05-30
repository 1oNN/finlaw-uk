import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { FiCopy, FiCheck, FiRefreshCw } from "react-icons/fi";
import AttachmentCard from "./AttachmentCard";

const sectionStyles = {
  "🟢 Green Areas": "border-risk-green bg-risk-green/10",
  "🟡 Yellow Areas": "border-risk-yellow bg-risk-yellow/10",
  "🟠 Amber Areas": "border-risk-amber bg-risk-amber/10",
  "🔴 Red Areas": "border-risk-red bg-risk-red/10",
};

// Editorial citation render. Matches the new generator-prompt form
//   (FCA Handbook DISP 1.6.2R)           — paren with source prefix
//   (PRA Rulebook Fundamental Rules 2)   — PRA branch
//   (FSMA 2000 s.19)                     — statutory, no source prefix
// The source name is rendered in small-caps, the rule code gets an
// oxblood underline. Falls through to the legacy bracket form
// [DISP 1.6.2R] without crashing if the model regresses.
const PAREN_CITE_RE =
  /\(((?:FCA Handbook|PRA Rulebook|FSMA(?:\s+2000)?|FSA\s+2012|MLR\s+2017|PSR\s+2017|RAO\s+2001|UK\s+MAR)[^)]*)\)/g;
const LEGACY_BRACKET_RE =
  /\[((?:FSMA\s+2000\s+s\.?\d+[A-Z]?|RAO\s+2001\s+art\.?\d+|MLR\s+2017\s+r\.?\d+|PSR\s+2017\s+r\.?\d+|UK\s+MAR\s+art\.?\d+|COBS\s+\d+(?:\.\d+)+[A-Z]?|SYSC\s+\d+(?:\.\d+)+[A-Z]?|DISP\s+\d+(?:\.\d+)+[A-Z]?|PRIN\s+\d+(?:\.\d+)+[A-Z]?|ICOBS\s+\d+(?:\.\d+)+[A-Z]?|MAR\s+\d+(?:\.\d+)+[A-Z]?))\]/g;

function normalizeSections(text) {
  if (!text) return text;
  let t = String(text);
  t = t.replace(
    /(?!^) *(\n?)(?:#+\s*)?(🟢|🟡|🟠|🔴)\s+(Green|Yellow|Amber|Red)\s+Areas\b/gi,
    (_m, _nl, emoji, color) =>
      `\n\n## ${emoji} ${color[0].toUpperCase() + color.slice(1)} Areas`
  );
  t = t.replace(
    /([^\n])\s*(##\s*(?:🟢|🟡|🟠|🔴)\s+[^\n]+)/g,
    (_m, prev, hdr) => `${prev}\n\n${hdr}`
  );
  t = t.replace(
    /(##\s*(?:🟢|🟡|🟠|🔴)\s+[^\n]+)\s*(?!\n\n)/g,
    (_m, hdr) => `${hdr}\n\n`
  );
  t = t.replace(/\n{3,}/g, "\n\n");
  return t.trim();
}

// Split a paren-cite payload into (source, code) where source is the
// editorial prefix (FCA Handbook / PRA Rulebook / FSMA 2000 / ...) and
// code is the rule citation that gets the oxblood underline.
function splitCite(payload) {
  const m = payload.match(
    /^(FCA Handbook|PRA Rulebook|FSMA(?:\s+2000)?|FSA\s+2012|MLR\s+2017|PSR\s+2017|RAO\s+2001|UK\s+MAR)\s*(.*)$/
  );
  if (!m) return { source: "", code: payload };
  return { source: m[1].trim(), code: m[2].trim() || m[1].trim() };
}

// Wrap citation tokens in editorial spans while skipping fenced and
// inline code blocks (so we don't restyle code samples).
function citationize(text) {
  if (!text) return text;
  const parts = text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  return parts
    .map((part) => {
      if (part.startsWith("```") || part.startsWith("`")) return part;
      let out = part.replace(PAREN_CITE_RE, (_m, payload) => {
        const { source, code } = splitCite(payload);
        if (!source) {
          return `(<span class="cite"><span class="code">${payload}</span></span>)`;
        }
        // Statutory short-form has no source prefix; otherwise small-caps the source.
        const isStatutory = !/^(FCA Handbook|PRA Rulebook)$/.test(source);
        if (isStatutory) {
          return `(<span class="cite"><span class="code">${source} ${code}</span></span>)`;
        }
        return `(<span class="cite"><span class="smallcaps">${source}&nbsp;</span><span class="code">${code}</span></span>)`;
      });
      out = out.replace(LEGACY_BRACKET_RE, (_m, code) => {
        return `<span class="cite"><span class="code">${code}</span></span>`;
      });
      return out;
    })
    .join("");
}

function CopyBtn({ text }) {
  const [ok, setOk] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setOk(true);
      setTimeout(() => setOk(false), 900);
    } catch {}
  };
  return (
    <button
      className={[
        "grid h-7 w-7 place-items-center rounded-md text-ink-soft transition-colors",
        "hover:text-accent",
        ok ? "text-verified" : "",
      ].join(" ")}
      onClick={copy}
      title={ok ? "Copied" : "Copy"}
      aria-label="Copy message"
    >
      {ok ? <FiCheck size={14} /> : <FiCopy size={14} />}
    </button>
  );
}

function RegenBtn({ onClick, disabled }) {
  return (
    <button
      className={[
        "grid h-7 w-7 place-items-center rounded-md text-ink-soft transition-colors",
        disabled ? "cursor-not-allowed opacity-50" : "hover:text-accent",
      ].join(" ")}
      onClick={onClick}
      disabled={disabled}
      title="Regenerate"
      aria-label="Regenerate response"
    >
      <FiRefreshCw size={14} />
    </button>
  );
}

// User's question — small italic block in serif, accent rule on the left,
// labelled "your question" in small-caps above. Not a chat bubble.
function UserQuery({ message }) {
  const { type, content, attachment } = message;
  if (type === "attachment") {
    return (
      <div className="animate-fade-in py-3">
        <div className="smallcaps-fallback pb-1.5 text-ink-mute">
          Your upload
        </div>
        <AttachmentCard
          name={attachment?.name}
          type={attachment?.type}
          size={attachment?.size}
          chunks={attachment?.chunks}
          error={attachment?.error}
        />
      </div>
    );
  }
  return (
    <div className="animate-fade-in py-3">
      <div className="smallcaps-fallback pb-1.5 text-ink-mute">
        Your question
      </div>
      <blockquote
        className="font-display border-l-2 border-rule-2 pl-3.5 text-[1.02rem] italic text-ink-soft"
        style={{ marginInlineStart: 0, marginInlineEnd: 0 }}
      >
        {content}
      </blockquote>
    </div>
  );
}

// Assistant's answer — flowing typeset prose, no container, no avatar.
function AssistantAnswer({ message, onRegenerate }) {
  const { content } = message;
  const raw = typeof content === "string" ? content : "";
  const typing = raw === "";
  const display = useMemo(() => {
    const normalized = normalizeSections(raw);
    return citationize(normalized);
  }, [raw]);

  if (typing) {
    return (
      <div className="animate-fade-in pb-6 pt-1">
        <span className="cursor-blink">▍</span>
      </div>
    );
  }

  return (
    <article className="group animate-fade-in pb-8 pt-1">
      <div className="finlaw-prose prose prose-base max-w-prose font-sans text-[1rem] leading-[1.62] text-ink">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            p({ children, ...props }) {
              return (
                <p className="mb-4 leading-[1.62]" {...props}>
                  {children}
                </p>
              );
            },
            // Traffic-light section headers — keep the colored block so the
            // Risk-review mode still reads as a structured audit.
            h2({ children, ...props }) {
              const key = children?.[0];
              const style = sectionStyles[key] || "border-rule-2 bg-mute/60";
              return (
                <h2
                  className={`mb-3 mt-6 rounded-card border-l-4 px-3 py-2 font-display text-base font-semibold ${style}`}
                  {...props}
                >
                  {children}
                </h2>
              );
            },
            a({ children, ...props }) {
              return (
                <a
                  {...props}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="border-b border-accent text-ink hover:border-accent-2 hover:text-accent-2"
                >
                  {children}
                </a>
              );
            },
            code({ inline, className, children, ...props }) {
              const txt = String(children).replace(/\n$/, "");
              if (inline)
                return (
                  <code
                    className="rounded-sm bg-mute px-1 py-0.5 font-mono text-[0.85em] text-ink"
                    {...props}
                  >
                    {children}
                  </code>
                );
              return (
                <pre className="overflow-auto rounded-card border border-rule bg-[#1A1A1A] p-3 font-mono text-[12px] leading-5 text-paper">
                  <code className={className} {...props}>
                    {txt}
                  </code>
                </pre>
              );
            },
            table({ children }) {
              return (
                <div className="my-4 overflow-auto border-y border-rule">
                  <table className="min-w-[520px] border-collapse">
                    {children}
                  </table>
                </div>
              );
            },
            th({ children }) {
              return (
                <th className="border-b border-rule px-3 py-2 text-left text-[0.74rem] font-semibold uppercase tracking-[0.1em] text-ink-soft">
                  {children}
                </th>
              );
            },
            td({ children }) {
              return (
                <td className="border-b border-rule px-3 py-2 text-left">
                  {children}
                </td>
              );
            },
            ul({ children }) {
              return (
                <ul className="my-3 list-disc space-y-1 pl-5 marker:text-ink-mute">
                  {children}
                </ul>
              );
            },
            ol({ children }) {
              return (
                <ol className="my-3 list-decimal space-y-1 pl-5 marker:text-ink-mute">
                  {children}
                </ol>
              );
            },
            blockquote({ children }) {
              return (
                <blockquote className="my-4 border-l-2 border-accent pl-4 italic text-ink-soft">
                  {children}
                </blockquote>
              );
            },
            strong({ children }) {
              // The new generator prompt restricts bold to inside paren-cites,
              // which we render via inline HTML spans already. Markdown
              // **bold** that does slip through gets a subtle weight bump
              // and the accent color — never a heavy display weight.
              return (
                <strong className="font-medium text-ink">{children}</strong>
              );
            },
          }}
        >
          {display}
        </ReactMarkdown>
      </div>
      <div className="mt-2 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <CopyBtn text={content || ""} />
        {onRegenerate && <RegenBtn onClick={onRegenerate} />}
      </div>
    </article>
  );
}

export default function MessageBubble({ message, onRegenerate }) {
  const { role } = message;
  if (role === "user") return <UserQuery message={message} />;
  return <AssistantAnswer message={message} onRegenerate={onRegenerate} />;
}

MessageBubble.propTypes = {
  message: PropTypes.shape({
    id: PropTypes.string.isRequired,
    role: PropTypes.oneOf(["user", "assistant", "meta"]).isRequired,
    type: PropTypes.oneOf(["text", "attachment"]).isRequired,
    content: PropTypes.string,
    attachment: PropTypes.shape({
      name: PropTypes.string,
      type: PropTypes.string,
      size: PropTypes.number,
    }),
    thoughtMs: PropTypes.number,
  }).isRequired,
  onRegenerate: PropTypes.func,
};
