import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ["localhost", "192.168.1.105", "demetra.manti.by"],
  },
  preview: {
    allowedHosts: ["localhost", "192.168.1.105", "demetra.manti.by"],
  },
});
