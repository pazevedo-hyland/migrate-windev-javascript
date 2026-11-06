// Smoke test of the production build (`vite build` -> `vite preview`): what the installer ships, not the dev server.
// Copy with prod.smoke.example.spec.ts into ui-check/ and add `"smoke:prod": "playwright test -c ui-check/prod.config.ts"`
// to package.json, run by `verify` after the build. Keep assetsInlineLimit: 0 in vite.config.ts (see the spec).
import { defineConfig } from "@playwright/test";

const port = Number(process.env.PROD_SMOKE_PORT ?? 1450);
export default defineConfig({
  testDir: ".", testMatch: "prod.smoke*.spec.ts", workers: 1, timeout: 120_000,
  use: { baseURL: `http://127.0.0.1:${port}`, channel: "chrome", navigationTimeout: 90_000 },
  webServer: { command: `npx vite preview --host 127.0.0.1 --port ${port} --strictPort`, url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false, timeout: 120_000, cwd: ".." },
});
