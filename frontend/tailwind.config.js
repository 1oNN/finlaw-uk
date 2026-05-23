/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0F1E3D",
          2: "#1A2A4F",
          soft: "#25355A",
        },
        ivory: {
          DEFAULT: "#F7F3EA",
          2: "#EFE9DA",
          3: "#E5DEC9",
        },
        gold: {
          DEFAULT: "#B8893A",
          2: "#8E6A2C",
          soft: "#E8D9B7",
        },
        slate: {
          DEFAULT: "#4A5878",
          2: "#6B7796",
        },
        mist: "#C7CCDB",
        verified: "#2F7A4F",
        caution: "#B07A1F",
        danger: "#A33A2A",

        // legacy aliases so existing components keep compiling while they're being restyled
        bg: "#F7F3EA",
        panel: "#FFFFFF",
        surface: "#FBF7EE",
        border: "#E5DEC9",
        text: "#0F1E3D",
        muted: "#4A5878",
        accent: { DEFAULT: "#B8893A", hover: "#8E6A2C" },

        risk: {
          green: "#4A8A6B",
          yellow: "#C7A04A",
          amber: "#B57536",
          red: "#B5453E",
        },
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      maxWidth: {
        chat: "760px",
        prose: "68ch",
      },
      borderRadius: {
        card: "14px",
        bubble: "16px",
        chip: "999px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15,30,61,.06), 0 8px 24px rgba(15,30,61,.08)",
        chat: "0 1px 2px rgba(15,30,61,.05), 0 12px 32px rgba(15,30,61,.10)",
        ring: "0 0 0 3px rgba(184,137,58,.25)",
      },
      letterSpacing: {
        tightish: "-0.01em",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in .25s ease-out both",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
