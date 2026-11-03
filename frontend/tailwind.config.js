/** @type {import('tailwindcss').Config} */
// Theme: "dark premium". Every colour family the app uses is a CSS variable (RGB triplet, defined in index.css), so
// the whole UI is themed in one place and opacity modifiers (bg-white/90) keep working.
//   slate  = neutral scale, ROLE-based: 50 = page background ... 900 = headings, 950 = brightest text
//   white  = card / surface colour (not literally white in the dark theme)
//   brand  = indigo-violet accent; emerald/rose/red/amber/sky/teal = status colours, dark-tuned
// Fixed colours that never change with the theme:
//   snow   = real white (text on coloured buttons, overlays on video)   night = real dark navy (video/3D stages)
const v = (name) => {
  const out = {};
  for (const k of [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]) out[k] = `rgb(var(--${name}-${k}) / <alpha-value>)`;
  return out;
};

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        slate: v("n"), brand: v("brand"), emerald: v("emerald"), rose: v("rose"), red: v("rose"),
        amber: v("amber"), sky: v("sky"), teal: v("teal"),
        white: "rgb(var(--surface) / <alpha-value>)",
        snow: "#ffffff",
        night: { 700: "#1a2240", 800: "#111832", 900: "#0b1024", 950: "#060914" },
        violet: { 400: "#a78bfa", 500: "#8b5cf6", 600: "#7c3aed" },
      },
      fontFamily: {
        sans: ["Geist", "Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Geist", "Inter", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      boxShadow: {
        soft: "0 1px 0 rgb(255 255 255 / 0.04) inset, 0 1px 2px rgb(0 0 0 / 0.4)",
        lift: "0 1px 0 rgb(255 255 255 / 0.05) inset, 0 20px 40px -20px rgb(0 0 0 / 0.7)",
        glow: "0 0 0 1px rgb(129 140 248 / 0.35), 0 8px 24px -6px rgb(99 102 241 / 0.55)",
        pop: "0 0 0 1px rgb(255 255 255 / 0.06), 0 24px 48px -12px rgb(0 0 0 / 0.75)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "none" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        grow: { "0%": { transform: "scaleX(0)" }, "100%": { transform: "scaleX(1)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        "pulse-ring": { "0%": { transform: "scale(0.9)", opacity: "0.6" }, "100%": { transform: "scale(1.6)", opacity: "0" } },
      },
      animation: {
        "fade-up": "fade-up 0.35s cubic-bezier(.2,.7,.2,1) both",
        float: "float 6s ease-in-out infinite",
        shimmer: "shimmer 2.5s linear infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(.2,.7,.2,1) infinite",
      },
    },
  },
  plugins: [],
};
