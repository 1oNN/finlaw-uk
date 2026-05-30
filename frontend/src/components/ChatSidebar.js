import { useEffect, useState } from "react";
import { FiPlus, FiTrash2 } from "react-icons/fi";

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

// Group chats into "Today" / "Yesterday" / "Earlier" buckets so the
// list reads as a typeset index, not a stack of identical rows.
function bucket(ts) {
  if (!ts) return "Earlier";
  const d = new Date(ts);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return "Today";
  const yest = new Date(now);
  yest.setDate(now.getDate() - 1);
  if (d.toDateString() === yest.toDateString()) return "Yesterday";
  const weekAgo = new Date(now);
  weekAgo.setDate(now.getDate() - 7);
  if (d > weekAgo) return "Earlier this week";
  return "Earlier";
}

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

  // Bucket the list while preserving order within each bucket.
  const groups = [];
  const byBucket = new Map();
  for (const c of chats) {
    const b = bucket(c.createdAt);
    if (!byBucket.has(b)) {
      byBucket.set(b, []);
      groups.push(b);
    }
    byBucket.get(b).push(c);
  }

  return (
    <aside className="hidden h-full w-[244px] flex-col bg-paper md:flex">
      <div className="px-5 pt-5">
        <button
          className="inline-flex items-center gap-1.5 text-sm font-medium text-ink transition-colors hover:text-accent"
          onClick={onNewChat}
          title="New research"
        >
          <FiPlus size={14} aria-hidden /> New research
        </button>
      </div>

      <div className="smallcaps-fallback px-5 pt-7 text-ink-mute">
        Recent
      </div>

      <div className="mt-1 flex-1 overflow-auto px-5 pb-5">
        {chats.length === 0 ? (
          <div className="pt-3 text-[0.86rem] italic text-ink-mute">
            Nothing yet — your previous questions will list here.
          </div>
        ) : (
          groups.map((g) => (
            <section key={g} className="pt-4">
              <div
                className="pb-1 text-[0.7rem] uppercase tracking-[0.08em] text-ink-mute"
              >
                {g}
              </div>
              <ul className="m-0 list-none p-0">
                {byBucket.get(g).map((c, i) => {
                  const active = selectedId === c.id;
                  return (
                    <li
                      key={c.id}
                      className={[
                        "group flex items-baseline gap-2",
                        i === 0
                          ? "border-t-0"
                          : "border-t border-[var(--rule)]",
                      ].join(" ")}
                    >
                      <button
                        type="button"
                        onClick={() => onSelect?.(c.id)}
                        className={[
                          "min-w-0 flex-1 truncate py-2 pr-2 text-left text-[0.92rem] leading-snug transition-colors",
                          active
                            ? "text-ink"
                            : "text-ink-soft hover:text-accent",
                        ].join(" ")}
                        title={c.title}
                        aria-current={active ? "page" : undefined}
                      >
                        {active && (
                          <span
                            aria-hidden
                            className="mr-1.5 inline-block h-1 w-1 -translate-y-[1px] rounded-full bg-accent align-middle"
                          />
                        )}
                        {c.title}
                      </button>
                      <button
                        type="button"
                        onClick={() => remove(c.id)}
                        className="flex-none py-2 text-ink-mute opacity-0 transition-opacity hover:text-accent group-hover:opacity-100"
                        title="Delete"
                        aria-label="Delete research item"
                      >
                        <FiTrash2 size={12} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}
      </div>
    </aside>
  );
}
