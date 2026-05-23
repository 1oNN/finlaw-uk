import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import MessageBubble from "./MessageBubble";
import { FiSend } from "react-icons/fi";
import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:5000" });
api.interceptors.request.use((cfg) => {
  const tok = localStorage.getItem("access_token");
  if (tok) cfg.headers.Authorization = `Bearer ${tok}`;
  return cfg;
});

export default function ChatSimple() {
  const [messages, setMessages] = useState([]); // {role, type:'text', content}
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const location = useLocation();

  const histId = new URLSearchParams(location.search).get("history");

  useEffect(() => {
    if (!histId) return;
    api
      .get(`/api/chats/${histId}/messages`)
      .then((res) =>
        setMessages(
          res.data.map((m) => ({
            id: crypto.randomUUID(),
            role: m.role,
            type: "text",
            content: m.content,
          }))
        )
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

    // optimistic
    const userMsg = {
      id: crypto.randomUUID(),
      role: "user",
      type: "text",
      content: prompt,
    };
    const asstMsg = {
      id: crypto.randomUUID(),
      role: "assistant",
      type: "text",
      content: "",
    };
    setMessages((m) => [...m, userMsg, asstMsg]);
    const idx = (messages.length || 0) + 1;
    const token = localStorage.getItem("access_token");

    const resp = await fetch(
      `http://localhost:5000/api/chat/stream?prompt=${encodeURIComponent(prompt)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }
    );

    if (!resp.ok || !resp.body) {
      setMessages((m) =>
        m.map((msg, i) =>
          i === idx ? { ...msg, content: "❌ Error contacting backend." } : msg
        )
      );
      return;
    }

    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    while (true) {
      const { value, done } = await reader.read().catch(() => ({ done: true }));
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const p of parts) {
        if (p.startsWith("data: ")) {
          const tok = p.slice(6);
          setMessages((m) =>
            m.map((msg, i) =>
              i === idx ? { ...msg, content: (msg.content || "") + tok } : msg
            )
          );
        }
      }
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 bg-bg py-6">
        <div className="mx-auto w-full max-w-chat space-y-2 px-4">
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <form
        onSubmit={send}
        className="sticky bottom-0 z-10 border-t border-white/15 bg-panel/95 px-4 pb-3 pt-2 backdrop-blur"
      >
        <div className="mx-auto flex w-full max-w-chat items-end gap-2">
          <textarea
            rows={1}
            placeholder="Send a message…"
            className="max-h-60 min-h-[46px] flex-1 resize-none rounded-2xl border border-white/15 bg-surface/90 px-4 py-3 text-white shadow-chat outline-none placeholder:text-muted"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="grid h-11 w-11 place-items-center rounded-xl border border-accent bg-accent text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
            title="Send"
          >
            <FiSend size={18} />
          </button>
        </div>
      </form>
    </div>
  );
}
