// Runs the app's Vite dev server in browser-preview mode (fake backend) and drives it with the
// installed Chrome (no browser download). Proves UI structure, look and click-through behavior, never the Rust commands.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: ["ui-check.spec.ts", "*.flows.spec.ts"], // structure and look; click-throughs of golden scenarios
  workers: 1,
  use: { baseURL: "http://localhost:1431", channel: "chrome", viewport: { width: 1024, height: 768 } },
  webServer: { command: "npm run dev -- --port 1431 --strictPort", url: "http://localhost:1431", reuseExistingServer: true },
});
