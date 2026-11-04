import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to FastAPI so the auth cookie stays same-origin.
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Big libraries in their own long-cached chunks. three and recharts are only downloaded by the pages that
        // use them (avatar / charts), react is shared by everything.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler|@remix-run)[\\/]/.test(id)) return "react";
          if (id.includes("/three/") || id.includes("\\three\\")) return "three";
          if (/[\\/]node_modules[\\/](recharts|d3-[^\\/]+|victory-vendor|internmap|lodash|react-smooth|recharts-scale|decimal\.js-light|eventemitter3|fast-equals|tiny-invariant|clsx|react-is|prop-types|react-transition-group|dom-helpers)[\\/]/.test(id)) return "charts";
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.HS_API || "http://127.0.0.1:8000", changeOrigin: true }, // HS_API: a second backend for tests
    },
  },
});
