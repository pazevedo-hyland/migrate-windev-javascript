import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./ui-check", fullyParallel: false, workers: 1,
  use: { baseURL: "http://127.0.0.1:1421", channel: "chrome", viewport: { width: 1280, height: 850 } },
  webServer: { command: "node --import tsx ui-check/support/server.ts", url: "http://127.0.0.1:1421", reuseExistingServer: false,
    gracefulShutdown: { signal: "SIGTERM", timeout: 10000 } },
});
