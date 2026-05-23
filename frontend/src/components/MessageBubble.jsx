import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { FiCopy, FiCheck, FiUser } from "react-icons/fi";
import Logo from "./Logo";
import AttachmentCard from "./AttachmentCard";

const sectionStyles = {
  "🟢 Green Areas": "border-risk-green bg-risk-green/10",
  "🟡 Yellow Areas": "border-risk-yellow bg-risk-yellow/10",
  "🟠 Amber Areas": "border-risk-amber bg-risk-amber/10",
  "🔴 Red Areas": "border-risk-red bg-risk-red/10",
};

const CITATION_RE = new RegExp(
  [
    "FSMA\\s+2000\\s+s\\.?\\d+[A-Z]?",
    "RAO\\s+2001\\s+art\\.?\\d+",
    "MLR\\s+2017\\s+r\\.?\\d+",
    "PSR\\s+2017\\s+r\\.?\\d+",
    "UK\\s+MAR\\s+art\\.?\\d+",
    "COBS\\s+\\d+(?:\\.\\d+)+[A-Z]?",
    "SYSC\\s+\\d+(?:\\.\\d+)+[A-Z]?",
    "DISP\\s+\\d+(?:\\.\\d+)+[A-Z]?",
    "PRIN\\s+\\d+(?:\\.\\d+)+[A-Z]?",
    "ICOBS\\s+\\d+(?:\\.\\d+)+[A-Z]?",
    "MAR\\s+\\d+(?:\\.\\d+)+[A-Z]?",
  ].join("|"),
  "g"
);

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

/**
 * Wrap citation tokens in <span class="cite-chip"> while skipping
 * fenced code blocks and inline code spans.
 */
function citationize(text) {
  if (!text) return text;
  const parts = text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  return parts
    .map((part) => {
      if (part.startsWith("```") || part.startsWith("`")) return part;
      return part.replace(
        CITATION_RE,
        (m) => `<span class="cite-chip">${m}</span>`
      );
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
        "absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-md text-slate transition-colors",
        "hover:bg-ivory-2 hover:text-ink",
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

export default function MessageBubble({ message }) {
  const { role, type, content, attachment } = message;
  const isUser = role === "user";
  const raw = typeof content === "string" ? content : "";
  const typing = type === "text" && raw === "" && role === "assistant";
  const display = useMemo(() => {
    const normalized = normalizeSections(raw);
    return citationize(normalized);
  }, [raw]);
  const isLong = (display?.match(/\n\n/g) || []).length >= 1;

  return (
    <div
      className={[
        "flex w-full animate-fade-in items-start gap-3",
        isUser ? "justify-end" : "justify-start",
      ].join(" ")}
    >
      {!isUser && (
        <div className="mt-0.5 hidden flex-none sm:block">
          <div className="grid h-8 w-8 place-items-center">
            <Logo variant="mark" size="sm" />
          </div>
        </div>
      )}

      <div
        className={[
          "relative max-w-[78%] rounded-bubble px-4 py-3",
          isUser
            ? "bg-ink text-ivory shadow-soft"
            : "border border-ivory-3 bg-white text-ink shadow-soft",
        ].join(" ")}
      >
        {type === "attachment" ? (
          <AttachmentCard
            name={attachment?.name}
            type={attachment?.type}
            size={attachment?.size}
          />
        ) : typing ? (
          <span className="cursor-blink text-slate">▍</span>
        ) : (
          <>
            {!isUser && <CopyBtn text={content || ""} />}
            <div
              className={[
                "prose prose-sm max-w-none",
                isUser ? "prose-invert" : "",
                !isUser && isLong ? "drop-cap" : "",
              ].join(" ")}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  h2({ children, ...props }) {
                    const key = children?.[0];
                    const style = sectionStyles[key] || "border-ivory-3 bg-ivory-2/50";
                    return (
                      <h2
                        className={`my-3 rounded-lg border-l-4 px-3 py-2 font-display text-base font-semibold ${style}`}
                        {...props}
                      >
                        {children}
                      </h2>
                    );
                  },
                  a({ node, children, ...props }) {
                    return (
                      <a
                        {...props}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="border-b border-gold/50 text-ink hover:border-gold"
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
                          className="rounded bg-ivory-2 px-1 py-0.5 text-[0.85em] text-ink"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    return (
                      <pre className="overflow-auto rounded-lg border border-ivory-3 bg-[#0F1419] p-3 text-[12px] leading-5 text-ivory">
                        <code className={className} {...props}>
                          {txt}
                        </code>
                      </pre>
                    );
                  },
                  table({ children }) {
                    return (
                      <div className="overflow-auto rounded-lg border border-ivory-3">
                        <table className="min-w-[520px]">{children}</table>
                      </div>
                    );
                  },
                  th({ children }) {
                    return (
                      <th className="border-b border-ivory-3 bg-ivory-2/60 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-slate">
                        {children}
                      </th>
                    );
                  },
                  td({ children }) {
                    return (
                      <td className="border-b border-ivory-3 px-3 py-2 text-left">
                        {children}
                      </td>
                    );
                  },
                  blockquote({ children }) {
                    return (
                      <blockquote className="border-l-4 border-gold/60 bg-ivory-2/50 px-3 py-2 italic text-ink/85">
                        {children}
                      </blockquote>
                    );
                  },
                }}
              >
                {display}
              </ReactMarkdown>
            </div>
          </>
        )}
      </div>

      {isUser && (
        <div className="mt-0.5 hidden flex-none sm:block">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-ink-2 text-ivory">
            <FiUser size={14} />
          </div>
        </div>
      )}
    </div>
  );
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
};
