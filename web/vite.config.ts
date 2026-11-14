import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on("error", () => {
            // Suppress proxy ECONNRESET when backend is offline or browser tab closes
          });
        },
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        configure: (proxy) => {
          proxy.on("error", () => {
            // Suppress proxy ECONNRESET
          });
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
