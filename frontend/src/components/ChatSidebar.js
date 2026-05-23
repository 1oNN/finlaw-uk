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
    <aside className="hidden h-full w-[260px] flex-col border-r border-ivory-3 bg-ivory/60 md:flex">
      <div className="border-b border-ivory-3 p-3">
        <button
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-3 py-2 text-sm font-medium text-ivory shadow-soft transition-colors hover:bg-ink-2"
          onClick={onNewChat}
          title="New chat"
        >
          <FiPlus size={14} /> New chat
        </button>
      </div>

      <div className="border-b border-ivory-3 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.15em] text-slate">
        Recent
      </div>

      <div className="flex-1 overflow-auto p-2">
        {chats.length === 0 ? (
          <div className="px-2 py-3 text-xs text-slate">
            No saved chats yet.
          </div>
        ) : (
          <ul className="space-y-1">
            {chats.map((c) => {
              const active = selectedId === c.id;
              return (
                <li
                  key={c.id}
                  className={[
                    "group flex items-center gap-1 rounded-md transition-colors",
                    active
                      ? "bg-white shadow-soft"
                      : "hover:bg-ivory-2",
                  ].join(" ")}
                >
                  <button
                    className="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-2 text-left text-sm"
                    onClick={() => onSelect?.(c.id)}
                    title={c.title}
                  >
                    <span
                      className={[
                        "grid h-6 w-6 flex-none place-items-center rounded-md",
                        active
                          ? "bg-gold-soft text-gold-2"
                          : "bg-ivory-2 text-slate",
                      ].join(" ")}
                    >
                      <FiMessageSquare size={12} />
                    </span>
                    <span
                      className={[
                        "truncate",
                        active ? "text-ink" : "text-ink/85",
                      ].join(" ")}
                    >
                      {c.title}
                    </span>
                  </button>
                  <button
                    className="mr-1 grid h-7 w-7 flex-none place-items-center rounded-md text-slate opacity-0 transition-opacity hover:bg-ivory-2 hover:text-danger group-hover:opacity-100"
                    onClick={() => remove(c.id)}
                    title="Delete chat"
                    aria-label="Delete chat"
                  >
                    <FiTrash2 size={13} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
