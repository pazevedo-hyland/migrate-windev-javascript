import type { ReportDocument } from "./contracts";

export type ReportValues = Readonly<Record<string, string | null>>;
export type PaperSize = { widthMm: number; heightMm: number };
export type ReportMargins = { top: number; right: number; bottom: number; left: number };
export type ReportControl = {
  name: string;
  xMm: number;
  yMm?: number;
  widthMm: number;
  heightMm: number;
  field?: string;
  text?: string | null;
  autoHeight?: boolean;
  divisible?: boolean;
  title?: boolean;
  visible?: boolean;
  border?: readonly ("top" | "right" | "bottom" | "left")[];
};
export type ReportBand = { name: string; heightMm: number; controls: readonly ReportControl[] };
export type ReportPageFooter = {
  heightMm: number;
  pageNumber?: { xMm: number; widthMm: number; heightMm: number };
};
export type ReportLayout = {
  paper: PaperSize;
  marginsMm: ReportMargins;
  widthMm: number;
  header?: ReportBand;
  start?: ReportBand;
  detail: ReportBand;
  end?: ReportBand;
  footer?: ReportPageFooter;
};
export type BoundReportControl = ReportControl & { value: string | null };

export function paperSize(name: "A4" | "A5" | "Letter", orientation: "portrait" | "landscape" = "portrait"): PaperSize {
  const [widthMm, heightMm] = name === "A4" ? [210, 297] : name === "A5" ? [148, 210] : [215.9, 279.4];
  return orientation === "portrait" ? { widthMm, heightMm } : { widthMm: heightMm, heightMm: widthMm };
}

export function escapeReportText(value: string | null): string {
  return (value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}
const mm = (value: number, positive = false): number => {
  if (!Number.isFinite(value) || value < 0 || positive && value === 0) throw new Error("Invalid report geometry");
  return value;
};
function validateControl(control: ReportControl): void {
  mm(control.xMm); mm(control.yMm ?? 0); mm(control.widthMm, true); mm(control.heightMm);
  if (control.border?.some(edge => !["top", "right", "bottom", "left"].includes(edge))) throw new Error("Invalid report border");
}
function borders(control: ReportControl): string {
  return (control.border ?? []).map(side => `border-${side}:0.1mm solid white`).join(";");
}
function classes(kind: string): string {
  if (!/^[a-z-]*$/.test(kind)) throw new Error("Invalid report band kind");
  return kind;
}

export function band(name: string, heightMm: number, controls: readonly BoundReportControl[], kind = ""): string {
  mm(heightMm); classes(kind); controls.forEach(validateControl);
  return `<div data-band="${escapeReportText(name)}" class="band ${kind}" style="display:block;height:${heightMm}mm">${controls.map(control =>
    `<div data-control="${escapeReportText(control.name)}" class="control${control.title ? " title" : ""}" style="display:block;left:${control.xMm}mm;top:${control.yMm ?? 0}mm;width:${control.widthMm}mm;height:${control.heightMm}mm;${borders(control)}">${escapeReportText(control.value)}</div>`
  ).join("")}</div>`;
}

/** The browser measures text. Intersecting source rectangles share a flow section;
 * later sections retain their gaps while moving below growing content. */
export function intrinsicBand(name: string, heightMm: number, controls: readonly BoundReportControl[], kind = ""): string {
  mm(heightMm); classes(kind); controls.forEach(validateControl);
  const sections: { top: number; bottom: number; controls: BoundReportControl[] }[] = [];
  for (const control of [...controls].sort((first, last) => (first.yMm ?? 0) - (last.yMm ?? 0))) {
    const top = control.yMm ?? 0, bottom = top + control.heightMm, previous = sections.at(-1);
    if (previous && top < previous.bottom - 0.00001) { previous.bottom = Math.max(previous.bottom, bottom); previous.controls.push(control); }
    else sections.push({ top, bottom, controls: [control] });
  }
  const divisible = controls.some(control => control.autoHeight && control.divisible);
  let previousBottom = 0;
  const content = sections.map(section => {
    const gap = section.top - previousBottom; previousBottom = section.bottom;
    const split = section.controls.length === 1 && section.controls[0].autoHeight && section.controls[0].divisible;
    const inner = section.controls.map(control => `<div data-control="${escapeReportText(control.name)}" class="control flow-control${control.title ? " title" : ""}" style="margin-left:${control.xMm}mm;margin-top:${(control.yMm ?? 0) - section.top}mm;width:${control.widthMm}mm;${control.autoHeight ? `min-height:${control.heightMm}mm;height:auto` : `height:${control.heightMm}mm`};${borders(control)}">${escapeReportText(control.value)}</div>`).join("");
    return `<div class="flow-section${split ? " divisible" : ""}"${split ? "" : " data-report-indivisible"} style="min-height:${section.bottom - section.top}mm;margin-top:${gap}mm">${inner}</div>`;
  }).join("");
  return `<div data-band="${escapeReportText(name)}" class="band intrinsic-band ${kind}${divisible ? " divisible" : ""}"${divisible ? "" : " data-report-indivisible"} style="min-height:${heightMm}mm;padding-bottom:${Math.max(0, heightMm - previousBottom)}mm">${content}</div>`;
}

/** A field is an explicit binding; missing and NULL values display blank. */
export function renderBand(definition: ReportBand, values: ReportValues = {}, kind = ""): string {
  const controls = definition.controls.filter(control => control.visible !== false).map(control => ({ ...control,
    value: control.field === undefined ? control.text ?? "" : Object.hasOwn(values, control.field) ? values[control.field] : null,
  }));
  const render = controls.some(control => control.autoHeight) ? intrinsicBand : band;
  return render(definition.name, definition.heightMm, controls, kind);
}

/** Paged.js 0.4.3 needs a running element for positioned-band headers.
 * The first page keeps document-start followed by the actual table header. */
export function pageHeaderCss(heightMm: number, widthMm: number, topMarginMm: number): string {
  mm(heightMm); mm(widthMm, true); mm(topMarginMm);
  return `@page{margin-top:${topMarginMm + heightMm}mm;@top-left{content:element(reportHeader);vertical-align:bottom;width:${widthMm}mm;}}
@page:first{margin-top:${topMarginMm}mm;@top-left{content:none;}}
.running-header{position:running(reportHeader);width:${widthMm}mm;height:${heightMm}mm;}`;
}

export const reportBodyCss = `
*{box-sizing:border-box;}body{margin:0;font-family:ReportSans;font-size:8pt;color:#000;}
.band{position:relative;break-inside:avoid;}.control{position:absolute;padding:0.6mm 0.3mm;white-space:pre-wrap;overflow:hidden;overflow-wrap:anywhere;}
.title{border:0.1mm solid #314653;border-radius:3mm;background:white;font-size:16pt;font-weight:700;text-align:center;}
.intrinsic-band{display:flow-root;}.flow-section{display:grid;break-inside:avoid;}.flow-control{position:relative;grid-area:1/1;align-self:start;min-width:0;}
.intrinsic-band.divisible,.flow-section.divisible{break-inside:auto;}.flow-section.divisible{display:block;}.flow-section.divisible>.flow-control{position:static;overflow:visible;box-decoration-break:clone;}
table{border-collapse:collapse;table-layout:fixed;}thead{display:table-row-group;}td,th{padding:0;border:0;font-weight:normal;text-align:left;}tr{break-inside:avoid;}
.page-header{background:#819fb4;}.detail{background:#d4e3ed;}.document-start,.document-end{background:linear-gradient(#fafafa,#e1e1e1);}
.group-header{break-after:avoid;}.group-footer{break-before:avoid;}html{-webkit-print-color-adjust:exact;print-color-adjust:exact;}`;

export function fixedReportDocument(input: {
  reportId: string;
  layout: ReportLayout;
  rows: readonly ReportValues[];
  values?: ReportValues;
  unresolved?: readonly string[];
  language?: string;
}): ReportDocument {
  const { layout, values = {} } = input, margins = layout.marginsMm;
  mm(layout.paper.widthMm, true); mm(layout.paper.heightMm, true); mm(layout.widthMm, true);
  [margins.top, margins.right, margins.bottom, margins.left].forEach(value => mm(value));
  const headerHeight = layout.header?.heightMm ?? 0, footerHeight = layout.footer?.heightMm ?? 0;
  mm(headerHeight); mm(footerHeight);
  const capacity = layout.paper.heightMm - margins.top - margins.bottom - headerHeight - footerHeight;
  if (layout.widthMm > layout.paper.widthMm - margins.left - margins.right || capacity <= 0) throw new Error("Report does not fit the paper");
  const header = layout.header ? renderBand(layout.header, values, "page-header") : "";
  const counter = layout.footer?.pageNumber;
  if (counter) { mm(counter.xMm); mm(counter.widthMm, true); mm(counter.heightMm); }
  // This engine replaces partial margin maps. Keep all four sides in the final
  // rule and declare only margin boxes actually used by this document.
  const footerCss = counter ? `@page{@bottom-left{content:counter(page) "/" counter(pages);font-family:ReportSans;font-size:9pt;vertical-align:top;margin-left:${counter.xMm}mm;width:${counter.widthMm}mm;height:${counter.heightMm}mm;padding:0;}}` : "";
  const css = reportBodyCss + (layout.header ? pageHeaderCss(headerHeight, layout.widthMm, margins.top) : "") + footerCss
    + `@page{size:${layout.paper.widthMm}mm ${layout.paper.heightMm}mm;margin:${margins.top + headerHeight}mm ${margins.right}mm ${margins.bottom + footerHeight}mm ${margins.left}mm;}.report,.band,table{width:${layout.widthMm}mm;}.running-header{width:${layout.widthMm}mm;}`;
  const row = (html: string) => `<tr><td>${html}</td></tr>`;
  return { reportId: input.reportId, unresolved: [...input.unresolved ?? []], language: input.language, css,
    html: `${layout.header ? `<div class="running-header">${header}</div>` : ""}<article class="report" data-report-page-height="${capacity}">${layout.start ? renderBand(layout.start, values, "document-start") : ""}<table>${layout.header ? `<thead>${row(header)}</thead>` : ""}<tbody>${input.rows.map(values => row(renderBand(layout.detail, values, "detail"))).join("")}</tbody></table>${layout.end ? renderBand(layout.end, values, "document-end") : ""}</article>` };
}
