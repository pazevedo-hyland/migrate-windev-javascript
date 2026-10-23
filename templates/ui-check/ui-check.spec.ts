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
type Config = {
  /** inspect_windev.py output; default: "inspect" in analysis-local/latest.json (prepare_evidence.py). */
  inspectDir?: string;
  /** Legacy window images (<WINDOW>.png|jpg); default: docs/evidence/images (committed). */
  legacyScreenshots?: string;
  report: string;
  /** dossier_extract.py output, for caption comparison; default: "dossier" in analysis-local/latest.json. */
  dossierDir?: string;
  /** Caption language in the dossier, e.g. "PT"; default: the first language of each caption. */
  language?: string;
  windows: Record<string, WindowConfig & { captionIgnore?: Record<string, string> }>;
};

const root = process.cwd();
const config: Config = JSON.parse(readFileSync(join(root, "ui-check.config.json"), "utf-8"));
const latestPath = join(root, "analysis-local", "latest.json");
const latest: { inspect?: string; dossier?: string } = existsSync(latestPath) ? JSON.parse(readFileSync(latestPath, "utf-8")) : {};
config.inspectDir ??= latest.inspect;
config.dossierDir ??= latest.dossier;
config.legacyScreenshots ??= "docs/evidence/images";
if (!config.inspectDir) throw new Error("no inspector output: run python3 scripts/prepare_evidence.py first");

/** Legacy control names per window, from inspect_windev.py output (code/<file>.wdw.json). */
function legacyControls(window: string): string[] {
  const stack = [resolve(root, config.inspectDir!, "code")];
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

/** {legacy control name: caption} from the dossier extract. */
function legacyCaptions(window: string): Record<string, string> {
  if (!config.dossierDir) return {};
  const path = resolve(root, config.dossierDir, "windev-window", `${window}.json`);
  if (!existsSync(path)) return {};
  const controls = JSON.parse(readFileSync(path, "utf-8")).controls ?? {};
  const captions: Record<string, string> = {};
  for (const [name, control] of Object.entries<{ kind?: string; caption?: string | Record<string, string> }>(controls)) {
    // Tables, supercontrols and loopers carry an internal caption that WINDEV does not display.
    if (["Table", "Supercontrol", "Looper"].includes(control.kind ?? "")) continue;
    const caption = typeof control.caption === "string" ? control.caption
      : control.caption && (control.caption[config.language ?? ""] ?? Object.values(control.caption)[0]);
    if (caption) captions[name] = caption;
  }
  return captions;
}

const normalize = (text: string) => text.replace(/&/g, "").replace(/\s+/g, " ").trim().toLowerCase();

type Mismatch = { name: string; legacy: string; actual: string };
const results: { window: string; missing: string[]; ignored: number; total: number; captions: Mismatch[] }[] = [];

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
    const captions: Mismatch[] = [];
    for (const [name, legacy] of Object.entries(legacyCaptions(window))) {
      if (name in settings.ignore || name in (settings.captionIgnore ?? {})) continue;
      if ((await page.getByTestId(name).count()) === 0) continue;
      const element = page.getByTestId(name).first();
      const actual = (await element.innerText().catch(() => "")) || (await element.getAttribute("value")) || "";
      if (!normalize(actual).includes(normalize(legacy))) captions.push({ name, legacy, actual: actual.trim() });
    }
    mkdirSync(resolve(root, config.report), { recursive: true });
    await view.screenshot({ path: resolve(root, config.report, `${window}.png`) });
    results.push({ window, missing, ignored: Object.keys(settings.ignore).length, total: expected.length, captions });
    expect(missing, `legacy controls with no data-testid in ${window}`).toEqual([]);
    expect(captions, `captions differing from the legacy dossier in ${window}`).toEqual([]);
  });
}

test.afterAll(() => {
  const rows = results.map((r) => {
    const legacy = [`${r.window}.png`, `${r.window}.jpg`, join(r.window, "screenshot.png")]
      .map((name) => resolve(root, config.legacyScreenshots!, name))
      .find((path) => existsSync(path)) ?? "";
    const legacyCell = legacy ? `<img src="file://${legacy}">` : "<em>no legacy screenshot yet</em>";
    return `<tr><td><b>${r.window}</b><br>${r.total - r.missing.length}/${r.total} controls, ${r.ignored} ignored` +
      `${r.missing.length ? `<br>missing: ${r.missing.join(", ")}` : ""}` +
      `${r.captions.map((c) => `<br>${c.name}: “${c.actual}” ≠ legacy “${c.legacy}”`).join("")}</td>` +
      `<td><img src="${r.window}.png"></td><td>${legacyCell}</td></tr>`;
  });
  writeFileSync(resolve(root, config.report, "index.html"),
    `<!doctype html><meta charset="utf-8"><title>UI parity report</title><style>img{max-width:560px;border:1px solid #ccc}` +
    `td{vertical-align:top;padding:8px}</style><table><tr><th>Window</th><th>New</th><th>Legacy</th></tr>${rows.join("")}</table>`);
});
