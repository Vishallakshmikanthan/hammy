import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.VITE_API_TARGET || "http://127.0.0.1:8088";
const wsTarget = apiTarget.replace(/^http/, "ws");

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
        target: apiTarget,
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on("error", () => {
            // Suppress proxy ECONNRESET when backend is offline or browser tab closes
          });
        },
      },
      "/ws": {
        target: wsTarget,
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
