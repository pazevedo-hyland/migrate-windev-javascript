import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./ui-check", fullyParallel: false, workers: 1,
  use: { baseURL: "http://127.0.0.1:1421", channel: "chrome", viewport: { width: 1280, height: 850 } },
  webServer: { command: "npx vite --host 127.0.0.1 --port 1421 --strictPort", url: "http://127.0.0.1:1421", reuseExistingServer: false },
});
