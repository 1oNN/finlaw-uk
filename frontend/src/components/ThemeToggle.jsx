import React, { useCallback, useEffect, useState } from "react";
import { FiSun, FiMoon } from "react-icons/fi";

// "theme" in localStorage is the user's explicit choice ('light' | 'dark').
// When it's absent we follow the OS setting. The pre-paint <script> in
// public/index.html applies the right class before React mounts (no flash);
// this hook just keeps React in sync and handles toggling + live OS changes.
const STORAGE_KEY = "theme";

const isDarkNow = () =>
  typeof document !== "undefined" &&
  document.documentElement.classList.contains("dark");

export function useTheme() {
  const [dark, setDark] = useState(isDarkNow);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e) => {
      // Only track the OS while the user hasn't pinned a choice.
      if (!localStorage.getItem(STORAGE_KEY)) {
        document.documentElement.classList.toggle("dark", e.matches);
        setDark(e.matches);
      }
    };
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    const next = !isDarkNow();
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "dark" : "light");
    } catch (e) {
      /* private mode — fine, just don't persist */
    }
    setDark(next);
  }, []);

  return { dark, toggle };
}

export default function ThemeToggle({ className = "" }) {
  const { dark, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
      className={[
        "grid h-9 w-9 place-items-center rounded-[4px] text-ink-soft",
        "transition-colors hover:text-accent hover:bg-paper-2",
        className,
      ].join(" ")}
    >
      {dark ? <FiSun size={17} aria-hidden /> : <FiMoon size={16} aria-hidden />}
    </button>
  );
}
