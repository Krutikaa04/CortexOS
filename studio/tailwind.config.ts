import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark technical control-plane palette
        ink: {
          950: "#07090e",
          900: "#0b0e15",
          850: "#10141d",
          800: "#151a26",
          700: "#1e2534",
          600: "#2a3348",
          500: "#3b465f",
          400: "#5b6880",
          300: "#8593ab",
          200: "#b3becf",
          100: "#dde3ec",
        },
        signal: {
          green: "#3ddc97",
          amber: "#ffc75f",
          red: "#ff6b6b",
          blue: "#5aa7ff",
          violet: "#a78bfa",
          cyan: "#4dd0e1",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
