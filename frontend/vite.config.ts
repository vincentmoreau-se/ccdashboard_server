import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Node global, available when Vite evaluates this config (avoids a @types/node dep).
declare const process: { env: Record<string, string | undefined> };

// Dev proxy: the frontend talks to itself (same-origin) so the signed session
// cookie is sent automatically — including to the SSE endpoint.
export default defineConfig({
  // Subpath base for production builds (e.g. "/ccdash/"); "/" in dev.
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/api": { target: "http://localhost:8090", changeOrigin: true },
      "/ingest": { target: "http://localhost:8090", changeOrigin: true },
    },
  },
});
