import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// CryptoSage Console frontend.
// Talks to the FastAPI backend (default http://localhost:8000) over plain
// fetch -- see src/api.js. Override with a .env file: VITE_API_BASE_URL=...
export default defineConfig({
  plugins: [react()],
  server: { port: 3000, strictPort: true },
  preview: { port: 3000, strictPort: true },
});
