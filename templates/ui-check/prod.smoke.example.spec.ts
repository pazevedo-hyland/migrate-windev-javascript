// The packaged app of a real migration rendered a blank window while the dev server and every browser flow passed:
// Vite inlines assets under build.assetsInlineLimit (default 4096 bytes) as data: URLs in the production build only,
// and the skin resolver refuses data: URLs. Fix: `build: { assetsInlineLimit: 0 }` in vite.config.ts; this test keeps
// it fixed. Replace <start url> and <FIRST_WINDOW> with the app's start page and first window (its legacy name).
import { expect, test } from "@playwright/test";

test("production build: the first window renders with its skin images and no page error", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/"); // <start url>
  await expect(page.locator('section[data-layout="<FIRST_WINDOW>"]')).toBeVisible({ timeout: 60_000 });
  const inlined = await page.evaluate(() => [...document.querySelectorAll("*")].some(element => {
    const style = getComputedStyle(element);
    return /url\("?data:/.test(style.backgroundImage + style.borderImageSource)
      || (element instanceof HTMLImageElement && element.src.startsWith("data:"));
  }));
  expect(inlined, "images inlined as data: URLs in the production build").toBe(false);
  expect(errors).toEqual([]);
});
