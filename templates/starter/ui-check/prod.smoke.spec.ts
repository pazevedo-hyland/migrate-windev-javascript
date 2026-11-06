import { expect, test } from "@playwright/test";

// Smoke test of the production build (vite build -> vite preview): what the Tauri bundle ships, not the dev server.
// A migrated app once rendered a blank packaged window: Vite inlined small skin images as data: URLs in the build only,
// and the skin resolver refuses them. Extend it to open the application's first real window with its skin.
test("production build: the first window renders, no inlined image, no page error", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("navigation", { name: "Screens" }).getByRole("button").first().click();
  await expect(page.locator(".wd-frame").first()).toBeVisible();
  const inlined = await page.evaluate(() => [...document.querySelectorAll("*")].some(element => {
    const style = getComputedStyle(element);
    return /url\("?data:/.test(style.backgroundImage + style.borderImageSource)
      || (element instanceof HTMLImageElement && element.src.startsWith("data:"));
  }));
  expect(inlined).toBe(false);
  expect(errors).toEqual([]);
});
