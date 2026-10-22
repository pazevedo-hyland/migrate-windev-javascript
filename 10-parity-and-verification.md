# 10 — Parity and verification

"Full feature parity" must be **measurable**, or an agent will report 100% on the part of the application it happened to see. This chapter defines the denominator, the evidence, and the gates.

## 1. A closed-world inventory

The parity matrix `docs/parity/parity.csv` ([template](templates/parity.template.csv)) is the definition of done. It is built in three layers:

1. **Generated seed** — `scripts/inspect_windev.py` writes `parity-seed.csv`: one `SRC-*` row per extracted code block (window/control path + raw event code + `path:line`), one per XDD table, one per binary/unsupported source needing an export. IDs are stable across re-runs of the same sources.
2. **Manual rows** for what code blocks do not show: menu entries and shortcuts, Groupware rights, reports and labels, scheduled jobs, external integrations, imports/exports, printing and devices, INI/registry settings, installer/update behavior.
3. **Rule rows** (`RULE-*`) for business rules spanning several blocks (e.g. an order total computed in three events).

Rules of the matrix, enforced by `scripts/parity_check.py`:

- every seed row stays in the matrix (`--seed`): refine it, mark it `excluded` with an ADR, but never delete it;
- every row has evidence and a confidence (`verified` / `inferred` / `unresolved`);
- status flows `unmapped → specified → implemented → verified`, or `excluded`;
- `specified` needs a target behavior; `implemented` needs `implemented_in`; `verified` needs the **test that ran** and cannot keep `unresolved` legacy behavior; `excluded` needs a decision reference;
- a row is `verified` only when its test asserts the row's behavior **and** no part of that behavior is an implementer's choice for an unresolved item (e.g. what Esc does on a dialog nobody has observed). Otherwise it stays `implemented` and the choice goes to the handoff as a decision — or the unresolved part is split into its own row. The checker cannot see this; the review must;
- the migration is complete when `parity_check.py --require-complete --seed …` passes.

Run it in `npm run verify` (without `--require-complete`) on every commit, and with `--require-complete` as the final release gate.

## 2. Golden scenarios (characterization tests)

The only robust proof that totals, rounding, statuses and reports match is to **record the legacy application and replay the target** on identical inputs ([template](templates/golden-scenario.md)):

1. **Before**: export the relevant tables from a sanitized dataset (CSV + manifest).
2. **Act**: perform a scripted sequence in the legacy app (or with WINDEV's automated test scenarios, if the project has them).
3. **After**: export the same tables; save output files (report PDF, exported files) and the exact messages shown.
4. **Replay** in the target from the same "before" state, through the use cases (fast tests) and end to end (slower).
5. **Compare** with `scripts/compare_exports.py`: keys, renames, ignored technical columns and **declared** normalizations (decimal comma, date formats, trimming). Any undeclared difference fails.

**No legacy runs available?** Expected results can be derived from the mapped rules on synthetic data, but label them `spec-derived` (they prove the code matches the spec, not the legacy app) and replace them with recorded scenarios when the app can run. Historical data is a golden dataset too: wherever the legacy app stored a derived value (order totals, stock levels, durations, statuses) next to its inputs, the target's domain functions must reproduce it from those inputs. Every disagreement is either a rule not yet understood or a data-quality issue to record.

Choose scenarios for: every workflow's happy path, each boundary (zero, negative, maximum, empty date), each error message, rounding with many lines, and every report. Record them early (stage 0–3), while the legacy app and its experts are available.

## 3. UI fidelity

- **Screen spec** per window ([template](templates/window-spec.md)) from the `.wdw` source, designer and screenshots: controls in tab order, linked items, masks, required fields, max lengths, rules, shortcuts, default/cancel buttons, exact messages.
- **Legacy control names as `data-testid`** (`EDT_Customer`, `BTN_Save`): tests, parity rows, rights and the screen spec share one vocabulary.
- **Automated control coverage** ([templates/ui-check](templates/ui-check/)): a Playwright check opens each window in browser-preview mode (fake backend) through its configured route, asserts that **every legacy control** listed by the inspector (`controls` in its output, table columns included) exists as a `data-testid`, and fails on any gap that has no recorded reason in `ui-check.config.json`. It screenshots every window into a side-by-side report with the legacy screenshots from the capture kit. In the pilot it found the only gaps by itself (skin title-bar controls, a deferred picker button) in 3.5 seconds.
- **Keyboard walkthrough tests** generated from the spec (tab order, Enter/Esc, shortcuts).
- **Visual comparison** with the screenshot: an automated screenshot of the target next to the legacy one, **approved by the human**. Visual decisions are human decisions.

## 4. Reports

- Keep a legacy PDF **with its input data** for every report.
- Compare extracted text (e.g. `pdftotext -layout`) for headers, lines, breaks, subtotals and totals; numbers must match exactly.
- Human review for layout, fonts, page breaks, barcodes and label dimensions; print on the real printers.

## 5. Native and platform behavior

A browser run with mocked IPC proves UI logic only. For each target OS, record a smoke test: install, first start, migration, save/reopen after restart, printing, device input, file dialogs, update from the previous version, uninstall. Automate with `tauri-driver` where supported; otherwise keep a signed checklist in `docs/runbooks/`.

## 6. Data parity

Import reconciliation ([08](08-data-migration.md#import-and-reconciliation)): counts, keys, balances, quantities, durations, report totals — compared with `compare_exports.py`, with a stored report and approved exceptions.

## 7. Gates

| When | Gate |
|---|---|
| Every commit | `npm run verify` (types, lint, unit, IPC-mocked workflows, `parity_check.py`, bindings diff) |
| End of slice | Golden scenarios of the slice; parity rows `verified`; native smoke on at least one target OS |
| Nightly | Full rebuild, all tests, all golden scenarios, report pushed to `reports` |
| Release | All of the above on every target OS + `parity_check.py --require-complete --seed …` + reconciliation of a full import + cutover rehearsal |

## 8. What agents must not do

- Mark `verified` without a test that ran, or relax a comparison to make it pass.
- Delete or merge seed rows to improve the percentage.
- Treat "inferred" behavior as fact in code without flagging it in the handoff.
- Replace exact legacy messages, rounding or ordering with "better" ones without an ADR.
