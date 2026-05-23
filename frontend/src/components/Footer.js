import { Link, useLocation } from "react-router-dom";

export default function Footer() {
  const token = localStorage.getItem("access_token");
  const year = new Date().getFullYear();
  const { pathname } = useLocation();

  // Compact footer on chat page
  const compact = pathname.startsWith("/chat");

  return (
    <footer className="border-t border-white/15 bg-panel text-center text-sm text-muted">
      <div className="mx-auto flex w-full max-w-chat flex-col items-center px-4 py-4">
        {!token && !compact && (
          <div className="mb-2 space-x-3">
            <Link to="/login" className="underline">
              Login
            </Link>
            <Link to="/signup" className="underline">
              Sign Up
            </Link>
          </div>
        )}
        <div>© {year}. All rights reserved.</div>
      </div>
    </footer>
  );
}
