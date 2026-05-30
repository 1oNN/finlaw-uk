import React, { useContext, useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { FiArrowRight, FiMenu, FiX } from "react-icons/fi";
import { AuthContext } from "./AuthContext";

function navClass({ isActive }) {
  return [
    "px-1 py-2 text-[0.86rem] font-medium tracking-wide transition-colors",
    isActive ? "text-ink" : "text-ink-soft hover:text-accent",
  ].join(" ");
}

// Typographic mark — a pilcrow in the accent color paired with the
// FinLaw-UK wordmark in editorial serif. Replaces the SVG logo for the
// chrome of the chat experience.
function PilcrowWordmark({ size = "md" }) {
  const big = size === "lg";
  return (
    <span className="inline-flex items-baseline gap-2">
      <span
        aria-hidden
        className="font-display leading-none text-accent"
        style={{ fontSize: big ? "1.8rem" : "1.4rem" }}
      >
        ¶
      </span>
      <span
        className="font-display font-semibold tracking-tightish text-ink"
        style={{ fontSize: big ? "1.2rem" : "1.05rem" }}
      >
        FinLaw-UK
      </span>
    </span>
  );
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
        "sticky top-0 z-40 bg-paper",
        scrolled || onChatPage
          ? "border-b border-[var(--rule)]"
          : "border-b border-transparent",
      ].join(" ")}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-5 sm:px-7">
        <Link to="/" className="group inline-flex items-baseline" aria-label="FinLaw-UK home">
          <PilcrowWordmark size="md" />
          <span className="smallcaps-fallback ml-3 hidden text-ink-mute md:inline">
            UK financial regulation, cited
          </span>
        </Link>

        <nav className="hidden items-baseline gap-5 md:flex">
          <NavLink to="/" end className={navClass}>
            Home
          </NavLink>
          <NavLink to="/chat" className={navClass}>
            Research
          </NavLink>
          <NavLink to="/eval" className={navClass}>
            Evaluation
          </NavLink>
        </nav>

        <div className="hidden items-baseline gap-4 md:flex">
          {!loggedIn ? (
            <>
              <Link
                to="/login"
                className="text-[0.86rem] font-medium text-ink-soft hover:text-accent"
              >
                Sign in
              </Link>
              <Link
                to="/chat"
                className="group inline-flex items-center gap-1.5 bg-ink px-3.5 py-1.5 text-[0.84rem] font-medium tracking-wide text-paper transition-colors hover:bg-accent"
              >
                Open the research tool
                <FiArrowRight
                  className="transition-transform group-hover:translate-x-0.5"
                  size={13}
                />
              </Link>
            </>
          ) : (
            <>
              <Link
                to="/chat"
                className="group inline-flex items-center gap-1.5 bg-ink px-3.5 py-1.5 text-[0.84rem] font-medium tracking-wide text-paper transition-colors hover:bg-accent"
              >
                Open the research tool
                <FiArrowRight size={13} />
              </Link>
              <button
                onClick={logout}
                className="text-[0.86rem] font-medium text-ink-soft hover:text-accent"
              >
                Sign out
              </button>
            </>
          )}
        </div>

        <button
          type="button"
          className="grid h-10 w-10 place-items-center text-ink md:hidden"
          aria-label="Open menu"
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <FiX size={20} /> : <FiMenu size={20} />}
        </button>
      </div>

      {open && (
        <div className="border-t border-[var(--rule)] bg-paper md:hidden">
          <div className="mx-auto flex max-w-7xl flex-col gap-1 px-5 py-3">
            <NavLink to="/" end className={navClass} onClick={() => setOpen(false)}>
              Home
            </NavLink>
            <NavLink to="/chat" className={navClass} onClick={() => setOpen(false)}>
              Research
            </NavLink>
            <NavLink to="/eval" className={navClass} onClick={() => setOpen(false)}>
              Evaluation
            </NavLink>
            <div className="mt-2 flex flex-col gap-2 border-t border-[var(--rule)] pt-3">
              {!loggedIn ? (
                <>
                  <Link
                    to="/login"
                    className="px-1 py-2 text-[0.86rem] font-medium text-ink-soft hover:text-accent"
                    onClick={() => setOpen(false)}
                  >
                    Sign in
                  </Link>
                  <Link
                    to="/chat"
                    className="inline-flex items-center justify-center gap-1.5 bg-ink px-3.5 py-2 text-[0.84rem] font-medium tracking-wide text-paper hover:bg-accent"
                    onClick={() => setOpen(false)}
                  >
                    Open the research tool <FiArrowRight size={13} />
                  </Link>
                </>
              ) : (
                <button
                  onClick={() => {
                    logout();
                    setOpen(false);
                  }}
                  className="px-1 py-2 text-left text-[0.86rem] font-medium text-ink-soft hover:text-accent"
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
