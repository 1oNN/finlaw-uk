/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        // --- Editorial palette (new semantic names) -------------------
        // Warm off-white paper, near-black ink, deep oxblood accent.
        // One accent only — no gradients, no secondary brand color.
        paper: {
          DEFAULT: "#FAF8F3",
          2: "#F4EFE5",
        },
        accent: {
          DEFAULT: "#722F37",
          2: "#5A252C",
          soft: "#E9D8DA",
        },
        rule: {
          DEFAULT: "#E8E5DE",     // hairline border on paper
          2: "#D6D2C8",           // stronger separator
        },
        mute: "#F0EBE0",

        // --- Legacy token names, REMAPPED to editorial palette --------
        // Old class names (bg-ivory, text-ink, text-gold, etc.) used in
        // pages we haven't refactored yet (Home, Login, Signup, Eval)
        // pick up the new colors automatically. The numeric meaning is
        // preserved (ivory = the page surface, ink = the body text,
        // gold = the accent), only the hex values change.
        ink: {
          DEFAULT: "#1A1A1A",
          2: "#2A2A2A",
          soft: "#4A4A4A",
        },
        ivory: {
          DEFAULT: "#FAF8F3",
          2: "#F4EFE5",
          3: "#E8E5DE",
        },
        gold: {
          DEFAULT: "#722F37",
          2: "#5A252C",
          soft: "#E9D8DA",
        },
        slate: {
          DEFAULT: "#4A4A4A",
          2: "#767676",
        },
        mist: "#D8D8D8",
        verified: "#2F7A4F",
        caution: "#B07A1F",
        danger: "#A33A2A",

        // Legacy alias bag — kept compiling, redirected to editorial
        bg: "#FAF8F3",
        panel: "#FFFFFF",
        surface: "#F4EFE5",
        border: "#E8E5DE",
        text: "#1A1A1A",
        muted: "#4A4A4A",

        // Traffic-light review colors — UNCHANGED. The Green/Yellow/
        // Amber/Red sections in MessageBubble depend on these exact
        // tokens, and the four-category review is part of the product.
        risk: {
          green: "#4A8A6B",
          yellow: "#C7A04A",
          amber: "#B57536",
          red: "#B5453E",
        },
      },
      fontFamily: {
        // Editorial serif for display / headings.
        display: ['"Source Serif 4"', 'Newsreader', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      maxWidth: {
        chat: "760px",
        prose: "68ch",
      },
      borderRadius: {
        card: "6px",
        bubble: "4px",
        chip: "999px",
      },
      boxShadow: {
        // Light hairline shadow only — no bubble blur, no chat-product glow.
        soft: "0 1px 0 rgba(0,0,0,0.04)",
        chat: "0 1px 0 rgba(0,0,0,0.04)",
        ring: "0 0 0 2px rgba(114,47,55,0.25)",
      },
      letterSpacing: {
        tightish: "-0.01em",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(2px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in .15s ease-out both",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
