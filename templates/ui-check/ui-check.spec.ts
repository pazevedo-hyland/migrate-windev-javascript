// Automated UI parity check: every legacy control exists in the new screen, plus a
// side-by-side screenshot report (new vs legacy). Copy templates/ui-check/ into the app.
import { expect, test } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

type WindowConfig = {
  /** data-testids to click, in order, from the start page (usually the legacy route). */
  open: string[];
  /** Legacy controls deliberately absent, each with the reason (ADR, deferred slice, skin chrome…). */
  ignore: Record<string, string>;
};
type Config = { inspectDir: string; legacyScreenshots: string; report: string; windows: Record<string, WindowConfig> };

const root = process.cwd();
const config: Config = JSON.parse(readFileSync(join(root, "ui-check.config.json"), "utf-8"));

/** Legacy control names per window, from inspect_windev.py output (code/<file>.wdw.json). */
function legacyControls(window: string): string[] {
  const stack = [resolve(root, config.inspectDir, "code")];
  while (stack.length) {
    const dir = stack.pop()!;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) stack.push(path);
      else if (entry.name.toLowerCase() === `${window.toLowerCase()}.wdw.json`) {
        return JSON.parse(readFileSync(path, "utf-8")).controls ?? [];
      }
    }
  }
  throw new Error(`no inspector output for ${window}`);
}

const results: { window: string; missing: string[]; ignored: number; total: number }[] = [];

for (const [window, settings] of Object.entries(config.windows)) {
  test(`${window}: legacy controls present`, async ({ page }) => {
    await page.goto("/");
    for (const id of settings.open) await page.getByTestId(id).first().click();
    const view = page.getByTestId(window).first();
    await expect(view).toBeVisible();
    const expected = legacyControls(window).filter((name) => !(name in settings.ignore));
    const missing: string[] = [];
    for (const name of expected) {
      if ((await page.getByTestId(name).count()) === 0) missing.push(name);
    }
    mkdirSync(resolve(root, config.report), { recursive: true });
    await view.screenshot({ path: resolve(root, config.report, `${window}.png`) });
    results.push({ window, missing, ignored: Object.keys(settings.ignore).length, total: expected.length });
    expect(missing, `legacy controls with no data-testid in ${window}`).toEqual([]);
  });
}

test.afterAll(() => {
  const rows = results.map((r) => {
    // Accepts both <WINDOW>.png and the capture kit's <WINDOW>/screenshot.png.
    const legacy = [`${r.window}.png`, join(r.window, "screenshot.png")]
      .map((name) => resolve(root, config.legacyScreenshots, name))
      .find((path) => existsSync(path)) ?? "";
    const legacyCell = legacy ? `<img src="file://${legacy}">` : "<em>no legacy screenshot yet</em>";
    return `<tr><td><b>${r.window}</b><br>${r.total - r.missing.length}/${r.total} controls, ${r.ignored} ignored` +
      `${r.missing.length ? `<br>missing: ${r.missing.join(", ")}` : ""}</td>` +
      `<td><img src="${r.window}.png"></td><td>${legacyCell}</td></tr>`;
  });
  writeFileSync(resolve(root, config.report, "index.html"),
    `<!doctype html><meta charset="utf-8"><title>UI parity report</title><style>img{max-width:560px;border:1px solid #ccc}` +
    `td{vertical-align:top;padding:8px}</style><table><tr><th>Window</th><th>New</th><th>Legacy</th></tr>${rows.join("")}</table>`);
});
