import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()], clearScreen: false, server: { host: "127.0.0.1", strictPort: true },
  // Never inline assets: Vite turns files under 4 KiB (build.assetsInlineLimit default 4096) into data: URLs in the
  // production build only, and the skin resolver (packages/ui assets.ts) refuses data: URLs, so a packaged app with
  // small skin images rendered a blank window while the dev server and browser flows passed. npm run smoke:prod
  // checks the built app.
  build: { assetsInlineLimit: 0 },
});
