import { expect, test } from "@playwright/test";

test("synthetic directory uses real RAD controls, table selection and awaited confirmation", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "Demo directory", exact: true }).click();
  await expect(page.getByTestId("TABLE_Entries")).toBeVisible();
  await page.getByRole("row").filter({ hasText: "Example association" }).click();
  await expect(page.getByTestId("EDT_Name")).toHaveValue("Example association");
  await page.getByTestId("EDT_Name").fill("Renamed association");
  await page.getByTestId("CBOX_Active").uncheck();
  await page.getByTestId("BTN_Save").click();
  await expect(page.getByRole("row").filter({ hasText: "Renamed association" })).toContainText("No");
  await page.getByTestId("BTN_Delete").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "Renamed association" })).toBeVisible();
  await page.getByTestId("BTN_Delete").click();
  await page.getByTestId("BTN_OUI").click();
  await expect(page.getByRole("row").filter({ hasText: "Renamed association" })).toHaveCount(0);
  await page.getByTestId("BTN_New").click();
  await page.getByTestId("EDT_Name").fill("New demo organisation");
  await page.getByTestId("BTN_Save").click();
  await expect(page.getByRole("row").filter({ hasText: "New demo organisation" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("workspace reuses one window and keeps controls inside its frame", async ({ page }) => {
  await page.goto("/");
  const launch = page.getByRole("button", { name: "Demo directory", exact: true });
  await launch.click(); await launch.click();
  await expect(page.locator(".wd-workspace-window")).toHaveCount(1);
  const frame = await page.locator(".wd-frame").boundingBox();
  const table = await page.getByTestId("TABLE_Entries").boundingBox();
  expect(frame).not.toBeNull(); expect(table).not.toBeNull();
  expect(table!.x).toBeGreaterThanOrEqual(frame!.x);
  expect(table!.y).toBeGreaterThanOrEqual(frame!.y);
  expect(table!.x + table!.width).toBeLessThanOrEqual(frame!.x + frame!.width);
  expect(table!.y + table!.height).toBeLessThanOrEqual(frame!.y + frame!.height);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.locator(".wd-workspace-window")).toHaveCount(0);
});

test("unconfigured source skins, prototype-like names and missing geometry remain usable scaffolds", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/ui-check/extraction.html");
  await page.getByRole("button", { name: "Unknown source assets", exact: true }).click();
  await page.getByTestId("Draft").fill("Draft survives React updates");
  await expect(page.getByTestId("Draft")).toHaveValue("Draft survives React updates");
  await expect(page.getByTestId("Action")).toBeDisabled();
  await expect(page.getByTestId("unbound:Unsupported")).toContainText("<img src=x onerror=alert(1)>");
  await expect(page.locator(".wd-frame img")).toHaveCount(0);
  const title = await page.locator(".wd-title").boundingBox();
  const missing = await page.getByTestId("unbound:MissingSize").boundingBox();
  expect(missing!.y).toBeGreaterThan(title!.y + title!.height);
  await page.getByText(/Extraction diagnostics/).click();
  await expect(page.locator(".screen-status details")).toContainText("unconfigured skin");
  expect(errors).toEqual([]);
});
