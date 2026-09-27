import { defineConfig } from "vite";
export default defineConfig({
  server: {
    port: 5197,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8197" },
  },
  build: { chunkSizeWarningLimit: 700 },
});
