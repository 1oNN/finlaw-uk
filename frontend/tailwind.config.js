/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0f14",
        panel: "#0f1115",
        surface: "#13161b",
        // brighter border so lines are visible
        border: "#3b4252",
        text: "#e6e6e6",
        muted: "#a0a3ad",
        accent: { DEFAULT: "#10a37f", hover: "#0e8f70" },
        risk: {
          green: "#2bb673",
          yellow: "#d9a441",
          amber: "#e07a35",
          red: "#d34b4b",
        },
      },
      maxWidth: { chat: "820px" },
      boxShadow: { chat: "0 10px 30px rgba(0,0,0,.35)" },
      borderRadius: { bubble: "18px" },
    },
  },
  plugins: [],
};
