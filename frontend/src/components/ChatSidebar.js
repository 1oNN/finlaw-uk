import { useEffect, useState } from "react";
import { FiPlus, FiTrash2, FiMessageSquare } from "react-icons/fi";

const CHAT_LIST_KEY = "flgpt:chats";
const loadChats = () => {
  try {
    return JSON.parse(localStorage.getItem(CHAT_LIST_KEY) || "[]");
  } catch {
    return [];
  }
};
const saveChats = (list) =>
  localStorage.setItem(CHAT_LIST_KEY, JSON.stringify(list));

export default function ChatSidebar({ selectedId, onSelect, onNewChat }) {
  const [chats, setChats] = useState(loadChats());

  useEffect(() => {
    const i = setInterval(() => setChats(loadChats()), 500);
    return () => clearInterval(i);
  }, []);

  const remove = (id) => {
    const next = loadChats().filter((c) => c.id !== id);
    saveChats(next);
    setChats(next);
    if (id === selectedId && next.length) onSelect?.(next[0].id);
  };

  return (
    <aside className="flex h-full w-[270px] flex-col border-r border-white/15 bg-panel">
      <div className="p-3">
        <button
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/15 bg-surface px-3 py-2 text-white hover:bg-surface/80"
          onClick={onNewChat}
          title="New chat"
        >
          <FiPlus /> New chat
        </button>
      </div>

      <div className="flex-1 overflow-auto p-2">
        {chats.length === 0 ? (
          <div className="px-2 text-sm text-muted">No saved chats yet.</div>
        ) : (
          <div className="space-y-2">
            {chats.map((c) => {
              const active = selectedId === c.id;
              return (
                <div
                  key={c.id}
                  className={`group flex items-center gap-2 rounded-lg border px-2 py-1.5 ${
                    active
                      ? "border-accent bg-surface ring-1 ring-accent/40"
                      : "border-white/15 bg-surface/60 hover:bg-surface/80"
                  }`}
                >
                  <button
                    className="flex min-w-0 flex-1 items-center gap-2 text-left text-white"
                    onClick={() => onSelect?.(c.id)}
                    title={c.title}
                  >
                    <span className="grid h-6 w-6 flex-none place-items-center rounded-md bg-panel text-white/90">
                      <FiMessageSquare size={14} />
                    </span>
                    <span className="truncate">{c.title}</span>
                  </button>
                  <button
                    className="grid h-8 w-8 flex-none place-items-center rounded-md border border-white/15 text-white/90 hover:bg-white/10"
                    onClick={() => remove(c.id)}
                    title="Delete chat"
                  >
                    <FiTrash2 />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
