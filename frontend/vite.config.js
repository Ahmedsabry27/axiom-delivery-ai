import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({mode})=>{
  const env=loadEnv(mode,".","");
  if(mode==="production"&&env.VITE_USE_MOCK_DELIVERY_DATA==="true")throw new Error("Production builds cannot enable VITE_USE_MOCK_DELIVERY_DATA");
  return ({
  plugins: [
    react(),
    tailwindcss(),
  ],

  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },

  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/conversations": {
        target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/chat": {
        target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
    maxWorkers: 1,
    exclude: ["e2e/**", "e2e-live/**", "node_modules/**", "dist/**"],
  },
  });
});
