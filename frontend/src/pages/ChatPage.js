import React, { useState } from "react";
import { FiChevronLeft, FiChevronRight, FiX } from "react-icons/fi";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ChatSidebar from "../components/ChatSidebar";
import Chat from "../components/Chat";
import SourcesPanel from "../components/SourcesPanel";
import DisclaimerModal from "../components/DisclaimerModal";

const newId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export default function ChatPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sourcesOpenMobile, setSourcesOpenMobile] = useState(false);
  const [activeId, setActiveId] = useState(newId());
  const [lastMeta, setLastMeta] = useState(null);
  const [lastMode, setLastMode] = useState("auto");

  const newChat = () => {
    setActiveId(newId());
    setLastMeta(null);
  };

  return (
    <div className="flex h-screen flex-col bg-paper text-ink">
      <Header variant="chat" />

      <div className="relative flex flex-1 overflow-hidden">
        {/* Left rail */}
        {sidebarOpen && (
          <ChatSidebar
            selectedId={activeId}
            onSelect={(id) => {
              setActiveId(id);
              setLastMeta(null);
            }}
            onNewChat={newChat}
            onClose={() => setSidebarOpen(false)}
          />
        )}

        <button
          onClick={() => setSidebarOpen((o) => !o)}
          className="absolute left-0 top-3 z-30 grid h-6 w-6 -translate-x-1/2 place-items-center rounded-full border border-[var(--rule-2)] bg-paper text-ink-soft hover:text-accent"
          title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
          aria-label={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
        >
          {sidebarOpen ? (
            <FiChevronLeft size={12} />
          ) : (
            <FiChevronRight size={12} />
          )}
        </button>

        {/* Center column */}
        <main
          className={[
            "flex min-w-0 flex-1 flex-col bg-paper",
            sidebarOpen ? "border-l border-[var(--rule)]" : "",
          ].join(" ")}
        >
          <Chat
            activeChatId={activeId}
            onChatCreated={setActiveId}
            onMetaUpdate={setLastMeta}
            onModeChange={setLastMode}
            onOpenSources={() => setSourcesOpenMobile(true)}
          />
        </main>

        {/* Right rail — desktop, footnotes column */}
        <div className="hidden w-[300px] flex-none lg:flex">
          <SourcesPanel meta={lastMeta} mode={lastMode} />
        </div>

        {/* Right rail — mobile drawer */}
        {sourcesOpenMobile && (
          <div className="fixed inset-0 z-40 flex lg:hidden">
            <button
              type="button"
              className="absolute inset-0 bg-ink/30"
              aria-label="Close footnotes panel"
              onClick={() => setSourcesOpenMobile(false)}
            />
            <div className="relative ml-auto flex h-full w-[320px] max-w-[85vw] flex-col bg-paper">
              <div className="flex items-center justify-between border-b border-[var(--rule)] px-4 py-2.5">
                <span className="smallcaps-fallback text-ink-mute">
                  Footnotes
                </span>
                <button
                  type="button"
                  className="grid h-8 w-8 place-items-center text-ink-soft hover:text-accent"
                  onClick={() => setSourcesOpenMobile(false)}
                  aria-label="Close"
                >
                  <FiX size={16} />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <SourcesPanel meta={lastMeta} mode={lastMode} />
              </div>
            </div>
          </div>
        )}
      </div>

      <Footer variant="compact" />
      <DisclaimerModal />
    </div>
  );
}
