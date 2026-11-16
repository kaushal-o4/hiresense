// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/tailwind.config.js
//
// FILE PURPOSE:
// Configuration of Tailwind CSS: which files to scan and the custom theme colours and fonts.
//
// WHAT THIS FILE DOES:
// 1. Tells Tailwind to scan index.html and src/**/*.js(x) for class names.
// 2. Maps colour names (slate, brand, emerald, ...) to the CSS variables in index.css.
// 3. Sets the Inter (body) and Manrope (display) font families.
//
// HOW THIS FILE WORKS:
// The helper v(name) creates a colour scale whose values are rgb(var(--name-N)), so colours come from
// index.css.
//
// IMPORTANT FUNCTIONS:
//    - v()
//        Theme: HireSense light + dark tokens.
//
// OUTPUT:
// The Tailwind theme used when the CSS is built.
//
// IMPORTANT DEPENDENCIES:
//    tailwindcss
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/** @type {import('tailwindcss').Config} */
// Every colour family is a CSS variable (RGB triplet, defined in index.css), so light/dark themes switch in one place
// and opacity modifiers (bg-white/90) keep working.
//   slate  = neutral scale, ROLE-based: 50 = page background ... 900 = headings, 950 = strongest ink
//   white  = card / surface colour (dark navy in the dark theme)
//   brand  = HireSense blue (#315EF7); emerald/rose/amber/sky/teal = status colours
// Fixed colours that never change with the theme:
//   snow = real white (text on brand buttons, overlays on video)   night = midnight navy (hero, video/3D stages)
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
        violet: v("brand"), indigo: v("brand"), // legacy names: no purple in the palette
        white: "rgb(var(--surface) / <alpha-value>)",
        snow: "#ffffff",
        night: { 600: "#263449", 700: "#1E2A3B", 800: "#172333", 900: "#10151D", 950: "#0B0F15" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Manrope", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      boxShadow: {
        soft: "var(--shadow-card)",
        lift: "var(--shadow-pop)",
        pop: "var(--shadow-pop)",
        glow: "0 1px 2px rgb(16 21 29 / 0.12), 0 4px 12px -4px rgb(49 94 247 / 0.35)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "none" } },
        "fade-in": { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        "scale-in": { "0%": { opacity: "0", transform: "scale(.97) translateY(4px)" }, "100%": { opacity: "1", transform: "none" } },
        "slide-in": { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "none" } },
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        grow: { "0%": { transform: "scaleX(0)" }, "100%": { transform: "scaleX(1)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        "pulse-ring": { "0%": { transform: "scale(0.9)", opacity: "0.6" }, "100%": { transform: "scale(1.6)", opacity: "0" } },
        "eq": { "0%,100%": { transform: "scaleY(.35)" }, "50%": { transform: "scaleY(1)" } },
      },
      animation: {
        "fade-up": "fade-up 0.35s cubic-bezier(.2,.7,.2,1) both",
        "fade-in": "fade-in 0.25s ease-out both",
        "scale-in": "scale-in 0.2s cubic-bezier(.2,.7,.2,1) both",
        "slide-in": "slide-in 0.25s cubic-bezier(.2,.7,.2,1) both",
        float: "float 6s ease-in-out infinite",
        shimmer: "shimmer 2.5s linear infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(.2,.7,.2,1) infinite",
        eq: "eq 0.9s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
