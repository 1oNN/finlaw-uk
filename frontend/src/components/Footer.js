import React from "react";
import { Link, useLocation } from "react-router-dom";
import Logo from "./Logo";

export default function Footer({ variant = "default" }) {
  const year = new Date().getFullYear();
  const { pathname } = useLocation();
  const compact = variant === "compact" || pathname.startsWith("/chat");

  if (compact) {
    return (
      <footer className="border-t border-ivory-3 bg-ivory">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 text-xs text-slate">
          <span>
            FinLaw is a research tool. Not legal advice.
          </span>
          <span className="hidden sm:inline">
            © {year} FinLaw — UK financial regulation, cited.
          </span>
        </div>
      </footer>
    );
  }

  return (
    <footer className="border-t border-ivory-3 bg-ivory">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-3">
        <div className="space-y-3">
          <Logo variant="wordmark" size="md" />
          <p className="max-w-xs text-sm text-slate">
            A graph-grounded research assistant for UK financial regulation.
            Every claim linked to its source.
          </p>
        </div>

        <div className="text-sm">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate">
            Product
          </div>
          <ul className="space-y-2">
            <li>
              <Link to="/chat" className="text-ink hover:text-gold-2">
                Open the chat
              </Link>
            </li>
            <li>
              <Link to="/eval" className="text-ink hover:text-gold-2">
                Evaluation
              </Link>
            </li>
            <li>
              <Link to="/login" className="text-ink hover:text-gold-2">
                Sign in
              </Link>
            </li>
          </ul>
        </div>

        <div className="text-sm">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate">
            About
          </div>
          <p className="text-sm text-slate">
            MSc dissertation project — University of Bradford. The retrieval
            pipeline, knowledge graph, and evaluation harness are
            reproducible from this codebase.
          </p>
        </div>
      </div>

      <div className="border-t border-ivory-3">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-2 px-4 py-5 text-xs text-slate sm:flex-row sm:items-center sm:px-6">
          <span>
            © {year} FinLaw. Information provided is for educational
            purposes only and does not constitute legal advice.
          </span>
          <span>Built on FSMA · FCA · PRA · MLR · PSR · UK MAR</span>
        </div>
      </div>
    </footer>
  );
}
