# Golden scenario — GS-<nnn> <short name>

Proves parity rows: <IDs>. Recorded on: <date>, WINDEV app version <x>, by <who>.

## Starting state
Recorded raw in `legacy/golden/GS-<nnn>/` (private). The copy every machine replays (anonymised if the data is personal) is committed in `docs/golden/GS-<nnn>/`: `before/` (CSV export of the tables listed below, with manifest: encoding, delimiter, decimal and date formats, row counts).
Tables: <ORDERS, ORDER_LINES, STOCK…>. Settings that matter: <date, user, rights, INI/registry values, printer>.

## Steps performed in the legacy application
1. <Open WIN_Order from menu Orders > New>
2. <Type "DUPONT" in EDT_Customer, Tab…>
3. <Click BTN_Save; answer Yes to "Confirm the order?">

## Recorded results
- Data after: `docs/golden/GS-<nnn>/after/` (same tables, same export settings).
- Outputs: <report PDF `docs/golden/GS-<nnn>/order.pdf`, exported file, message texts shown>.

## Replay in the target
- Seed the target from `before/` with the import tool; run the same steps as a use-case test (fast) and as an end-to-end test (slower).
- Export the same tables to `analysis-local/golden/GS-<nnn>/after/`.
- Compare: `python3 scripts/compare_exports.py --config docs/golden/compare.json --legacy docs/golden/GS-<nnn>/after --target analysis-local/golden/GS-<nnn>/after`.
- Report: compare extracted PDF text (totals, lines, headers) with the legacy PDF; layout differences go to human review.

## Accepted differences
<None, or column-level differences with the ADR that accepts them (e.g. technical timestamps ignored).>
