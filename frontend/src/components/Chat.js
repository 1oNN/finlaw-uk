import { useState, useRef, useEffect, useCallback } from "react";
import {
  FiSend,
  FiPaperclip,
  FiSquare,
  FiX,
  FiBookOpen,
  FiArrowRight,
} from "react-icons/fi";
import MessageBubble from "./MessageBubble";
import DisclaimerBand from "./DisclaimerBand";
import Logo from "./Logo";

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
  useEffect(
    () => bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
    [messages, isStreaming]
  );
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
      {/* Top controls */}
      <div className="border-b border-ivory-3 bg-ivory/85 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-4 py-2.5">
          <div className="inline-flex rounded-lg border border-ivory-3 bg-white p-0.5">
            {MODES.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => setMode(m.key)}
                disabled={isStreaming}
                title={m.hint}
                className={[
                  "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                  mode === m.key
                    ? "bg-ink text-ivory"
                    : "text-slate hover:text-ink",
                  isStreaming ? "cursor-not-allowed opacity-60" : "",
                ].join(" ")}
              >
                {m.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            {isStreaming && (
              <span className="hidden animate-pulse text-xs text-slate sm:inline">
                thinking…
              </span>
            )}
            {status && (
              <span className="rounded-chip border border-ivory-3 bg-white px-2.5 py-1 text-xs text-ink">
                {status}
              </span>
            )}
            <button
              type="button"
              onClick={onOpenSources}
              className="inline-flex items-center gap-1.5 rounded-md border border-ivory-3 bg-white px-2.5 py-1 text-xs font-medium text-ink hover:border-gold/40 lg:hidden"
            >
              <FiBookOpen size={12} />
              Sources
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-8">
          {isEmpty ? (
            <div className="mx-auto max-w-xl pt-6 text-center">
              <div className="mx-auto mb-5 grid h-14 w-14 place-items-center">
                <Logo variant="mark" size="lg" />
              </div>
              <h2 className="font-display text-2xl font-semibold text-ink">
                What does the corpus say?
              </h2>
              <p className="mt-2 text-sm text-slate">
                Ask in plain English. FinLaw will retrieve the relevant
                provisions and ground the answer with UK short-form
                citations.
              </p>

              <ul className="mx-auto mt-7 grid max-w-lg gap-2 text-left">
                {SUGGESTIONS.map((s) => (
                  <li key={s}>
                    <button
                      type="button"
                      onClick={() => send(s)}
                      className="group flex w-full items-start gap-3 rounded-lg border border-ivory-3 bg-white px-4 py-3 text-sm text-ink shadow-soft transition-colors hover:border-gold/40"
                    >
                      <span className="mt-0.5 text-gold-2">
                        <FiArrowRight size={14} />
                      </span>
                      <span className="text-left">{s}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((m) =>
                m.role === "meta" ? (
                  <div
                    key={m.id}
                    className="pl-1 text-xs text-slate"
                  >
                    {m.thoughtMs == null
                      ? "Thinking…"
                      : `Thought for ${(m.thoughtMs / 1000).toFixed(1)} s`}
                  </div>
                ) : (
                  <MessageBubble key={m.id} message={m} />
                )
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-ivory-3 bg-ivory/85 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl px-4 pb-3 pt-3">
          {filename && (
            <div className="mb-2 flex items-center justify-between gap-3 rounded-chip border border-ivory-3 bg-white px-3 py-1.5 text-sm text-ink">
              <div className="truncate">
                <span className="text-slate">Attached:</span>{" "}
                <span className="font-medium">{filename}</span>
              </div>
              <button
                className="grid h-6 w-6 place-items-center rounded-full text-slate hover:bg-ivory-2"
                onClick={clearFile}
                title="Remove file"
                aria-label="Remove attached file"
              >
                <FiX size={14} />
              </button>
            </div>
          )}

          <div className="flex items-end gap-2 rounded-2xl border border-ivory-3 bg-white p-1.5 shadow-soft transition-colors focus-within:border-gold/50">
            <label
              className="grid h-10 w-10 flex-none cursor-pointer place-items-center rounded-xl text-slate hover:bg-ivory-2 hover:text-ink"
              title="Attach a file"
              aria-label="Attach a file"
            >
              <FiPaperclip size={16} />
              <input className="hidden" type="file" onChange={onFileInput} />
            </label>

            <textarea
              ref={textRef}
              rows={1}
              placeholder="Ask about UK financial regulation…"
              className="max-h-60 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-ink outline-none placeholder:text-slate/70"
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
                className="grid h-10 w-10 flex-none place-items-center rounded-xl bg-danger/10 text-danger hover:bg-danger/15"
                onClick={stop}
                title="Stop generating"
                aria-label="Stop generating"
              >
                <FiSquare size={14} />
              </button>
            ) : (
              <button
                type="button"
                disabled={!canSend}
                className={[
                  "grid h-10 w-10 flex-none place-items-center rounded-xl transition-colors",
                  canSend
                    ? "bg-ink text-ivory hover:bg-ink-2"
                    : "cursor-not-allowed bg-ivory-2 text-slate",
                ].join(" ")}
                onClick={() => send()}
                title="Send"
                aria-label="Send"
              >
                <FiSend size={14} />
              </button>
            )}
          </div>
          <div className="mt-2 flex items-center justify-between gap-2 px-1">
            <DisclaimerBand variant="thin" />
            <span className="text-[11px] text-slate/70">
              Enter to send · Shift+Enter for newline
            </span>
          </div>
        </div>
      </div>

      {dragOver && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40">
          <div className="rounded-card border-2 border-dashed border-gold bg-ivory px-10 py-8 text-center font-display text-xl text-ink">
            Drop the file to attach
          </div>
        </div>
      )}
    </div>
  );
}
