/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  // Theme is driven by CSS variables (see src/styles/globals.css). Toggling the
  // `dark` class on <html> flips every token below at once.
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // --- Palette: "navy minimal" -------------------------------------
        // Every token reads an RGB channel triplet from a CSS var, so the
        // class works in both themes AND supports opacity (bg-ink/30, etc.).
        // Borders are full colors because components use border-[var(--rule*)].
        paper: {
          DEFAULT: "rgb(var(--paper) / <alpha-value>)",
          2: "rgb(var(--paper-2) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          2: "rgb(var(--accent-2) / <alpha-value>)",
          soft: "rgb(var(--accent-soft) / <alpha-value>)",
        },
        rule: {
          DEFAULT: "var(--rule)",     // hairline border
          2: "var(--rule-2)",         // stronger separator
        },
        mute: "rgb(var(--mute) / <alpha-value>)",
        scrim: "rgb(var(--scrim) / <alpha-value>)",

        // --- Legacy token names, remapped to the same vars ----------------
        // Old class names (bg-ivory, text-gold, text-slate, …) used across
        // the app keep working and now flip with the theme automatically.
        ink: {
          DEFAULT: "rgb(var(--ink) / <alpha-value>)",
          2: "rgb(var(--ink-2) / <alpha-value>)",
          soft: "rgb(var(--ink-soft) / <alpha-value>)",
          mute: "rgb(var(--ink-mute) / <alpha-value>)",
        },
        ivory: {
          DEFAULT: "rgb(var(--paper) / <alpha-value>)",
          2: "rgb(var(--paper-2) / <alpha-value>)",
          3: "var(--rule)",
        },
        gold: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          2: "rgb(var(--accent-2) / <alpha-value>)",
          soft: "rgb(var(--accent-soft) / <alpha-value>)",
        },
        slate: {
          DEFAULT: "rgb(var(--ink-soft) / <alpha-value>)",
          2: "rgb(var(--ink-mute) / <alpha-value>)",
        },
        mist: "var(--rule-2)",
        verified: "rgb(var(--verified) / <alpha-value>)",
        caution: "rgb(var(--caution) / <alpha-value>)",
        danger: "rgb(var(--danger) / <alpha-value>)",

        // Legacy alias bag — redirected to the var palette
        bg: "rgb(var(--paper) / <alpha-value>)",
        panel: "rgb(var(--paper-2) / <alpha-value>)",
        surface: "rgb(var(--paper-2) / <alpha-value>)",
        border: "var(--rule)",
        text: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--ink-soft) / <alpha-value>)",

        // Traffic-light review colors — semantic, tuned per theme in globals.css.
        risk: {
          green: "rgb(var(--risk-green) / <alpha-value>)",
          yellow: "rgb(var(--risk-yellow) / <alpha-value>)",
          amber: "rgb(var(--risk-amber) / <alpha-value>)",
          red: "rgb(var(--risk-red) / <alpha-value>)",
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
        // Hairline only — borders carry elevation (invisible-by-design on dark).
        soft: "0 1px 0 rgba(0,0,0,0.04)",
        chat: "0 1px 0 rgba(0,0,0,0.04)",
        ring: "0 0 0 2px rgb(var(--accent) / 0.25)",
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
