import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = process.env.VITE_API_BASE || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // timeouts holgados: las llamadas del VLM (LLM + imagen) tardan varios segundos
      "/api": { target: API, changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
    },
  },
});
