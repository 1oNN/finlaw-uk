import React, { useContext, useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { FiArrowRight, FiMenu, FiX } from "react-icons/fi";
import { AuthContext } from "./AuthContext";
import Logo from "./Logo";

function navClass({ isActive }) {
  return [
    "px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "text-ink"
      : "text-slate hover:text-ink",
  ].join(" ");
}

export default function Header({ variant = "default" }) {
  const { loggedIn, logout } = useContext(AuthContext);
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const onChatPage = variant === "chat";

  return (
    <header
      className={[
        "sticky top-0 z-40 backdrop-blur",
        "bg-ivory/85 supports-[backdrop-filter]:bg-ivory/70",
        scrolled || onChatPage
          ? "border-b border-ivory-3"
          : "border-b border-transparent",
      ].join(" ")}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6">
        <Link
          to="/"
          className="group inline-flex items-center"
          aria-label="FinLaw home"
        >
          <Logo variant="wordmark" size="md" />
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          <NavLink to="/" end className={navClass}>
            Home
          </NavLink>
          <NavLink to="/chat" className={navClass}>
            Chat
          </NavLink>
          <NavLink to="/eval" className={navClass}>
            Evaluation
          </NavLink>
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          {!loggedIn ? (
            <>
              <Link
                to="/login"
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate hover:text-ink"
              >
                Sign in
              </Link>
              <Link
                to="/chat"
                className="group inline-flex items-center gap-1.5 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-ivory shadow-soft transition-colors hover:bg-ink-2"
              >
                Open the chat
                <FiArrowRight
                  className="transition-transform group-hover:translate-x-0.5"
                  size={14}
                />
              </Link>
            </>
          ) : (
            <>
              <Link
                to="/chat"
                className="group inline-flex items-center gap-1.5 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-ivory shadow-soft hover:bg-ink-2"
              >
                Open the chat
                <FiArrowRight size={14} />
              </Link>
              <button
                onClick={logout}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate hover:text-ink"
              >
                Sign out
              </button>
            </>
          )}
        </div>

        <button
          type="button"
          className="grid h-10 w-10 place-items-center rounded-lg text-ink md:hidden"
          aria-label="Open menu"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <FiX size={20} /> : <FiMenu size={20} />}
        </button>
      </div>

      {open && (
        <div className="border-t border-ivory-3 bg-ivory md:hidden">
          <div className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-3">
            <NavLink to="/" end className={navClass} onClick={() => setOpen(false)}>
              Home
            </NavLink>
            <NavLink to="/chat" className={navClass} onClick={() => setOpen(false)}>
              Chat
            </NavLink>
            <NavLink to="/eval" className={navClass} onClick={() => setOpen(false)}>
              Evaluation
            </NavLink>
            <div className="mt-2 flex flex-col gap-2 border-t border-ivory-3 pt-3">
              {!loggedIn ? (
                <>
                  <Link
                    to="/login"
                    className="rounded-lg px-3 py-2 text-sm font-medium text-slate hover:text-ink"
                    onClick={() => setOpen(false)}
                  >
                    Sign in
                  </Link>
                  <Link
                    to="/chat"
                    className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-ivory"
                    onClick={() => setOpen(false)}
                  >
                    Open the chat <FiArrowRight size={14} />
                  </Link>
                </>
              ) : (
                <button
                  onClick={() => {
                    logout();
                    setOpen(false);
                  }}
                  className="rounded-lg px-3 py-2 text-sm font-medium text-slate hover:text-ink"
                >
                  Sign out
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
