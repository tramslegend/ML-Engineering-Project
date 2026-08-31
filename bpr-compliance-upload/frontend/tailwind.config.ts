import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        sans: ["var(--font-public-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        bpr: {
          ink: "#0E1826",
          navy: "#152238",
          navyLight: "#22344F",
          parchment: "#F6F1E7",
          parchmentDark: "#EFE7D6",
          card: "#FFFDF8",
          hairline: "#E4DCC8",
          brass: "#B8892B",
          brassLight: "#D9AE55",
          teal: "#1F6B57",
          tealLight: "#2C8B72",
          rose: "#A34840",
          plum: "#5C3F80",
          ink2: "#3B4657",
        },
      },
      boxShadow: {
        ledger: "0 1px 2px rgba(14,24,38,0.04), 0 8px 24px -12px rgba(14,24,38,0.18)",
        ledgerHover: "0 2px 4px rgba(14,24,38,0.06), 0 16px 32px -14px rgba(14,24,38,0.24)",
      },
      backgroundImage: {
        grain:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
};
export default config;
