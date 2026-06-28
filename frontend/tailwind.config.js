/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Flight-deck observatory palette — Capgemini brand re-theme
        void: "#04070d", // deep navy-black base
        panel: "#0a1018",
        "panel-2": "#0f1722",
        grid: "#14202e",
        edge: "#233246",
        brand: "#12ABDB", // Capgemini Gamma Blue — primary accent / glow
        deep: "#0070AD", // Capgemini Honolulu Blue — secondary / structural
        live: "#9be34a", // live / positive (functional, kept)
        alert: "#ff5d62", // alert / cost / error (functional, kept)
        ash: "#8595a8",
        haze: "#5b6878",
        bone: "#e6edf3",
      },
      fontFamily: {
        display: ['"Chakra Petch"', "sans-serif"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(18,171,219,0.25), 0 0 24px -6px rgba(18,171,219,0.45)",
        "glow-deep": "0 0 0 1px rgba(0,112,173,0.25), 0 0 24px -6px rgba(0,112,173,0.4)",
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
        glow_pulse: {
          "0%, 100%": { boxShadow: "0 0 0 1px rgba(18,171,219,0.20), 0 0 16px -8px rgba(18,171,219,0.30)" },
          "50%": { boxShadow: "0 0 0 1px rgba(18,171,219,0.45), 0 0 28px -6px rgba(18,171,219,0.65)" },
        },
        boot_bar: {
          "0%": { width: "0%" },
          "100%": { width: "100%" },
        },
      },
      animation: {
        flicker: "flicker 6s linear infinite",
        sweep: "sweep 7s linear infinite",
        "pulse-dot": "pulse_dot 1.4s ease-in-out infinite",
        "glow-pulse": "glow_pulse 2.6s ease-in-out infinite",
        "boot-bar": "boot_bar 0.9s ease-out forwards",
      },
    },
  },
  plugins: [],
};
