// Playwright globalSetup: load the app once before the tests. Vite's first page load on a cold start (dependency
// pre-bundling, large WASM/data packages) exceeded the first test's navigation timeout on a real migration, which
// then failed for no application reason. Optional WARMUP_SELECTOR: an element that appears once the app is ready.
import { chromium, type FullConfig } from "@playwright/test";

export default async function warmup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL;
  if (!baseURL) return;
  const browser = await chromium.launch({ channel: "chrome" });
  try {
    const page = await browser.newPage();
    await page.goto(baseURL, { timeout: 300_000 });
    if (process.env.WARMUP_SELECTOR) await page.locator(process.env.WARMUP_SELECTOR).first().waitFor({ timeout: 300_000 });
  } finally {
    await browser.close();
  }
}
