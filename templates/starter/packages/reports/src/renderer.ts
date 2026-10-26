import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { chromium, type Browser } from "playwright-core";
import type { ReportRenderer } from "./contracts";
import { escapeReportText } from "./geometry";

const require = createRequire(import.meta.url);
export type ReportAssets = { pagedScript: string; fontRegular: string; fontBold: string; notices: string };
/** Resolve only installed, pinned package assets; no CDN, user path or remote font. */
export async function loadReportAssets(moduleDirectory?: string): Promise<ReportAssets> {
  const modulePath = (name: string) => moduleDirectory ? resolve(moduleDirectory, name) : dirname(require.resolve(`${name}/package.json`));
  // pagedjs0.4.3's exports omit package.json, so resolve its installed CJS entry first.
  const pagedRoot = moduleDirectory ? resolve(moduleDirectory, "pagedjs") : resolve(dirname(require.resolve("pagedjs")), "..");
  const fontRoot = modulePath("@fontsource/noto-sans");
  const [pagedScript, regular, bold, pagedLicense, fontLicense] = await Promise.all([
    readFile(resolve(pagedRoot, "dist/paged.js"), "utf8"),
    readFile(resolve(fontRoot, "files/noto-sans-latin-400-normal.woff2")),
    readFile(resolve(fontRoot, "files/noto-sans-latin-700-normal.woff2")),
    readFile(resolve(pagedRoot, "LICENSE.md"), "utf8"), readFile(resolve(fontRoot, "LICENSE"), "utf8"),
  ]);
  const [pagedPackage, fontPackage, playwrightPackage] = await Promise.all([
    readFile(resolve(pagedRoot, "package.json"), "utf8"), readFile(resolve(fontRoot, "package.json"), "utf8"), readFile(require.resolve("playwright-core/package.json"), "utf8"),
  ]);
  if (JSON.parse(pagedPackage).version !== "0.4.3" || JSON.parse(fontPackage).version !== "5.3.0" || JSON.parse(playwrightPackage).version !== "1.64.1") throw new Error("Report asset version mismatch");
  for (const font of [regular, bold]) if (font.length < 48 || font.toString("ascii", 0, 4) !== "wOF2" || font.readUInt32BE(8) !== font.length) throw new Error("Report font invalid");
  return { pagedScript, fontRegular: regular.toString("base64"), fontBold: bold.toString("base64"), notices: pagedLicense + "\n" + fontLicense };
}
export type ReportRendererOptions = { assets?: Promise<ReportAssets> } & (
  { channel: "chrome" | "chromium"; executablePath?: never; expectedVersion?: never }
  | { channel?: never; executablePath: string; expectedVersion: string }
);

/** One existing Chromium stack; it owns pagination, fonts, text shaping and PDF creation.
 * Host-installed Chrome is an initial development prerequisite, not a packaged-runtime promise.
 */
export function createReportRenderer(options: ReportRendererOptions): ReportRenderer {
  const assets = options.assets ?? loadReportAssets();
  // Avoid an unhandled failed lazy asset read before the first request.
  void assets.catch(() => undefined);
  let rendering = false;
  return async report => {
    if (rendering) return { kind: "unavailable" };
    rendering = true;
    let browser: Browser | undefined;
    try {
      const files = await assets;
      browser = await chromium.launch(options.executablePath === undefined
        ? { channel: options.channel, headless: true }
        : { executablePath: options.executablePath, headless: true });
      // A provisioned browser that changes after startup cannot silently change the report runtime.
      if (options.expectedVersion !== undefined && browser.version() !== options.expectedVersion) return { kind: "unavailable" };
      const context = await browser.newContext({ serviceWorkers: "block" });
      await context.route("**/*", route => route.abort());
      const page = await context.newPage();
      page.setDefaultTimeout(30_000);
      const language = escapeReportText(report.language ?? "en");
      await page.setContent(`<!doctype html><html lang="${language}"><head><meta charset="utf-8"></head><body><main id="source"></main><main id="pages"></main></body></html>`);
      await page.addScriptTag({ content: files.pagedScript });
      const css = `@font-face{font-family:ReportSans;src:url(data:font/woff2;base64,${files.fontRegular}) format('woff2');font-weight:400;}\n`
        + `@font-face{font-family:ReportSans;src:url(data:font/woff2;base64,${files.fontBold}) format('woff2');font-weight:700;}\n` + report.css;
      // Real font loading must finish before Paged.js measures source bands.
      await page.addStyleTag({ content: css });
      const overflow = await page.evaluate(async ({ html, stylesheet }) => {
        const source = document.querySelector("#source")!;
        source.innerHTML = html;
        await document.fonts.load("8pt ReportSans");
        await document.fonts.load("700 16pt ReportSans");
        await document.fonts.ready;
        const report = source.querySelector<HTMLElement>("[data-report-page-height]");
        if (report) {
          const capacity = document.createElement("div");
          capacity.style.height = `${report.dataset.reportPageHeight}mm`; source.append(capacity);
          const height = capacity.getBoundingClientRect().height; capacity.remove();
          // The browser measures intrinsic text and actual CSS millimetres after fonts load.
          // Never clip an evidenced indivisible source block to manufacture a successful PDF.
          if ([...report.querySelectorAll("[data-report-indivisible]")].some(block => block.getBoundingClientRect().height > height + 0.5)) return true;
        }
        const api = window as unknown as { Paged: { Previewer: new () => { preview(source: Element, styles: Record<string, string>[], target: Element): Promise<{ total: number }> } } };
        const previewer = new api.Paged.Previewer();
        const result = await Promise.race([
          previewer.preview(source, [{ "report.css": stylesheet }], document.querySelector("#pages")!),
          new Promise<never>((_, reject) => setTimeout(() => reject(new Error("Report pagination timeout")), 30_000)),
        ]);
        document.documentElement.dataset.reportPages = String(result.total);
        if (report) {
          for (const block of document.querySelectorAll("#pages [data-report-indivisible]")) {
            const area = block.closest(".pagedjs_area"), rect = block.getBoundingClientRect();
            if (!area) return true;
            const bounds = area.getBoundingClientRect();
            if (rect.top < bounds.top - 0.5 || rect.bottom > bounds.bottom + 0.5) return true;
          }
        }
        source.remove();
        return null;
      }, { html: report.html, stylesheet: css });
      if (overflow) return { kind: "unresolved", unresolved: ["Indivisible report content exceeds the printable page"] };
      const snapshot = await page.evaluate(() => {
        const rules = Array.from(document.styleSheets).flatMap(sheet => Array.from(sheet.cssRules));
        // Paged.js has already materialized source margins/headers into each page.
        // Its final @page owns physical paper size and zero print margins. Retaining
        // source pseudo-page rules would add a second first-page margin in Chromium.
        const physicalPage = rules.filter(rule => rule.type === CSSRule.PAGE_RULE).at(-1) as CSSPageRule | undefined;
        if (!physicalPage?.style.getPropertyValue("size") || physicalPage.style.margin !== "0px") throw new Error("Report physical page rule missing");
        const styles = rules.filter(rule => rule.type !== CSSRule.PAGE_RULE).map(rule => rule.cssText).concat(physicalPage.cssText).join("\n");
        return { pages: Number(document.documentElement.dataset.reportPages), styles, content: document.querySelector("#pages")!.innerHTML,
          fontReady: document.fonts.check("8pt ReportSans") && document.fonts.check("700 16pt ReportSans") };
      });
      if (!snapshot.fontReady || !Number.isInteger(snapshot.pages) || snapshot.pages < 1) return { kind: "failed" };
      // Retain copyright/license notices within the offline artifact; no script in the preview.
      const notices = files.notices.replaceAll("--", "—");
      const html = `<!doctype html><html lang="${language}"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:"><style>${snapshot.styles}</style></head><body>${snapshot.content}<!--${notices}--></body></html>`;
      // Print exactly the immutable offline preview document. This also removes Paged.js's
      // measurement/source DOM and transient stylesheet state from Chromium's print context.
      const pdfPage = await context.newPage();
      await pdfPage.setContent(html);
      await pdfPage.evaluate(() => document.fonts.ready);
      const pdf = await pdfPage.pdf({ preferCSSPageSize: true, printBackground: true });
      return { kind: "rendered", reportId: report.reportId, html, pdfBase64: pdf.toString("base64"), pageCount: snapshot.pages, unresolved: [...report.unresolved ?? []] };
    } catch { return { kind: "failed" }; }
    finally { try { await browser?.close(); } catch { /* The owned process may already have exited. */ } finally { rendering = false; } }
  };
}
