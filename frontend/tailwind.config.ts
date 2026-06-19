import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#fcf8fa",
          dim: "#dcd9db",
          container: {
            DEFAULT: "#f0edef",
            low: "#f6f3f5",
            highest: "#e4e2e4",
          },
        },
        on: {
          surface: {
            DEFAULT: "#1b1b1d",
            variant: "#45464d",
          },
        },
        outline: {
          DEFAULT: "#76777d",
          variant: "#c6c6cd",
        },
        primary: {
          DEFAULT: "#000000",
          container: "#131b2e",
        },
        status: {
          completed: { bg: "#ecfdf5", text: "#15803d", border: "#bbf7d0" },
          failed: { bg: "#fef2f2", text: "#b91c1c", border: "#fecaca" },
          partial: { bg: "#fffbeb", text: "#b45309", border: "#fde68a" },
          skipped: { bg: "#f8fafc", text: "#64748b", border: "#e2e8f0" },
          running: { bg: "#eff6ff", text: "#1d4ed8", border: "#bfdbfe" },
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "JetBrains Mono", "monospace"],
      },
      fontSize: {
        "label-caps": ["11px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "600" }],
        "headline-lg": ["24px", { lineHeight: "32px", letterSpacing: "-0.02em", fontWeight: "600" }],
        "headline-md": ["18px", { lineHeight: "24px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "body-md": ["14px", { lineHeight: "20px" }],
        "body-sm": ["13px", { lineHeight: "18px" }],
        "data-mono": ["12px", { lineHeight: "16px", fontWeight: "500" }],
      },
      maxWidth: {
        container: "1440px",
      },
      boxShadow: {
        overlay: "0 10px 15px -3px rgba(0,0,0,0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
