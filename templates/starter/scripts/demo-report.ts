import { mkdir, writeFile } from "node:fs/promises";
import { createReportRenderer, fixedReportDocument, paperSize } from "@windev-migration/reports";

// Explicit development opt-in. Production must pin executable path, SHA256 and version.
const render = createReportRenderer({ channel: "chrome" });
const document = fixedReportDocument({
  reportId: "synthetic-directory", language: "en-GB",
  layout: {
    paper: paperSize("A4", "portrait"), widthMm: 180, marginsMm: { top: 12, right: 15, bottom: 12, left: 15 },
    header: { name: "header", heightMm: 14, controls: [{ name: "title", xMm: 0, widthMm: 180, heightMm: 12, text: "Synthetic directory" }] },
    detail: { name: "detail", heightMm: 8, controls: [{ name: "entry", xMm: 0, widthMm: 180, heightMm: 8, field: "name" }] },
    footer: { heightMm: 8, pageNumber: { xMm: 160, widthMm: 20, heightMm: 8 } },
  },
  rows: Array.from({ length: 120 }, (_, index) => ({ name: `Synthetic entry ${index + 1}` })),
});
await mkdir("analysis-local", { recursive: true });
const rendered = await render(document);
if (rendered.kind !== "rendered") throw new Error(`Report not rendered: ${JSON.stringify(rendered)}`);
await writeFile("analysis-local/directory.pdf", Buffer.from(rendered.pdfBase64, "base64"));
await writeFile("analysis-local/directory.html", rendered.html);
console.log(`Wrote analysis-local/directory.pdf and directory.html (${rendered.pageCount} pages, synthetic data).`);
