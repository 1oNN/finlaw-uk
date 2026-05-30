import { useState, useRef, useEffect, useCallback } from "react";
import {
  FiSend,
  FiPaperclip,
  FiSquare,
  FiX,
  FiBookOpen,
} from "react-icons/fi";
import MessageBubble from "./MessageBubble";
import DisclaimerBand from "./DisclaimerBand";

const API_BASE = "http://localhost:5000";
const CHAT_LIST_KEY = "flgpt:chats";
const CHAT_DATA_KEY = (id) => `flgpt:chat:${id}`;
const uid = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const loadChats = () => {
  try {
    return JSON.parse(localStorage.getItem(CHAT_LIST_KEY) || "[]");
  } catch {
    return [];
  }
};
const saveChats = (list) =>
  localStorage.setItem(CHAT_LIST_KEY, JSON.stringify(list));
const loadChatMessages = (id) => {
  try {
    return JSON.parse(localStorage.getItem(CHAT_DATA_KEY(id)) || "[]");
  } catch {
    return [];
  }
};
const safeSaveMessages = (id, msgs) => {
  try {
    localStorage.setItem(CHAT_DATA_KEY(id), JSON.stringify(msgs));
  } catch {}
};

const MODES = [
  { key: "auto", label: "Auto", hint: "auto-route" },
  { key: "general", label: "General", hint: "free-form" },
  { key: "finance", label: "Finance", hint: "RAG" },
  { key: "traffic-light", label: "Risk", hint: "traffic-light" },
];

const SUGGESTIONS = [
  "What is the 'general prohibition' in UK financial services?",
  "What is the FSCS deposit protection limit per individual?",
  "What standard applies to financial promotions in the UK?",
  "How many days does a consumer have to cancel a general insurance policy?",
];

export default function Chat({
  activeChatId,
  onChatCreated,
  onMetaUpdate,
  onModeChange,
  onOpenSources,
}) {
  const [chatId, setChatId] = useState(activeChatId || uid());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setStreaming] = useState(false);
  const [abortCtrl, setAbortCtrl] = useState(null);

  const [filename, setFilename] = useState("");
  const model = "mistral:7b-instruct";
  const [mode, setMode] = useState("auto");
  const [status, setStatus] = useState("");

  const [dragOver, setDragOver] = useState(false);
  const bottomRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const isNearBottomRef = useRef(true);
  const textRef = useRef(null);
  const token =
    typeof localStorage !== "undefined"
      ? localStorage.getItem("access_token")
      : null;

  // re-load when active chat switches
  useEffect(() => {
    if (activeChatId && activeChatId !== chatId) {
      setChatId(activeChatId);
    }
  }, [activeChatId, chatId]);

  useEffect(() => setMessages(loadChatMessages(chatId)), [chatId]);
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      isNearBottomRef.current =
        el.scrollHeight - (el.scrollTop + el.clientHeight) < 80;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    // Auto-scroll only when the user is near the bottom OR the last message
    // is the user's own — a freshly-sent prompt should always pull into view.
    const last = messages[messages.length - 1];
    if (!last) return;
    if (last.role === "user" || isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isStreaming]);
  useEffect(() => safeSaveMessages(chatId, messages), [chatId, messages]);
  useEffect(() => onModeChange?.(mode), [mode, onModeChange]);

  const ensureChatListed = useCallback(
    (firstUserText) => {
      const list = loadChats();
      if (!list.some((c) => c.id === chatId)) {
        const title =
          firstUserText?.slice(0, 60) || `Chat ${new Date().toLocaleString()}`;
        saveChats([{ id: chatId, title, createdAt: Date.now() }, ...list]);
        onChatCreated?.(chatId);
      }
    },
    [chatId, onChatCreated]
  );

  function autogrow() {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "0px";
    const h = Math.min(el.scrollHeight, 240);
    el.style.height = Math.max(46, h) + "px";
  }
  useEffect(() => autogrow(), []);

  async function uploadFile(file) {
    const body = new FormData();
    body.append("file", file);
    body.append("session_id", chatId);
    let res;
    try {
      res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body,
      });
    } catch {
      setStatus("Upload failed.");
      return;
    }
    if (!res.ok) {
      let msg = "Upload failed.";
      try {
        const j = await res.json();
        if (j?.error) msg = j.error;
      } catch {}
      setStatus(msg);
      setMessages((m) => [
        ...m,
        {
          id: uid(),
          role: "user",
          type: "attachment",
          content: "",
          attachment: {
            name: file.name,
            type: file.type,
            size: file.size,
            error: msg,
          },
        },
      ]);
      return;
    }
    const { filename: fn, chunks } = await res.json();
    setFilename(fn);
    setStatus(`Attached ${fn} (${chunks} chunks)`);
    setTimeout(() => setStatus(""), 1500);

    setMessages((m) => [
      ...m,
      {
        id: uid(),
        role: "user",
        type: "attachment",
        content: "",
        attachment: {
          name: file.name,
          type: file.type,
          size: file.size,
          chunks,
        },
      },
    ]);
  }
  const onFileInput = (e) => {
    const f = e.target.files?.[0];
    if (f) uploadFile(f);
    e.target.value = "";
  };
  const clearFile = () => setFilename("");

  const onDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };
  const onDragLeave = () => setDragOver(false);
  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) uploadFile(f);
  };

  function pushMetaPlaceholder() {
    setMessages((m) => [
      ...m,
      { role: "meta", type: "text", thoughtMs: null, id: uid() },
    ]);
  }
  function setMeta(ms) {
    setMessages((m) => {
      const idx = m.findIndex((x) => x.role === "meta" && x.thoughtMs == null);
      if (idx === -1) return m;
      const copy = [...m];
      copy[idx] = {
        role: "meta",
        type: "text",
        thoughtMs: ms,
        id: copy[idx].id,
      };
      return copy;
    });
  }

  async function send(textOverride) {
    const prompt =
      typeof textOverride === "string" && textOverride.trim()
        ? textOverride.trim()
        : input.trim();
    if (!prompt && !filename) return;

    ensureChatListed(prompt || filename);

    setMessages((m) => [
      ...m,
      {
        id: uid(),
        role: "user",
        type: "text",
        content:
          prompt ||
          `📄 Please review the uploaded file thoroughly: **${
            filename || "N/A"
          }**`,
      },
      { id: uid(), role: "assistant", type: "text", content: "" },
    ]);
    pushMetaPlaceholder();
    if (!textOverride) {
      setInput("");
    }
    autogrow();
    setStreaming(true);
    setStatus("");
    // reset previous meta — new question, new sources
    onMetaUpdate?.(null);

    const ctrl = new AbortController();
    setAbortCtrl(ctrl);

    let res;
    try {
      res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ prompt, filename, mode, model, session_id: chatId }),
        signal: ctrl.signal,
      });
    } catch {
      res = null;
    }

    if (!res || !res.ok || !res.body) {
      setMessages((m) => {
        const idx = [...m]
          .map((x, i) => [x.role, i])
          .filter(([r]) => r === "assistant")
          .pop()?.[1];
        if (idx == null) return m;
        const copy = [...m];
        copy[idx] = { ...copy[idx], content: "Error contacting backend." };
        return copy;
      });
      setMeta(0);
      setStreaming(false);
      setStatus("Backend error.");
      return;
    }

    const reader = res.body.getReader();
    const dec = new TextDecoder("utf-8");
    let buf = "";
    let finished = false;
    let accumulatedMeta = {};

    const appendToken = (t) => {
      setMessages((m) => {
        const idx = [...m]
          .map((x, i) => [x.role, i])
          .filter(([r]) => r === "assistant")
          .pop()?.[1];
        if (idx == null) return m;
        const copy = [...m];
        copy[idx] = { ...copy[idx], content: (copy[idx].content || "") + t };
        return copy;
      });
    };

    const handlePacket = (packet) => {
      let ev = "message";
      let data = "";
      for (const rawLine of packet.split(/\r?\n/)) {
        if (!rawLine) continue;
        const line = rawLine.trimStart();
        if (line.startsWith("event:")) ev = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5);
      }
      if (ev === "meta") {
        try {
          const j = JSON.parse(data || "{}");
          const ms = j.thought_ms ?? j.thoughtMs;
          if (typeof ms === "number") setMeta(ms);
          accumulatedMeta = { ...accumulatedMeta, ...j };
          onMetaUpdate?.(accumulatedMeta);
        } catch {
          setMeta(0);
        }
        return;
      }
      if (ev === "done") {
        finished = true;
        return;
      }
      if (ev === "message" || ev === "") appendToken(data);
    };

    while (!finished) {
      const { value, done } = await reader.read().catch(() => ({ done: true }));
      if (done) {
        if (buf.trim()) handlePacket(buf);
        finished = true;
        break;
      }
      if (value) {
        buf += dec.decode(value, { stream: true });
        const parts = buf.split(/\r?\n\r?\n/);
        buf = parts.pop() || "";
        for (const p of parts) handlePacket(p);
      }
    }
    try {
      reader.cancel();
    } catch {}
    setStreaming(false);
  }

  const stop = () => {
    abortCtrl?.abort();
    setStreaming(false);
    setStatus("Stopped");
    setTimeout(() => setStatus(""), 900);
  };

  function regenerate() {
    if (isStreaming) return;
    // Find the most recent user-text message; drop it and everything after,
    // then re-send so a fresh user+assistant pair takes its place.
    let lastUserText = null;
    let dropFromIdx = messages.length;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "user" && m.type === "text" && (m.content || "").trim()) {
        lastUserText = m.content;
        dropFromIdx = i;
        break;
      }
    }
    if (!lastUserText) return;
    setMessages((cur) => cur.slice(0, dropFromIdx));
    setTimeout(() => send(lastUserText), 0);
  }
  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };
  const canSend = !!input.trim() || !!filename;
  const isEmpty = messages.length === 0;

  return (
    <div
      className="flex h-full flex-col"
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragLeave={onDragLeave}
    >
      {/* Top controls — hairline only, no card */}
      <div className="border-b border-[var(--rule)] bg-paper">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-5 py-2.5">
          <div className="inline-flex items-baseline gap-4">
            {MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => setMode(m.key)}
                disabled={isStreaming}
                title={m.hint}
                className={[
                  "text-[0.78rem] font-medium tracking-wide transition-colors",
                  mode === m.key
                    ? "text-accent"
                    : "text-ink-soft hover:text-ink",
                  isStreaming ? "cursor-not-allowed opacity-60" : "",
                ].join(" ")}
              >
                {mode === m.key && (
                  <span aria-hidden className="mr-1.5 inline-block h-1 w-1 -translate-y-[1px] rounded-full bg-accent align-middle" />
                )}
                {m.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {isStreaming && (
              <span className="hidden text-[0.78rem] italic text-ink-mute sm:inline">
                thinking…
              </span>
            )}
            {status && (
              <span className="text-[0.78rem] italic text-ink-soft">
                {status}
              </span>
            )}
            <button
              type="button"
              onClick={onOpenSources}
              className="inline-flex items-center gap-1 text-[0.78rem] text-ink-soft hover:text-accent lg:hidden"
            >
              <FiBookOpen size={12} aria-hidden />
              Footnotes
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-5 py-10">
          {isEmpty ? (
            <div className="mx-auto max-w-xl pt-6">
              <div className="font-display text-[2.4rem] text-accent leading-none">
                ¶
              </div>
              <h2 className="mt-3 font-display text-[1.75rem] font-normal leading-tight tracking-tightish text-ink">
                Ask about UK financial regulation.
              </h2>
              <p className="mt-3 text-[0.95rem] leading-relaxed text-ink-soft">
                Plain English is fine. FinLaw-UK will retrieve the
                relevant provisions and ground the answer in the FCA
                Handbook, PRA Rulebook, and UK statutory instruments —
                with every claim linked to its footnote.
              </p>

              <div className="smallcaps-fallback mt-9 pb-2 text-ink-mute">
                Try
              </div>
              <ul className="m-0 list-none p-0">
                {SUGGESTIONS.map((s, i) => (
                  <li
                    key={s}
                    className={i === 0 ? "" : "border-t border-[var(--rule)]"}
                  >
                    <button
                      type="button"
                      onClick={() => send(s)}
                      className="w-full py-3 text-left font-display text-[1.02rem] italic text-ink-soft transition-colors hover:text-accent"
                    >
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div>
              {(() => {
                let latestAssistantIdx = -1;
                for (let i = messages.length - 1; i >= 0; i--) {
                  if (messages[i]?.role === "assistant") {
                    latestAssistantIdx = i;
                    break;
                  }
                }
                return messages.map((m, idx) =>
                  m.role === "meta" ? (
                    <div
                      key={m.id}
                      className="pb-3 pt-1 text-[0.78rem] italic text-ink-mute"
                    >
                      {m.thoughtMs == null
                        ? "Thinking…"
                        : `Thought for ${(m.thoughtMs / 1000).toFixed(1)} s`}
                    </div>
                  ) : (
                    <div
                      key={m.id}
                      className={
                        idx > 0 && messages[idx - 1]?.role === "assistant"
                          ? "border-t border-[var(--rule)] pt-2"
                          : ""
                      }
                    >
                      <MessageBubble
                        message={m}
                        onRegenerate={
                          idx === latestAssistantIdx &&
                          !isStreaming &&
                          (m.content || "").trim()
                            ? regenerate
                            : undefined
                        }
                      />
                    </div>
                  )
                );
              })()}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>

      {/* Composer — hairline-only, no shadow, no rounded card */}
      <div className="border-t border-[var(--rule)] bg-paper">
        <div className="mx-auto w-full max-w-3xl px-5 pb-3 pt-3">
          {filename && (
            <div className="mb-2 flex items-baseline justify-between gap-3 border-b border-[var(--rule)] pb-2 text-[0.86rem] text-ink-soft">
              <div className="truncate">
                <span className="smallcaps-fallback mr-2 text-ink-mute">
                  Attached
                </span>
                <span className="font-medium text-ink">{filename}</span>
              </div>
              <button
                className="text-ink-mute hover:text-accent"
                onClick={clearFile}
                title="Remove file"
                aria-label="Remove attached file"
              >
                <FiX size={14} />
              </button>
            </div>
          )}

          <div className="flex items-end gap-2 border border-[var(--rule-2)] bg-paper px-2 py-1.5 transition-colors focus-within:border-accent">
            <label
              className="grid h-10 w-9 flex-none cursor-pointer place-items-center text-ink-mute hover:text-accent"
              title="Attach a file"
              aria-label="Attach a file"
            >
              <FiPaperclip size={15} />
              <input className="hidden" type="file" onChange={onFileInput} />
            </label>

            <textarea
              ref={textRef}
              rows={1}
              placeholder="Ask about UK financial regulation"
              className="max-h-60 min-h-[40px] flex-1 resize-none bg-transparent px-1 py-2 text-[0.98rem] text-ink outline-none placeholder:text-ink-mute"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                autogrow();
              }}
              onKeyDown={onKeyDown}
              disabled={isStreaming}
            />

            {isStreaming ? (
              <button
                type="button"
                className="px-3 py-2 text-[0.84rem] font-medium tracking-wide text-danger hover:text-accent"
                onClick={stop}
                title="Stop generating"
                aria-label="Stop generating"
              >
                <FiSquare size={13} className="-mt-0.5 mr-1 inline" aria-hidden />
                Stop
              </button>
            ) : (
              <button
                type="button"
                disabled={!canSend}
                className={[
                  "px-3.5 py-2 text-[0.84rem] font-medium tracking-wide transition-colors",
                  canSend
                    ? "bg-ink text-paper hover:bg-accent"
                    : "cursor-not-allowed bg-mute text-ink-mute",
                ].join(" ")}
                onClick={() => send()}
                title="Send"
                aria-label="Send"
              >
                <FiSend size={13} className="-mt-0.5 mr-1 inline" aria-hidden />
                Send
              </button>
            )}
          </div>
          <div className="mt-2 flex items-center justify-between gap-2 px-0.5">
            <DisclaimerBand variant="thin" />
            <span className="text-[0.72rem] text-ink-mute">
              Enter to send · Shift+Enter for newline
            </span>
          </div>
        </div>
      </div>

      {dragOver && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/30">
          <div className="border-2 border-dashed border-accent bg-paper px-10 py-8 text-center font-display text-xl text-ink">
            Drop the file to attach
          </div>
        </div>
      )}
    </div>
  );
}
