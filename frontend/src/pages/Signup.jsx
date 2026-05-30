import React, { useState, useContext } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FiArrowRight, FiAlertCircle, FiLoader } from "react-icons/fi";
import { AuthContext } from "../components/AuthContext";
import Wordmark from "../components/Wordmark";
import DisclaimerBand from "../components/DisclaimerBand";

const API_BASE = "http://localhost:5000";

export default function Signup() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const { setLoggedIn } = useContext(AuthContext);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/signup`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        await fetch(`${API_BASE}/login`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        setLoggedIn(true);
        navigate("/chat");
      } else {
        const { error } = await res.json().catch(() => ({}));
        setError(error || "Sign-up failed.");
      }
    } catch (err) {
      setError("Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-paper text-ink">
      <main className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="w-full max-w-md">
          <Link to="/" className="mb-8 inline-flex">
            <Wordmark size="lg" />
          </Link>

          <div className="rounded-card border border-[var(--rule-2)] bg-paper p-7 shadow-soft">
            <h1 className="font-display text-2xl font-semibold tracking-tightish">
              Create your account
            </h1>
            <p className="mt-1 text-sm text-slate">
              Save chats and pick up where you left off.
            </p>

            {error && (
              <div className="mt-4 flex items-start gap-2 rounded-[4px] border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
                <FiAlertCircle className="mt-0.5 flex-none" size={14} />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={submit} className="mt-5 space-y-4">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-slate">
                  Email
                </span>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-[4px] border border-[var(--rule-2)] bg-paper-2/40 px-3 py-2.5 text-sm text-ink outline-none transition-colors focus:border-accent focus:bg-paper"
                  placeholder="you@example.com"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-slate">
                  Password
                </span>
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-[4px] border border-[var(--rule-2)] bg-paper-2/40 px-3 py-2.5 text-sm text-ink outline-none transition-colors focus:border-accent focus:bg-paper"
                  placeholder="At least 8 characters"
                />
              </label>
              <button
                type="submit"
                disabled={submitting}
                className="group inline-flex w-full items-center justify-center gap-2 rounded-[4px] bg-ink px-4 py-2.5 text-sm font-medium text-paper shadow-soft transition-colors hover:bg-ink-2 disabled:opacity-60"
              >
                {submitting ? "Creating…" : "Create account"}
                {submitting ? (
                  <FiLoader size={14} className="animate-spin" />
                ) : (
                  <FiArrowRight
                    size={14}
                    className="transition-transform group-hover:translate-x-0.5"
                  />
                )}
              </button>
            </form>

            <p className="mt-5 text-center text-sm text-slate">
              Already have an account?{" "}
              <Link
                to="/login"
                className="border-b border-accent/50 text-ink hover:border-accent"
              >
                Sign in
              </Link>
            </p>
          </div>

          <p className="mt-6 text-center text-xs text-slate">
            <Link to="/" className="hover:text-ink">
              ← Back to home
            </Link>
          </p>
        </div>
      </main>
      <DisclaimerBand />
    </div>
  );
}
