/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Flight-deck observatory palette
        void: "#07090d",
        panel: "#0d1117",
        "panel-2": "#11161f",
        grid: "#1b2330",
        edge: "#2a3543",
        amber: "#ffb000", // phosphor CRT amber — primary accent
        cyan: "#36e0e0", // cool telemetry secondary
        lime: "#9be34a",
        rose: "#ff5d62",
        ash: "#8595a8",
        haze: "#5b6878",
        bone: "#e6edf3",
      },
      fontFamily: {
        display: ['"Chakra Petch"', "sans-serif"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,176,0,0.25), 0 0 24px -6px rgba(255,176,0,0.35)",
        "glow-cyan": "0 0 0 1px rgba(54,224,224,0.25), 0 0 24px -6px rgba(54,224,224,0.35)",
        panel: "inset 0 1px 0 0 rgba(255,255,255,0.03), 0 8px 30px -12px rgba(0,0,0,0.8)",
      },
      keyframes: {
        flicker: {
          "0%, 100%": { opacity: "1" },
          "92%": { opacity: "1" },
          "93%": { opacity: "0.7" },
          "94%": { opacity: "1" },
        },
        sweep: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        pulse_dot: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.35", transform: "scale(0.8)" },
        },
      },
      animation: {
        flicker: "flicker 6s linear infinite",
        sweep: "sweep 7s linear infinite",
        "pulse-dot": "pulse_dot 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
