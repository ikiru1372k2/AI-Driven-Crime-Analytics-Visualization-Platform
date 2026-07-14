import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Local dev: proxy API to the FastAPI backend; deployed builds call the
      // Catalyst API Gateway base URL via VITE_API_BASE (CAT-004/CAT-006).
      "/api": "http://localhost:8000",
    },
  },
});
