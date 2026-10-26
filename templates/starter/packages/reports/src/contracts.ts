/** Report IDs, data selection, authorization and calculations belong to each application. */
export type ReportDocument = {
  reportId: string;
  html: string;
  css: string;
  unresolved?: string[];
  language?: string;
};

export type ReportRenderResult = {
  kind: "rendered";
  reportId: string;
  html: string;
  pdfBase64: string;
  pageCount: number;
  unresolved: string[];
} | { kind: "failed" | "unavailable" }
  | { kind: "unresolved"; unresolved: string[] };

export type ReportRenderer = (document: ReportDocument) => Promise<ReportRenderResult>;
