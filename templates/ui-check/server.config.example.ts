import { defineConfig } from "@playwright/test";

/** Real-server flows (server-fixtures.example.ts): the app in Chrome, the built Node server over HTTP, a fresh database per
 *  worker. `npm run flows:server`; APP_TEST_DATABASE_URL (from the CI environment) uses a real PostgreSQL. */
const port = Number(process.env.APP_SERVER_FLOW_PORT ?? 1440);
export default defineConfig({
  testDir: ".",
  testMatch: "*.server.spec.ts",
  globalSetup: "./server-build.example.ts",
  fullyParallel: true,
  workers: Number(process.env.APP_FLOW_WORKERS ?? 2),
  timeout: 120_000,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    channel: "chrome",
    locale: "pt-PT",
    navigationTimeout: 90_000,
    viewport: { width: 1400, height: 900 },
  },
  webServer: {
    command: `npx vite --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120_000,
    cwd: "../..",
  },
});
