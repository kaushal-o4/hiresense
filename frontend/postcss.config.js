// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/postcss.config.js
//
// FILE PURPOSE:
// Tells PostCSS to run Tailwind CSS and Autoprefixer when CSS is built.
//
// WHAT THIS FILE DOES:
// 1. Enables the tailwindcss plugin.
// 2. Enables autoprefixer (adds browser-specific CSS prefixes).
//
// OUTPUT:
// Processed CSS for the browser.
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
