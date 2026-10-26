# Portable fixed reports

`@windev-migration/reports` is a private source TypeScript workspace package. It contains a fixed-report HTML/CSS adapter and one Paged.js/Chromium rendering engine. Application report IDs, source definitions, queries, authorization, grouping, calculations and data are supplied by the consumer.

```ts
import { fixedReportDocument, paperSize, createConfiguredReportRenderer } from "@windev-migration/reports";

const document = fixedReportDocument({
  reportId: "synthetic-list",
  layout: {
    paper: paperSize("A4"), widthMm: 170,
    marginsMm: { top: 20, right: 20, bottom: 20, left: 20 },
    header: { name: "heading", heightMm: 8, controls: [
      { name: "title", xMm: 0, widthMm: 170, heightMm: 8, field: "title" },
    ] },
    detail: { name: "detail", heightMm: 6, controls: [
      { name: "description", xMm: 0, widthMm: 170, heightMm: 6, field: "description" },
    ] },
    footer: { heightMm: 6, pageNumber: { xMm: 0, widthMm: 20, heightMm: 6 } },
  },
  values: { title: "Synthetic list" },
  rows: [{ description: "9007199254740993 — AÇÃO" }],
});
// Provision these exact pins explicitly on the API host. There is no download or fallback.
const render = await createConfiguredReportRenderer({ executablePath, sha256, version });
const result = await render!(document);
```

Use `@windev-migration/reports/geometry` for pure template construction without loading Node/browser modules. Controls bind an exact field name or an explicit `text` literal. NULL/missing values display blank. Values, control names and band names are HTML-escaped; whitespace and large numeric strings remain intact. Do all arithmetic before constructing the document using the application's accepted exact representation.

Set `autoHeight` only when the source supports growing text. Intersecting control rectangles share a flow section; later sections move below growing content. A single growing control marked `divisible` may span pages. An indivisible block exceeding the printable page returns `unresolved`, never a clipped success. `band`, `intrinsicBand`, `renderBand`, `pageHeaderCss` and `reportBodyCss` are exported for explicit grouped/custom assembly. The caller owns group order, headers, totals and counters.

`createReportRenderer({ channel: "chrome" })` is an explicit development option using installed Chrome. Production uses the configured executable, SHA-256 and exact browser version. Startup validates fingerprint/version/assets; each render checks browser version again and owns/closes its process. Configuration diagnostics contain fixed codes. One renderer accepts one active render; competing calls return `unavailable`. No browser is shared with application startup.

The adapter accepts trusted application HTML/CSS; it is not a general HTML sanitizer. Construct data through the escaped helpers. Network requests and service workers are blocked. Paged.js produces an immutable offline HTML snapshot with embedded fonts and CSP, and Chromium prints that snapshot. There is no native printer adapter. Tests establish browser/PDF behavior; desktop dialogs, print handlers and physical printers need separate platform acceptance.

Pinned dependencies are Paged.js 0.4.3 (MIT), Playwright 1.64.1 (Apache-2.0) and Noto Sans 5.3.0 Latin (OFL-1.1). Assets load from installed packages, never a CDN. Paged.js/font license notices are retained in the HTML artifact; dependency licenses remain in the installed packages. Latin glyph coverage is explicit; additional languages/fonts require a separately reviewed asset configuration.

Synthetic tests exercise real Chromium pagination/PDFs, headers, counters, margins, orientation, empty reports, exact rows, long flow, overflow, network blocking, embedded fonts, runtime pins and owned-process cleanup. PDF inspection uses the starter's pinned Python `pypdf` through `PYTHON` (or the platform Python executable). `REPORT_TEST_EXECUTABLE` selects an explicit test browser; no legacy data, application source assets or credentials are required.
