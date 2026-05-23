import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import MessageBubble from "./MessageBubble";
import { FiSend } from "react-icons/fi";
import axios from "axios";

/* helper for JSON/history calls */
const api = axios.create({ baseURL: "http://localhost:5000" });
api.interceptors.request.use((cfg) => {
  const tok = localStorage.getItem("access_token");
  if (tok) cfg.headers.Authorization = `Bearer ${tok}`;
  return cfg;
});

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const location = useLocation();

  /* load history if ?history=ID */
  const histId = new URLSearchParams(location.search).get("history");
  useEffect(() => {
    if (!histId) return;
    api
      .get(`/api/chats/${histId}/messages`)
      .then((res) =>
        setMessages(res.data.map((m) => ({ role: m.role, content: m.content })))
      )
      .catch(console.error);
  }, [histId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e) {
    e.preventDefault();
    const prompt = input.trim();
    if (!prompt) return;
    setInput("");

    /* optimistic UI */
    setMessages((m) => [
      ...m,
      { role: "user", content: prompt },
      { role: "assistant", content: "", streaming: true },
    ]);
    const idx = messages.length + 1;
    const token = localStorage.getItem("access_token");

    /* stream */
    const resp = await fetch(
      `http://localhost:5000/api/chat/stream?prompt=${encodeURIComponent(
        prompt
      )}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!resp.ok) {
      setMessages((m) =>
        m.map((msg, i) =>
          i === idx ? { ...msg, streaming: false, content: "❌ Error" } : msg
        )
      );
      return;
    }
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n"); // SSE frames
      buf = parts.pop();
      for (const p of parts) {
        if (p.startsWith("data: ")) {
          const tok = p.slice(6);
          setMessages((m) =>
            m.map((msg, i) =>
              i === idx ? { ...msg, content: msg.content + tok } : msg
            )
          );
        } else if (p.startsWith("event: done")) {
          reader.cancel();
        }
      }
    }
    setMessages((m) =>
      m.map((msg, i) => (i === idx ? { ...msg, streaming: false } : msg))
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto space-y-4 p-6 bg-panel">
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role}>
            {m.content}
            {m.streaming && <span className="animate-pulse">▍</span>}
          </MessageBubble>
        ))}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={send}
        className="border-t border-border bg-panel/40 backdrop-blur p-4 flex gap-3"
      >
        <textarea
          rows={1}
          placeholder="Send a message…"
          className="flex-1 resize-none rounded-lg bg-surface/60 backdrop-blur
                     border border-border px-4 py-3 text-sm focus:outline-none
                     focus:ring-2 focus:ring-accent placeholder-gray-500"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          disabled={!input.trim()}
          className="w-12 h-12 grid place-content-center rounded-lg bg-accent
                     hover:bg-accent-hover disabled:opacity-40 transition-colors"
        >
          <FiSend size={18} />
        </button>
      </form>
    </div>
  );
}
