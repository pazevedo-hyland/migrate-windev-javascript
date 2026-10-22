# Report spec — <RPT_Name>

Evidence: `legacy/code/<file>.wde`, dossier extract `<dossier>/report/<RPT_Name>.json` and image `<dossier>/images/<RPT_Name>.*`, mapping note `docs/mapping/<unit>.md`.
Printed by: <callers from docs/evidence-report.json, with parameters — or "no caller found" and what that means>.
Destination: <preview (`iPreview`), printer, PDF, file>. Parameters: <…>.

## Page

| Format | Orientation | Margins (mm) T/B/L/R | Printable width (mm) | Widest band (mm) | Fits? |
|---|---|---|---|---|---|
| A4 (210 × 297) | <portrait / landscape, or "not in dossier": read it from the image> | 20/20/20/20 | 170 | <max x + width> | <yes / no: what legacy does> |

## Data source

Type: <embedded query / query QRY_x / file / programmed>. SQL: <from the dossier, or "encoded" + what it must return>. Sort: <…>. Filters and parameters: <…>.

## Bands

| Band | Repeats | Contents | Notes |
|---|---|---|---|
| Start of document | once | <title block, if any> | |
| Page header | every page | <company name, title, date…> | |
| Column header | every page | <captions> | |
| Body | per record | <bound items> | |
| Break header / footer | per <item> | <…> | |
| Page footer | every page | <page n/N, totals…> | needs page count (two passes) |
| End of document | once | <grand totals, if any> | |

## Columns and controls

| Control | Band | Type | Text / bound item | Text source | x, width (mm) | Alignment | Mask / format | Borders | Overflow |
|---|---|---|---|---|---|---|---|---|---|

Text source: `dossier` (parsed field), `image` (read from the dossier image: say so) or `code`. Geometry comes from the source layout (`layout` in the inspector output) or the dossier, in millimetres. Adjacent cells often share a border line (one cell's x + width = the next x): draw it once.

## Calculations and presets

| Control | Kind | Formula / preset | Reset on | Mask | Parity ID |
|---|---|---|---|---|---|

## Acceptance checks

- A legacy PDF of this report for known data (golden), compared on extracted text: headers, rows, totals, page numbers.
- Visual comparison with the dossier image, approved by: <human, date>.
