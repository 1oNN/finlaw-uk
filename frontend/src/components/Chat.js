import { useState, useRef, useEffect, useCallback } from "react";
import MessageBubble from "./MessageBubble";
import { FiSend, FiUpload, FiSquare, FiX } from "react-icons/fi";

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

export default function Chat({ activeChatId, onChatCreated }) {
  const [chatId] = useState(activeChatId || uid());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setStreaming] = useState(false);
  const [abortCtrl, setAbortCtrl] = useState(null);

  const [filename, setFilename] = useState("");
  // Multi-model selection was dropped — backend hardcodes Mistral via OLLAMA_MODEL.
  const model = "mistral:7b-instruct";
  const [mode, setMode] = useState("auto");
  const [status, setStatus] = useState("");

  const [dragOver, setDragOver] = useState(false);
  const bottomRef = useRef(null);
  const textRef = useRef(null);
  const token = localStorage.getItem("access_token");

  useEffect(() => setMessages(loadChatMessages(chatId)), [chatId]);
  useEffect(
    () => bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
    [messages, isStreaming]
  );
  useEffect(() => safeSaveMessages(chatId, messages), [chatId, messages]);

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
    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body,
      });
      if (!res.ok) throw new Error("Upload failed");
      const { filename: fn } = await res.json();
      setFilename(fn);
      setStatus(`Attached ${fn}`);
      setTimeout(() => setStatus(""), 1200);

      setMessages((m) => [
        ...m,
        {
          id: uid(),
          role: "user",
          type: "attachment",
          content: "",
          attachment: { name: file.name, type: file.type, size: file.size },
        },
      ]);
    } catch {
      setStatus("Upload failed.");
    }
  }
  const onFileInput = (e) => {
    const f = e.target.files?.[0];
    if (f) uploadFile(f);
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

  async function send(e) {
    e?.preventDefault();
    const prompt = input.trim();
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
    setInput("");
    autogrow();
    setStreaming(true);
    setStatus("");

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
        body: JSON.stringify({ prompt, filename, mode, model }),
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
        copy[idx] = { ...copy[idx], content: "❌ Error contacting backend." };
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
          setMeta(j.thought_ms ?? j.thoughtMs ?? 0);
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
        const parts = buf.split(/\r?\n\r?\n/); // CRLF or LF
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

  return (
    <div
      className="flex h-full flex-col"
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragLeave={onDragLeave}
    >
      {/* Top controls */}
      <div className="sticky top-0 z-20 border-b border-white/15 bg-panel/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-chat items-center justify-between px-4 py-2">
          <div className="flex items-center gap-2">
            <select
              className="rounded-lg border border-white/15 bg-surface/90 px-2 py-1 text-sm text-white"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              disabled={isStreaming}
              title="Mode"
            >
              <option value="auto">auto</option>
              <option value="general">general</option>
              <option value="finance">finance review</option>
              <option value="traffic-light">traffic-light</option>
            </select>

            {isStreaming && (
              <span className="ml-1 animate-pulse text-xs text-muted">
                thinking…
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {status && (
              <div className="rounded-full border border-white/15 bg-surface/80 px-2 py-1 text-xs text-white">
                {status}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 bg-bg py-6">
        {messages.length === 0 ? (
          <div className="mx-auto max-w-chat px-4 py-10 text-center text-white/90">
            <div className="text-3xl opacity-80">💼</div>
            <div className="mt-2 font-extrabold">
              Ask anything about UK finance and law
            </div>
          </div>
        ) : null}

        {messages.map((m) =>
          m.role === "meta" ? (
            <div
              key={m.id}
              className="mx-auto max-w-chat px-4 text-xs text-muted"
            >
              {m.thoughtMs == null
                ? "💡 Thinking…"
                : `💡 Thought for ${(m.thoughtMs / 1000).toFixed(1)}s`}
            </div>
          ) : (
            <MessageBubble key={m.id} message={m} />
          )
        )}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="sticky bottom-0 z-10 border-t border-white/15 bg-panel/95 pb-3 pt-2 backdrop-blur">
        <div className="mx-auto w-full max-w-chat px-4">
          {filename && (
            <div className="mb-2 flex items-center justify-between gap-3 rounded-full border border-white/15 bg-surface/80 px-3 py-1.5 text-sm text-white">
              <div className="truncate">
                <span className="font-semibold">Attached:</span>{" "}
                <span className="truncate">{filename}</span>
              </div>
              <button
                className="grid h-7 w-7 place-items-center rounded-full border border-white/15 text-white/90 hover:bg-white/10"
                onClick={clearFile}
                title="Remove file"
              >
                <FiX />
              </button>
            </div>
          )}

          <div className="flex items-end gap-2">
            <label
              className="grid h-11 w-11 cursor-pointer place-items-center rounded-xl border border-white/15 bg-surface/80 text-white hover:bg-surface"
              title="Attach a file"
            >
              <FiUpload />
              <input className="hidden" type="file" onChange={onFileInput} />
            </label>

            <textarea
              ref={textRef}
              rows={1}
              placeholder="Ask about UK finance law, or anything else"
              className="max-h-60 min-h-[46px] flex-1 resize-none rounded-2xl border border-white/15 bg-surface/90 px-4 py-3 text-white shadow-chat outline-none placeholder:text-muted"
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
                className="grid h-11 w-11 place-items-center rounded-xl border border-red-400/60 bg-red-500/10 text-red-300 hover:bg-red-500/20"
                onClick={stop}
                title="Stop generating"
              >
                <FiSquare />
              </button>
            ) : (
              <button
                type="button"
                disabled={!canSend}
                className={`grid h-11 w-11 place-items-center rounded-xl border text-white transition ${
                  canSend
                    ? "border-accent bg-accent hover:bg-accent-hover"
                    : "cursor-not-allowed border-white/15 bg-surface/70 opacity-60"
                }`}
                onClick={send}
                title="Send"
              >
                <FiSend />
              </button>
            )}
          </div>
        </div>
      </div>

      {dragOver && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/70 text-2xl font-extrabold text-white">
          Drop file to attach
        </div>
      )}
    </div>
  );
}
