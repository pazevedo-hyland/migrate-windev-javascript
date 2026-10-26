import { expect, it } from "vitest";
import { band, fixedReportDocument, intrinsicBand, paperSize, renderBand, type ReportLayout } from "./geometry";

const layout: ReportLayout = {
  paper: paperSize("A4"), widthMm: 170, marginsMm: { top: 20, right: 20, bottom: 20, left: 20 },
  detail: { name: "detail", heightMm: 6, controls: [{ name: "value", xMm: 0, widthMm: 170, heightMm: 6, field: "value" }] },
};

it("binds only explicit fields, displays NULL/missing blank and escapes data and metadata without normalizing text", () => {
  const definition = { name: 'band"<>', heightMm: 6, controls: [
    { name: 'field"<>', xMm: 0, widthMm: 50, heightMm: 6, field: "value" },
    { name: "null", xMm: 50, widthMm: 20, heightMm: 6, field: "nil" },
    { name: "missing", xMm: 70, widthMm: 20, heightMm: 6, field: "absent" },
    { name: "literal", xMm: 90, widthMm: 20, heightMm: 6, text: "Literal &" },
    { name: "hidden", xMm: 110, widthMm: 20, heightMm: 6, text: "HIDDEN", visible: false },
  ] };
  const html = renderBand(definition, { value: "  AÇÃO <script>\r\n9007199254740993 & ' \"  ", nil: null });
  expect(html).toContain('data-band="band&quot;&lt;&gt;"');
  expect(html).toContain('data-control="field&quot;&lt;&gt;"');
  expect(html).toContain("  AÇÃO &lt;script&gt;\r\n9007199254740993 &amp; &#39; &quot;  ");
  expect(html).toContain("Literal &amp;"); expect(html).not.toContain("HIDDEN"); expect(html).not.toContain("undefined");
});

it("growing intersecting controls keep offsets and gaps while only explicit divisible controls may split", () => {
  const controls = [
    { name: "first", xMm: 0, yMm: 0, widthMm: 100, heightMm: 5, autoHeight: true, value: "first" },
    { name: "overlap", xMm: 100, yMm: 2, widthMm: 20, heightMm: 4, value: "overlap" },
    { name: "later", xMm: 0, yMm: 10, widthMm: 120, heightMm: 5, autoHeight: true, divisible: true, value: "later" },
  ];
  const html = intrinsicBand("body", 17, controls);
  expect(html.match(/class="flow-section/g)).toHaveLength(2);
  expect(html).toContain('class="flow-section divisible" style="min-height:5mm;margin-top:4mm"');
  expect(html).toContain("margin-top:2mm"); expect(html).toContain("padding-bottom:2mm");
  expect(html.match(/data-report-indivisible/g)).toHaveLength(1);
});

it("validates finite nonnegative geometry, printable width/capacity and controlled CSS tokens", () => {
  for (const value of [NaN, Infinity, -1]) expect(() => band("x", value, [])).toThrow("Invalid report geometry");
  expect(() => band("x", 1, [{ name: "x", xMm: 0, widthMm: 0, heightMm: 1, value: "" }])).toThrow();
  expect(() => band("x", 1, [], 'detail" style="')).toThrow();
  expect(() => fixedReportDocument({ reportId: "wide", rows: [], layout: { ...layout, widthMm: 171 } })).toThrow("does not fit");
  expect(() => fixedReportDocument({ reportId: "tall", rows: [], layout: { ...layout, footer: { heightMm: 260 } } })).toThrow("does not fit");
});

it("paper orientation swaps physical dimensions and margin CSS preserves all four independently supplied sides", () => {
  expect(paperSize("A4", "landscape")).toEqual({ widthMm: 297, heightMm: 210 });
  expect(paperSize("A5")).toEqual({ widthMm: 148, heightMm: 210 });
  expect(paperSize("Letter")).toEqual({ widthMm: 215.9, heightMm: 279.4 });
  const document = fixedReportDocument({ reportId: "synthetic", rows: [], layout: { ...layout,
    marginsMm: { top: 17, right: 19, bottom: 23, left: 13 },
    header: { name: "header", heightMm: 7, controls: [] }, footer: { heightMm: 6 },
  } });
  expect(document.css).toContain("margin:24mm 19mm 29mm 13mm");
  expect(document.css).not.toContain("@bottom-left");
  expect(document.html).not.toContain('data-band="detail"');
});
