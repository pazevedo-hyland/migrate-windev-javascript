import { afterAll, beforeAll, expect, it, vi } from "vitest";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, type Browser } from "playwright-core";
import { createReportRenderer, loadReportAssets } from "./renderer";
import { fixedReportDocument, paperSize, type ReportLayout, type PaperSize } from "./geometry";
import type { ReportDocument, ReportRenderResult } from "./contracts";

const executablePath = process.env.REPORT_TEST_EXECUTABLE ?? (process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  : process.platform === "win32" ? join(process.env.PROGRAMFILES ?? "C:\\Program Files", "Google", "Chrome", "Application", "chrome.exe") : "/opt/google/chrome/chrome");
let version: string;
beforeAll(async () => {
  const browser = await chromium.launch({ executablePath, headless: true });
  try { version = browser.version(); } finally { await browser.close(); }
}, 60_000);
afterAll(() => vi.restoreAllMocks());
function renderer() { return createReportRenderer({ executablePath, expectedVersion: version }); }
type PdfPage = { text: string; widthMm: number; heightMm: number; embeddedFonts: number; runs: { text: string; xMm: number; yMm: number }[] };
function pdf(result: ReportRenderResult): { rendered: Extract<ReportRenderResult, { kind: "rendered" }>; pages: PdfPage[] } {
  expect(result.kind).toBe("rendered"); if (result.kind !== "rendered") throw new Error("Synthetic report failed");
  const pages = JSON.parse(execFileSync(process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3"),
    [fileURLToPath(new URL("../test-support/pdf-info.py", import.meta.url))], { input: Buffer.from(result.pdfBase64, "base64"), encoding: "utf8" })) as PdfPage[];
  expect(pages).toHaveLength(result.pageCount); return { rendered: result, pages };
}
function layout(paper: PaperSize = paperSize("A4")): ReportLayout {
  const widthMm = paper.widthMm - 32;
  return { paper, widthMm, marginsMm: { top: 17, right: 19, bottom: 23, left: 13 },
    header: { name: "header", heightMm: 8, controls: [{ name: "heading", xMm: 0, widthMm, heightMm: 8, text: "SYNTHETIC HEADER" }] },
    detail: { name: "detail", heightMm: 6, controls: [{ name: "row", xMm: 0, widthMm, heightMm: 6, field: "label" }] },
    end: { name: "end", heightMm: 8, controls: [{ name: "total", xMm: 0, widthMm, heightMm: 8, field: "total", autoHeight: true }] },
    footer: { heightMm: 6, pageNumber: { xMm: 0, widthMm: 20, heightMm: 6 } },
  };
}
function document(rows: number, sourceLayout = layout()): ReportDocument {
  return fixedReportDocument({ reportId: "synthetic-list", layout: sourceLayout, language: "pt", unresolved: ["synthetic-open-question"],
    values: { total: `FINAL TOTAL ${rows}` }, rows: Array.from({ length: rows }, (_, index) => ({ label: `ROW_${String(index + 1).padStart(4, "0")} AÇÃO 9007199254740993` })) });
}

it("actual pagination preserves 120 exact rows, repeated headers, counters, final totals and the immutable offline artifact", async () => {
  const result = pdf(await renderer()(document(120))), text = result.pages.map(page => page.text).join("\n");
  expect(result.pages.length).toBeGreaterThan(1);
  for (let index = 1; index <= 120; index++) expect(text.match(new RegExp(`ROW_${String(index).padStart(4, "0")}\\b`, "g")), String(index)).toHaveLength(1);
  for (const [index, page] of result.pages.entries()) {
    expect(page.text).toContain("SYNTHETIC HEADER"); expect(page.text).toContain(`${index + 1}/${result.pages.length}`);
    expect(page.widthMm).toBeCloseTo(210, 0); expect(page.heightMm).toBeCloseTo(297, 0);
  }
  expect(result.pages.at(-1)!.text).toContain("FINAL TOTAL 120");
  expect(result.rendered.unresolved).toEqual(["synthetic-open-question"]);
  expect(result.rendered.html).toContain("Content-Security-Policy"); expect(result.rendered.html).toContain("SIL OPEN FONT LICENSE");
  expect(result.rendered.html).toContain("data:font/woff2;base64,"); expect(result.rendered.html).not.toContain("<script");
  expect(/<main\b[^>]*\sid="source"/.test(result.rendered.html)).toBe(false); expect(result.rendered.html).toContain('lang="pt"');
}, 90_000);

it("empty real PDFs retain independent margins and literal A4/A5/Letter dimensions in both orientations", async () => {
  for (const [name, orientation] of [["A4", "portrait"], ["A5", "portrait"], ["Letter", "portrait"], ["A4", "landscape"]] as const) {
    const paper = paperSize(name, orientation), result = pdf(await renderer()(document(0, layout(paper))));
    expect(result.pages).toHaveLength(1); const page = result.pages[0];
    expect(page.widthMm).toBeCloseTo(paper.widthMm, 0); expect(page.heightMm).toBeCloseTo(paper.heightMm, 0);
    expect(page.text).toContain("SYNTHETIC HEADER"); expect(page.text).toContain("FINAL TOTAL 0"); expect(page.text).toContain("1/1");
    expect(page.text).not.toContain("ROW_");
    const header = page.runs.find(run => run.text.includes("SYNTHETIC HEADER")); expect(header).toBeDefined();
    expect(header!.xMm).toBeGreaterThanOrEqual(12.9); expect(header!.xMm).toBeLessThan(15);
    // The print snapshot must not apply @page:first margins for a second time.
    const top = page.heightMm - header!.yMm; expect(top).toBeGreaterThanOrEqual(17); expect(top).toBeLessThan(25);
  }
}, 90_000);

it("intrinsic long text moves later fields and the final total without losing lines in the actual PDF", async () => {
  const sourceLayout = layout(), lines = Array.from({ length: 18 }, (_, index) => `LONG_${String(index + 1).padStart(2, "0")}`);
  sourceLayout.detail = { name: "growing", heightMm: 20, controls: [
    { name: "long", xMm: 0, widthMm: sourceLayout.widthMm, heightMm: 6, autoHeight: true, field: "label" },
    { name: "later", xMm: 0, yMm: 10, widthMm: sourceLayout.widthMm, heightMm: 6, text: "LATER FIELD" },
  ] };
  const report = fixedReportDocument({ reportId: "growing", layout: sourceLayout, rows: [{ label: lines.join("\r\n") }], values: { total: "FINAL AFTER LONG" } });
  const { pages } = pdf(await renderer()(report)), text = pages.map(page => page.text).join("\n");
  for (const line of lines) expect(text).toContain(line);
  expect(text.indexOf("LATER FIELD")).toBeGreaterThan(text.indexOf(lines.at(-1)!));
  expect(text.indexOf("FINAL AFTER LONG")).toBeGreaterThan(text.indexOf("LATER FIELD"));
}, 60_000);

it("an oversized indivisible block stays unresolved while explicitly divisible final content spans real pages", async () => {
  const sourceLayout = layout(), lines = Array.from({ length: 160 }, (_, index) => `FLOW_${String(index + 1).padStart(3, "0")}`);
  sourceLayout.end = { name: "long-end", heightMm: 8, controls: [{ name: "total", xMm: 0, widthMm: sourceLayout.widthMm, heightMm: 8, field: "total", autoHeight: true }] };
  const report = fixedReportDocument({ reportId: "flow", layout: sourceLayout, rows: [], values: { total: lines.join("\r\n") } });
  expect(await renderer()(report)).toEqual({ kind: "unresolved", unresolved: ["Indivisible report content exceeds the printable page"] });
  const divisible = structuredClone(sourceLayout); divisible.end!.controls = divisible.end!.controls.map(control => ({ ...control, divisible: true }));
  const { pages } = pdf(await renderer()(fixedReportDocument({ reportId: "flow", layout: divisible, rows: [], values: { total: lines.join("\r\n") } })));
  expect(pages.length).toBeGreaterThan(1); const text = pages.map(page => page.text).join("\n");
  for (const line of lines) expect(text.match(new RegExp(`${line}\\b`, "g")), line).toHaveLength(1);
}, 90_000);

it("the owned Chromium context blocks remote media and embeds actual regular and bold fonts", async () => {
  let requests = 0;
  const server = createServer((_request, response) => { requests++; response.end("unexpected network access"); });
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  try {
    const address = server.address(); if (!address || typeof address === "string") throw new Error("Synthetic server unavailable");
    const report: ReportDocument = { reportId: "offline", html: `<h1>OFFLINE — AÇÃO</h1><p>9007199254740993</p><img src="http://127.0.0.1:${address.port}/blocked.png">`,
      css: "@page{size:A4;margin:20mm;}body{font-family:ReportSans;}h1{font-weight:700;}p{font-weight:400;}" };
    const { pages } = pdf(await renderer()(report));
    expect(requests).toBe(0); expect(pages[0].text).toContain("OFFLINE — AÇÃO"); expect(pages[0].embeddedFonts).toBeGreaterThanOrEqual(2);
  } finally { await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
}, 60_000);

it("busy/lazy-asset failure paths release renderer state and owned browsers close after pagination failure", async () => {
  let rejectAssets!: (error: Error) => void;
  const assets = new Promise<Awaited<ReturnType<typeof loadReportAssets>>>((_resolve, reject) => { rejectAssets = reject; });
  const render = createReportRenderer({ executablePath, expectedVersion: version, assets });
  const first = render(document(0)); expect(await render(document(0))).toEqual({ kind: "unavailable" });
  rejectAssets(new Error("synthetic asset failure")); expect(await first).toEqual({ kind: "failed" });
  expect(await render(document(0))).toEqual({ kind: "failed" });
  const launch = chromium.launch.bind(chromium), owned: Browser[] = [], closes: ReturnType<typeof vi.spyOn>[] = [];
  const spy = vi.spyOn(chromium, "launch").mockImplementation(async options => { const browser = await launch(options); owned.push(browser); closes.push(vi.spyOn(browser, "close")); return browser; });
  try {
    const files = await loadReportAssets();
    const failed = createReportRenderer({ executablePath, expectedVersion: version, assets: Promise.resolve({ ...files, pagedScript: "throw new Error('synthetic pagination failure')" }) });
    expect(await failed(document(0))).toEqual({ kind: "failed" });
    expect(owned).toHaveLength(1); expect(closes[0]).toHaveBeenCalledOnce(); expect(owned[0].isConnected()).toBe(false);
  } finally { spy.mockRestore(); for (const browser of owned) await browser.close(); }
}, 60_000);
