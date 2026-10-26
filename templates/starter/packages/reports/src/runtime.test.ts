import { afterAll, beforeAll, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { chmod, cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { createRequire } from "node:module";
import { chromium } from "playwright-core";
import { createReportRenderer, loadReportAssets } from "./renderer";
import { createConfiguredReportRenderer, validateReportRuntimeConfiguration, type ReportRuntimeConfiguration } from "./runtime";

const require = createRequire(import.meta.url);
const executablePath = process.env.REPORT_TEST_EXECUTABLE ?? (process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  : process.platform === "win32" ? join(process.env.PROGRAMFILES ?? "C:\\Program Files", "Google", "Chrome", "Application", "chrome.exe") : "/opt/google/chrome/chrome");
let folder: string, configuration: ReportRuntimeConfiguration;
beforeAll(async () => {
  folder = await mkdtemp(join(tmpdir(), "migration-report-runtime-"));
  const sha256 = createHash("sha256").update(await readFile(executablePath)).digest("hex"), browser = await chromium.launch({ executablePath, headless: true });
  try { configuration = { executablePath, sha256, version: browser.version() }; } finally { await browser.close(); }
}, 60_000);
afterAll(async () => { if (folder) await rm(folder, { recursive: true, force: true }); });

function errorCode(promise: Promise<unknown>, code: string) {
  return expect(promise).rejects.toMatchObject({ name: "ReportRuntimeConfigurationError", code, message: `Report runtime configuration failed (${code})` });
}
const report = { reportId: "runtime-smoke", html: "<h1>RUNTIME AÇÃO</h1><p>9007199254740993</p>", css: "@page{size:A4;margin:20mm;}body{font-family:ReportSans;}h1{font-weight:700;}" };

it("undefined configuration explicitly leaves rendering unavailable without looking up environment or browser caches", async () => {
  expect(await createConfiguredReportRenderer()).toBeUndefined();
});

it("explicit complete pins accept platform absolute paths and normalize only the hexadecimal fingerprint", () => {
  expect(validateReportRuntimeConfiguration({ ...configuration, sha256: configuration.sha256.toUpperCase() })).toEqual(configuration);
  expect(validateReportRuntimeConfiguration({ ...configuration, executablePath: "C:\\Runtime With Spaces\\chrome.exe" }, "win32").executablePath).toBe("C:\\Runtime With Spaces\\chrome.exe");
  expect(validateReportRuntimeConfiguration({ ...configuration, executablePath: "/Applications/Offline Runtime.app/Contents/MacOS/Chrome" }, "darwin").executablePath).toContain("Offline Runtime.app");
  expect(() => validateReportRuntimeConfiguration({ ...configuration, executablePath: "\\\\network\\share\\chrome.exe" }, "win32")).toThrow("(configuration)");
});

it("partial/unknown settings, relative URLs, NUL and invalid pins fail with fixed diagnostics", async () => {
  for (const input of [null, [], {}, { ...configuration, sha256: "private-invalid-hash" }, { ...configuration, version: "156" },
    { ...configuration, sha256: undefined }, { ...configuration, arbitrary: "value" },
    { ...configuration, executablePath: "relative/chrome" }, { ...configuration, executablePath: "https://example.invalid/chrome" },
    { ...configuration, executablePath: executablePath + "\0" }]) {
    expect(() => validateReportRuntimeConfiguration(input)).toThrow("Report runtime configuration failed (configuration)");
    await errorCode(createConfiguredReportRenderer(input as ReportRuntimeConfiguration), "configuration");
  }
});

it("missing, directory and non-executable paths fail without switching to an installed browser", async () => {
  await errorCode(createConfiguredReportRenderer({ ...configuration, executablePath: join(folder, "missing-private-location") }), "executable");
  await errorCode(createConfiguredReportRenderer({ ...configuration, executablePath: folder }), "executable");
  if (process.platform !== "win32") {
    const noExecute = join(folder, "no-execute"); await writeFile(noExecute, "not a browser", { mode: 0o600 });
    await errorCode(createConfiguredReportRenderer({ ...configuration, executablePath: noExecute }), "executable");
  }
});

it("fingerprint/version mismatches and failed launch cannot silently become another browser", async () => {
  const sha256 = (configuration.sha256[0] === "0" ? "1" : "0") + configuration.sha256.slice(1);
  await errorCode(createConfiguredReportRenderer({ ...configuration, sha256 }), "fingerprint");
  await errorCode(createConfiguredReportRenderer({ ...configuration, version: "0.0.0.0" }), "version");
  const invalid = join(folder, process.platform === "win32" ? "invalid-browser.exe" : "invalid-browser");
  await writeFile(invalid, "not a browser"); await chmod(invalid, 0o700);
  await errorCode(createConfiguredReportRenderer({ ...configuration, executablePath: invalid, sha256: createHash("sha256").update(await readFile(invalid)).digest("hex") }), "launch");
}, 60_000);

it("installed assets require exact packages, valid regular/bold WOFF2 bytes and retained dependency notices", async () => {
  const assets = await loadReportAssets();
  for (const value of [assets.fontRegular, assets.fontBold]) expect(Buffer.from(value, "base64").toString("ascii", 0, 4)).toBe("wOF2");
  expect(assets.notices).toContain("SIL OPEN FONT LICENSE"); expect(assets.notices).toContain("MIT License");
  const modules = join(folder, "modules"), paged = join(modules, "pagedjs"), fonts = join(modules, "@fontsource", "noto-sans");
  await mkdir(join(paged, "dist"), { recursive: true }); await mkdir(join(fonts, "files"), { recursive: true });
  const pagedRoot = resolve(dirname(require.resolve("pagedjs")), ".."), fontRoot = dirname(require.resolve("@fontsource/noto-sans/package.json"));
  for (const file of ["package.json", "LICENSE.md", "dist/paged.js"]) await cp(join(pagedRoot, file), join(paged, file));
  for (const file of ["package.json", "LICENSE", "files/noto-sans-latin-400-normal.woff2", "files/noto-sans-latin-700-normal.woff2"]) await cp(join(fontRoot, file), join(fonts, file));
  await writeFile(join(paged, "package.json"), '{"version":"0.0.0"}');
  await expect(loadReportAssets(modules)).rejects.toThrow("Report asset version mismatch");
  await writeFile(join(paged, "package.json"), '{"version":"0.4.3"}');
  await writeFile(join(fonts, "files/noto-sans-latin-700-normal.woff2"), "broken font");
  await expect(loadReportAssets(modules)).rejects.toThrow("Report font invalid");
  await rm(join(fonts, "files/noto-sans-latin-700-normal.woff2")); await expect(loadReportAssets(modules)).rejects.toThrow();
});

it("the explicitly provisioned executable produces offline PDF bytes and later version/executable failures release the engine", async () => {
  const render = await createConfiguredReportRenderer(configuration); expect(render).toBeTypeOf("function");
  const result = await render!(report); expect(result.kind).toBe("rendered");
  if (result.kind !== "rendered") throw new Error("Synthetic runtime did not render");
  expect(Buffer.from(result.pdfBase64, "base64").subarray(0, 5).toString()).toBe("%PDF-");
  expect(result.html).toContain("RUNTIME AÇÃO"); expect(result.html).not.toContain("<script");
  const mismatched = createReportRenderer({ executablePath, expectedVersion: "0.0.0.0" });
  expect(await mismatched(report)).toEqual({ kind: "unavailable" }); expect(await mismatched(report)).toEqual({ kind: "unavailable" });
  expect(await createReportRenderer({ executablePath: join(folder, "missing-after-startup"), expectedVersion: configuration.version })(report)).toEqual({ kind: "failed" });
}, 60_000);
