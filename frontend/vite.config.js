import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173 (matches the backend's default CORS allow-list -
// see backend/app/api/app_factory.py).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
