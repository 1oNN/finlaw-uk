import { useState } from "react";
import { FiChevronLeft, FiChevronRight } from "react-icons/fi";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ChatSidebar from "../components/ChatSidebar";
import Chat from "../components/Chat";

const newId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export default function ChatPage() {
  const [open, setOpen] = useState(true);
  const [activeId, setActiveId] = useState(newId());

  const newChat = () => setActiveId(newId());

  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <Header />
      <div className="relative flex flex-1 overflow-hidden">
        {open && (
          <ChatSidebar
            selectedId={activeId}
            onSelect={setActiveId}
            onNewChat={newChat}
          />
        )}

        <button
          onClick={() => setOpen(!open)}
          className="absolute left-0 top-16 z-30 -translate-x-1/2 rounded-full bg-accent p-1.5 text-white shadow-chat"
          title={open ? "Hide sidebar" : "Show sidebar"}
        >
          {open ? <FiChevronLeft size={18} /> : <FiChevronRight size={18} />}
        </button>

        <main className="flex flex-1 flex-col">
          <Chat activeChatId={activeId} onChatCreated={setActiveId} />
        </main>
      </div>
      <Footer />
    </div>
  );
}
