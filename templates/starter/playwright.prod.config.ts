import { defineConfig } from "@playwright/test";

/** Production-build smoke test: serves dist/ with `vite preview`. Run after `vite build` (npm run smoke:prod). */
export default defineConfig({
  testDir: "./ui-check", testMatch: "prod.smoke.spec.ts", workers: 1,
  use: { baseURL: "http://127.0.0.1:1422", channel: "chrome", viewport: { width: 1280, height: 850 } },
  webServer: { command: "npx vite preview --host 127.0.0.1 --port 1422 --strictPort", url: "http://127.0.0.1:1422", reuseExistingServer: false },
});
