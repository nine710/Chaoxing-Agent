/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface1: "var(--surface-1)",
        surface2: "var(--surface-2)",
        surface3: "var(--surface-3)",
        line: "var(--line)",
        fg: "var(--fg)",
        muted: "var(--fg-muted)",
        dim: "var(--fg-dim)",
        accent: "var(--accent)",
        "accent-fg": "var(--accent-fg)",
        "accent-dim": "var(--accent-dim)",
        ok: "var(--ok)",
        err: "var(--err)",
        warn: "var(--warn)",
        info: "var(--info)",
        background: "var(--bg)",
        foreground: "var(--fg)",
        border: "var(--line)",
        destructive: "var(--err)",
        "destructive-foreground": "var(--bg)",
        primary: "var(--accent)",
        "primary-foreground": "var(--accent-fg)",
      },
      fontFamily: {
        sans: "var(--sans)",
        mono: "var(--mono)",
      },
    },
  },
  plugins: [],
};