# Screen spec — <WIN_Name>

Evidence: `legacy/code/<file>.wdw`, `legacy/screenshots/<WIN_Name>*.png`, mapping note `docs/mapping/<unit>.md`.
Opened from: <menu path / window + event>. Mode: <modal / non-modal / child / internal window>. Parameters: <…>. Returns: <…>.
Size/resizing: <fixed / anchors>. Default button (Enter): <…>. Cancel button (Esc): <…>.

## Controls (in tab order)

| # | Legacy name (= `data-testid`) | Type | Caption | Linked item | Mask / format | Required | Max len | Initial state | Rules (visible / enabled / read-only) | Shortcut | Parity IDs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | EDT_Customer | edit | Customer | CUSTOMER.Name | uppercase | yes | 50 | empty | read-only when order closed | Alt+C | SRC-… |

## Tables (grids)

| Legacy name | Source (file/query/array) | Columns (name, item, format, width, editable) | Sort / filter | Row actions | Totals | Parity IDs |
|---|---|---|---|---|---|---|

## Messages

| Trigger | Exact legacy text | Type (Info/Error/YesNo/Dialog) | Buttons and result | Parity ID |
|---|---|---|---|---|

## Acceptance checks

- Keyboard-only walkthrough: <sequence of keys and expected focus/results>.
- Visual comparison with screenshot approved by: <human, date>.
