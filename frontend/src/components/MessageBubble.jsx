import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { FiCopy, FiCheck, FiUser } from "react-icons/fi";
import { LuBot } from "react-icons/lu";
import AttachmentCard from "./AttachmentCard";

const sectionStyles = {
  "🟢 Green Areas": "border-risk-green bg-risk-green/10",
  "🟡 Yellow Areas": "border-risk-yellow bg-risk-yellow/10",
  "🟠 Amber Areas": "border-risk-amber bg-risk-amber/10",
  "🔴 Red Areas": "border-risk-red bg-risk-red/10",
};

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
      className={`absolute right-2 top-2 rounded-md border border-white/15 px-2 py-1 text-xs text-white/90 hover:bg-white/10 ${
        ok ? "bg-risk-green border-risk-green" : ""
      }`}
      onClick={copy}
      title="Copy"
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
  const display = useMemo(() => normalizeSections(raw), [raw]);

  return (
    <div className="flex w-full justify-center px-4">
      <div className="w-full max-w-chat">
        <div
          className={`flex items-start gap-3 py-2 ${
            isUser ? "justify-end" : "justify-start"
          }`}
        >
          {!isUser && (
            <div className="mt-1 hidden sm:block">
              <div className="grid h-8 w-8 place-items-center rounded-lg border border-white/15 bg-surface text-white">
                <LuBot size={16} />
              </div>
            </div>
          )}

          <div
            className={`relative max-w-[720px] rounded-bubble border px-4 py-3 ${
              isUser
                ? "bg-[#1b1f27] border-white/12 text-white"
                : "bg-surface border-white/15 text-white"
            }`}
          >
            {type === "attachment" ? (
              <AttachmentCard
                name={attachment?.name}
                type={attachment?.type}
                size={attachment?.size}
              />
            ) : typing ? (
              <span className="inline-block animate-pulse opacity-70">▍</span>
            ) : (
              <>
                {!isUser && <CopyBtn text={display || ""} />}
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                  components={{
                    h2({ children, ...props }) {
                      const key = children?.[0];
                      const style = sectionStyles[key] || "border-white/15";
                      return (
                        <h2
                          className={`mb-2 mt-3 rounded-lg border-l-4 px-3 py-2 font-semibold ${style}`}
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
                          className="underline text-accent hover:text-accent-hover"
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
                            className="rounded bg-black/40 px-1 py-0.5"
                            {...props}
                          >
                            {children}
                          </code>
                        );
                      return (
                        <div className="relative">
                          <pre className="overflow-auto rounded-lg border border-white/10 bg-[#0d1117] p-3 text-[12px] leading-5">
                            <code className={className} {...props}>
                              {txt}
                            </code>
                          </pre>
                        </div>
                      );
                    },
                    table({ children }) {
                      return (
                        <div className="overflow-auto rounded-lg border border-white/12">
                          <table className="min-w-[520px]">{children}</table>
                        </div>
                      );
                    },
                    th({ children }) {
                      return (
                        <th className="border-b border-white/12 px-3 py-2 text-left">
                          {children}
                        </th>
                      );
                    },
                    td({ children }) {
                      return (
                        <td className="border-b border-white/12 px-3 py-2 text-left">
                          {children}
                        </td>
                      );
                    },
                  }}
                >
                  {display}
                </ReactMarkdown>
              </>
            )}
          </div>

          {isUser && (
            <div className="mt-1 hidden sm:block">
              <div className="grid h-8 w-8 place-items-center rounded-lg border border-white/15 bg-surface text-white">
                <FiUser size={16} />
              </div>
            </div>
          )}
        </div>
      </div>
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
