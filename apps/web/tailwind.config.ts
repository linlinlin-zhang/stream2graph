import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 16px 48px rgba(15, 23, 42, 0.08)",
      },
      colors: {
        accent: "var(--accent)",
        "accent-strong": "var(--accent-strong)",
      },
    },
  },
  plugins: [],
};

export default config;
