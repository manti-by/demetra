import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
    server: {
        allowedHosts: ["demetra.manti.by"],
    },
    preview: {
        allowedHosts: ["demetra.manti.by"],
    },
});
