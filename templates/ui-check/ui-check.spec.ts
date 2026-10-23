// Automated UI parity check: every legacy control exists in the new screen with its legacy caption, and the
// screen is scored against the legacy image (scripts/visual_compare.py, recorded in docs/evidence/visual/ for
// the progress page; a score below the floor or a drop below the last score fails; so does a failed image request). Side-by-side report in ui-report/. Configure every
// window the app can open — modal forms included — in ui-check.config.json. Copy templates/ui-check/ into the app.
import { expect, test } from "@playwright/test";
import { spawnSync } from "node:child_process";
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
  /** Where visual scores are recorded (scripts/visual_compare.py --record); default docs/evidence/visual. */
  visualDir?: string;
  /** Points of layout match (edge overlap) a window may lose against its last recorded score; default 2. */
  visualTolerance?: number;
  /** Scores every window must reach, also on its first record; default { pixel: 90, edge: 60 }. */
  visualFloor?: { pixel: number; edge: number };
  windows: Record<string, WindowConfig & { captionIgnore?: Record<string, string> }>;
};

const root = process.cwd();
const config: Config = JSON.parse(readFileSync(join(root, "ui-check.config.json"), "utf-8"));
const latestPath = join(root, "analysis-local", "latest.json");
const latest: { inspect?: string; dossier?: string } = existsSync(latestPath) ? JSON.parse(readFileSync(latestPath, "utf-8")) : {};
config.inspectDir ??= latest.inspect;
config.dossierDir ??= latest.dossier;
config.legacyScreenshots ??= "docs/evidence/images";
config.visualDir ??= "docs/evidence/visual";
for (const [key, path] of Object.entries({ inspectDir: config.inspectDir, dossierDir: config.dossierDir,
  legacyScreenshots: config.legacyScreenshots })) {
  // Evidence of another checkout would be compared silently: every path stays inside this repository.
  if (path && !resolve(root, path).startsWith(root)) throw new Error(`${key} points outside the repository: ${path}`);
}

type Score = { pixel_similarity: number; edge_overlap: number };
const legacyImage = (window: string) =>
  [`${window}.png`, `${window}.jpg`, join(window, "screenshot.png")]
    .map((name) => resolve(root, config.legacyScreenshots!, name))
    .find((path) => existsSync(path));

/** Score the new screenshot against the legacy image and record it; returns [score, previous score]. */
function visualScore(window: string, screenshot: string): [Score | null, Score | null] {
  const legacy = legacyImage(window);
  if (!legacy) return [null, null];
  const record = resolve(root, config.visualDir!, `${window}.json`);
  const previous: Score | null = existsSync(record) ? JSON.parse(readFileSync(record, "utf-8")) : null;
  // scripts/py.mjs finds python3 (macOS, Linux) or py (Windows).
  const run = spawnSync("node", ["scripts/py.mjs", "scripts/visual_compare.py", legacy, screenshot,
    "--out", resolve(root, config.report, `${window}.compare.png`), "--record", record], { cwd: root, encoding: "utf-8" });
  if (run.status !== 0) throw new Error(`visual_compare.py failed for ${window}: ${run.stderr}`);
  return [JSON.parse(run.stdout), previous];
}
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
const results: { window: string; missing: string[]; ignored: number; total: number; captions: Mismatch[]; score: Score | null }[] = [];

for (const [window, settings] of Object.entries(config.windows)) {
  test(`${window}: legacy controls present`, async ({ page }) => {
    // A missing skin image or icon renders as a blank: every request must succeed.
    const failed: string[] = [];
    page.on("requestfailed", (request) => failed.push(request.url()));
    page.on("response", (response) => { if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`); });
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
      // An edit's caption is its associated <label> (or aria-label); a button's or static's is its own text.
      const actual = await element.evaluate((el) => {
        const labels = (el as HTMLInputElement).labels;
        const label = labels && labels.length ? Array.from(labels).map((l) => l.innerText).join(" ") : "";
        return label || el.getAttribute("aria-label") || (el as HTMLElement).innerText || "";
      });
      if (!normalize(actual).includes(normalize(legacy))) captions.push({ name, legacy, actual: actual.trim() });
    }
    mkdirSync(resolve(root, config.report), { recursive: true });
    const screenshot = resolve(root, config.report, `${window}.png`);
    await view.screenshot({ path: screenshot });
    const [score, previous] = visualScore(window, screenshot);
    results.push({ window, missing, ignored: Object.keys(settings.ignore).length, total: expected.length, captions, score });
    expect(missing, `legacy controls with no data-testid in ${window}`).toEqual([]);
    expect(captions, `captions differing from the legacy dossier in ${window}`).toEqual([]);
    // Dev servers answer a missing file with the app's HTML (200): fetch every image the window uses and check it is one.
    const images = await view.evaluate((root) => {
      const urls = new Set<string>();
      for (const el of [root, ...Array.from(root.querySelectorAll("*"))]) {
        if (el instanceof HTMLImageElement && el.src) urls.add(el.src);
        const style = getComputedStyle(el);
        for (const value of [style.backgroundImage, style.borderImageSource]) {
          for (const match of value.matchAll(/url\("?([^")]+)"?\)/g)) urls.add(new URL(match[1], location.href).href);
        }
      }
      return [...urls];
    });
    for (const url of images) {
      const response = await page.request.get(url);
      if (!response.ok() || !(response.headers()["content-type"] ?? "").startsWith("image/")) failed.push(url);
    }
    expect(failed, `images or requests that failed while showing ${window}`).toEqual([]);
    const floor = config.visualFloor ?? { pixel: 90, edge: 60 };
    if (score) {
      expect(score.pixel_similarity, `${window}: pixel similarity below the floor`).toBeGreaterThanOrEqual(floor.pixel);
      expect(score.edge_overlap, `${window}: layout match below the floor`).toBeGreaterThanOrEqual(floor.edge);
    }
    if (score && previous) {
      expect(score.edge_overlap, `${window} looks less like the legacy screen than last time`)
        .toBeGreaterThanOrEqual(previous.edge_overlap - (config.visualTolerance ?? 2));
    }
  });
}

test.afterAll(() => {
  const rows = results.map((r) => {
    const legacy = legacyImage(r.window) ?? "";
    const legacyCell = legacy ? `<img src="file://${legacy}">` : "<em>no legacy screenshot yet</em>";
    return `<tr><td><b>${r.window}</b><br>${r.total - r.missing.length}/${r.total} controls, ${r.ignored} ignored` +
      `${r.missing.length ? `<br>missing: ${r.missing.join(", ")}` : ""}` +
      `${r.captions.map((c) => `<br>${c.name}: “${c.actual}” ≠ legacy “${c.legacy}”`).join("")}` +
      `${r.score ? `<br>looks like the original: layout ${r.score.edge_overlap} %, pixels ${r.score.pixel_similarity} %` : ""}</td>` +
      `<td><img src="${r.window}.png"></td><td>${legacyCell}</td></tr>`;
  });
  writeFileSync(resolve(root, config.report, "index.html"),
    `<!doctype html><meta charset="utf-8"><title>UI parity report</title><style>img{max-width:560px;border:1px solid #ccc}` +
    `td{vertical-align:top;padding:8px}</style><table><tr><th>Window</th><th>New</th><th>Legacy</th></tr>${rows.join("")}</table>`);
});
