# Screen spec — <WIN_Name>

Evidence: `legacy/<path>/<file>.wdw`, `dossier: <WIN_Name>`, images `docs/evidence/images/<WIN_Name>.jpg` (designer) and `.svg` (layout drawing), mapping note `docs/mapping/<WIN_Name>.md`. Write it so an implementer can build from it without opening the legacy sources (they verify against them): quote every value it relies on (constants, masks, texts) and include the contract of each window or report it opens.
Opened from: <menu path / window + event, from docs/navigation.md>. Mode: <modal / non-modal / child / internal window>.
Size/resizing: <width × height, minimum size, resizable, anchors; saved position vs opening position — which wins>. Default button (Enter): <…>. Cancel button (Esc): <…>. Focus on open: <control, per mode>.

## Contract

What the window needs and leaves behind, including what WINDEV passes implicitly. The target turns implicit state into explicit inputs and outputs.

| Direction | What | How in legacy | Evidence |
|---|---|---|---|
| in | <record to edit, or new> | <parameter / shared file buffer (`Clientes` current record, `..NewRecord`) / global> | <path:line> |
| out | <saved: yes/no> | <`MyWindow..ReturnedValue` / buffer the caller reads afterwards / global> | <caller path:line> |

## Layout

From the inspector `layout` (pixels, absolute in the window) and the dossier (anchoring, images, skin). Fonts and colors come from the skin template: name it, and read them from the dossier image.

| Legacy name | x | y | width | height | Anchoring (how it moves or grows on resize) | Image / skin |
|---|---|---|---|---|---|---|

Style values: base font and size, colors (names resolved to RGB), and every icon or button visible in the dossier image — each named here or listed as a `U-` item.

| Element | Font / size | Color (RGB) | Source (dossier field / image) |
|---|---|---|---|

## Controls (in tab order)

`tab_order` counts within each container (a supercontrol has its own sequence): write the effective order across the window.

| # | Legacy name (= `data-testid`) | Type | Caption | Linked item | Mask / format | Required | Max len | Initial state | Rules (visible / enabled / read-only, tab stop when disabled) | Shortcut | Parity IDs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | EDT_Customer | edit | Customer | CUSTOMER.Name | uppercase | yes | 50 | empty | read-only when order closed | Alt+C | SRC-… |

## Tables (grids)

| Legacy name | Source (file/query/array) | Columns (name, item, format, width, editable) | Sort / filter | Row actions | Totals | Parity IDs |
|---|---|---|---|---|---|---|

## Selection and display state

| Moment | Selected row / current record | What dependent controls show | Evidence or U-id |
|---|---|---|---|
| On open | | | |
| After a search or filter change | | | |
| After add / modify / delete (and a record that no longer matches the filter) | | | |
| Empty result | | | |
| Keyboard row moves | | | |
| Data changed by another window or user | | | |
| A second instance opened | | | |

## Built-in control features

Table sort and per-column search, saved column configuration, Enter handling, drop-down search… (dossier `flags`): each has a parity row, or is excluded by an ADR.

| Control | Feature | On? | Interaction with the code's filters | Parity ID |
|---|---|---|---|---|

## Messages

| Trigger | Exact legacy text (with placeholders resolved: what each `+ x` prints) | Type (Info/Error/YesNo/Dialog), title, icon | Buttons (labels per language), default button, Esc / close box result | Parity ID |
|---|---|---|---|---|

## Data edge cases

| Case | Legacy behavior | Evidence or U-id |
|---|---|---|
| Empty vs NULL written for blank fields | | |
| Text with spaces only, maximum length, accents/case in keys | | |
| Number range actually supported (mask, item type, code variables) | | |
| No rows / first record / concurrent users | | |

## Acceptance checks

- Keyboard-only walkthrough: <sequence of keys and expected focus/results>.
- Visual comparison with the dossier image approved by: <human, date>.

Every open point is a `U-<UNIT>-nn` item in the mapping note — never a bare "check" or "untested".
