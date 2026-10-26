# 10 — Parity and verification

"Full feature parity" must be **measurable**, or an agent will report 100% on the part of the application it happened to see. This chapter defines the denominator, the evidence, and the gates.

## 1. A closed-world inventory

The parity matrix `docs/parity/parity.csv` ([template](templates/parity.template.csv)) defines strict migration completion. It is built in three layers:

1. **Generated seed** — `scripts/inspect_windev.py` writes `parity-seed.csv`: one `SRC-*` row per extracted code block (window/control path + raw event code + `path:line`), one per XDD table, one per binary/unsupported source needing an export. IDs are stable across re-runs of the same sources. If an upgraded inspector names a block differently, `parity_check.py --seed` reports `matrix row SRC-old is now seed row SRC-new`: rename the row.
2. **Manual rows** for what code blocks do not show: menu entries and shortcuts, Groupware rights, reports and labels, scheduled jobs, external integrations, imports/exports, printing and devices, INI/registry settings, installer/update behavior.
3. **Rule rows** (`RULE-*`) for business rules spanning several blocks (e.g. an order total computed in three events).

Rules of the matrix, enforced by `scripts/parity_check.py`:

- every seed row stays in the matrix (`--seed`): refine it, mark it `excluded` with an ADR, but never delete it;
- every row has evidence and a confidence (`verified` / `inferred` / `assumed` / `unresolved`);
- status flows `unmapped → specified → implemented → verified`, or `excluded`;
- `specified` needs a target behavior; `implemented` needs `implemented_in`; `verified` needs the **test that ran** and cannot keep `unresolved` legacy behavior; `excluded` needs a decision reference;
- a row is `verified` only when it passes the five checks of the AGENTS template's "No guessing" section ([templates/AGENTS.template.md](templates/AGENTS.template.md)): above all, its test asserts the behavior and no part of it is an implementer's choice for an unresolved item. Otherwise it stays `implemented`. The checker cannot see this; the review must;
- the migration is complete when `parity_check.py --require-complete --seed docs/parity/parity-seed.csv` passes. `docs/parity/parity-seed.csv` is the committed copy of the inspector's seed, refreshed by `prepare_evidence.py`.

Run it in `npm run verify` (without `--require-complete`) on every commit, and with `--require-complete` as the final release gate.


**Progress for everyone.** `python3 scripts/progress_dashboard.py` writes `docs/progress/index.html`: functional readiness first, then built/proven/strict parity counts, source questions, platform evidence and strict completion history. Without a functional acceptance inventory, the headline stays unassessed. Each stage regenerates the page so a non-technical owner can open one file.

For broad implementation waves, also report **built = implemented + verified**, verified targets, exclusions and unanswered source/U items, with explicit denominators. A built percentage measures target coverage; it is not legacy parity or release readiness. Keep assumption-backed targets visible. Linking existing code or testing an accepted default does not prove newly recovered legacy knowledge; never upgrade source confidence just because target tests pass. Initial implementation milestones retain an acceptance backlog; the final `--require-complete` gate is unchanged.

Projects may opt into **functional acceptance** in `docs/functional-acceptance.json` ([template](templates/functional-acceptance.template.json)). Each required case declares `id`, `units`, `requirement`, exact `checks` (`file`, `title`), `status` (`verified` or `pending`) and `evidence` (`run`, `os`, `commit`). Run metadata records which exact checks actually passed and the tested application commit. Requirements cite source rules or approved target decisions; assertions exercise real paths and would fail if the behavior disappeared. Validate the schema and evidence with `python3 scripts/functional_acceptance.py --check`; use `--require-complete` for this optional acceptance gate.

The primary functional percentage is verified required cases / all declared required cases. Cover the complete approved workflow scope and every screen/report from the inventory: a missing unit creates a pending, unassessed gap. Untested and failed cases stay in the denominator; built links and a suite pass rate never create acceptance. Proof must remain compatible with its tested commit: application or test changes invalidate affected evidence; documentation-only changes do not. Keep strict parity/source confidence and platform capabilities (status, OS, commit) alongside this view. An approved target choice may pass while its legacy U question remains unanswered; unexecuted native checks remain unexecuted.

Adapt the validator's `CODE_PATHS` to the actual project's application, assets, configuration, golden inputs, runtime-evidence JSON and native probes; cited test files are included automatically. Changing those inputs invalidates the witness. Ordinary report/status documentation may retain it. The validator checks recorded attestations; review still establishes that the exact tests ran and assert the full requirement.

## 2. Golden scenarios (characterization tests)

To compare observed legacy totals, rounding, statuses and reports, **record the legacy application and replay the target** on identical inputs ([template](templates/golden-scenario.md)):

1. **Before**: export the relevant tables from the data copy (CSV + manifest; anonymised if the data is personal).
2. **Act**: perform a scripted sequence in the legacy app (or with WINDEV's automated test scenarios, if the project has them).
3. **After**: export the same tables; save output files (report PDF, exported files) and the exact messages shown.
4. **Replay** in the target from the same "before" state, through the use cases (fast tests) and end to end (slower).
5. **Compare** with `scripts/compare_exports.py`: keys, renames, ignored technical columns and **declared** normalizations (decimal comma, date formats, trimming). Any undeclared difference fails.

**Source-derived checks** can verify readable rules directly: derive expected results from the actual source, schema and accepted decisions on synthetic data, then exercise the real target path. Label scenarios `spec-derived` and identify source rules versus approved target choices; reserve `recorded` for observed legacy runs. A legacy run is not a prerequisite for testing a readable assignment or calculation. Such a test does not establish encoded SQL, missing designer properties or native engine behavior; retain those U questions and add static exports or recorded checks for the missing evidence. Historical data is a golden dataset too: wherever the legacy app stored a derived value (order totals, stock levels, durations, statuses) next to its inputs, the target's domain functions must reproduce it from those inputs. Every disagreement is either a rule not yet understood or a data-quality issue to record.

Choose scenarios for: every workflow's happy path, each boundary (zero, negative, maximum, empty date), each error message, rounding with many lines, and every report. Record them early (stage 0–3), while the legacy app and its experts are available.

## 3. UI fidelity

- **Screen spec** per window ([template](templates/window-spec.md)) from the `.wdw` source, designer and screenshots: controls in tab order, linked items, masks, required fields, max lengths, rules, shortcuts, default/cancel buttons, exact messages.
- **Legacy control names as `data-testid`** (`EDT_Customer`, `BTN_Save`): tests, parity rows, rights and the screen spec share one vocabulary.
- **Layout reference for every window**, with no running app: `scripts/render_layouts.py` draws each `.wdw` to scale from the inspector's control positions; with the dossier extract it shows the real captions.
- **Automated control coverage and visual score** ([templates/ui-check](templates/ui-check/)): a Playwright check opens each window in browser-preview mode (fake backend) through its configured route, asserts that **every legacy control** listed by the inspector (`controls` in its output, table columns included) exists as a `data-testid`, and fails on any gap that has no recorded reason in `ui-check.config.json`. With the dossier extract it also compares each control's visible text with its legacy **caption**. It screenshots every window, scores it against the dossier image with `scripts/visual_compare.py` (recorded in `docs/evidence/visual/`, shown on the progress page) and fails when a window scores below the floor (default pixels 90 %, layout 60 %, `visualFloor`), looks less like the legacy one than its last recorded score, or uses an image that does not load (a missing skin icon renders as a blank, and dev servers answer it with HTML and status 200, so each image is fetched and its type checked); evidence paths outside the repository are refused; edit captions are read from their `<label>`. Side-by-side report in `ui-report/`. In the pilot it found the only missing controls by itself (skin title-bar controls, a deferred picker button) in 3.5 seconds.
- **Keyboard walkthrough tests** generated from the spec (tab order, Enter/Esc, shortcuts).
- **Build the screen from the evidence, not by hand.** `scripts/screen_layout.py <WINDOW>` writes one JSON per window (pixel positions, captions, button types, icons and their states, background images and stretching, caption widths, table columns in order); the screen's markup reads captions and coordinates from it, so they cannot drift. `scripts/skin_assets.py` copies the skin images it names from the WINDEV project folder, one PNG per state (normal, hover, pressed…), with the skins' magenta made transparent; CSS uses them as 9-slice `border-image`, as WINDEV stretches them. Fonts and colors are the skin template's (`.sty`): its font names are readable, sizes and colors are sampled from the dossier image and marked as such.
- **Click-through of the golden scenarios** ([flows example](templates/ui-check/flows.example.spec.ts)): per slice, a Playwright spec drives the screens like a user — search, open the form, save, the delete confirmation and its Esc, the close box — on the golden data, in browser-preview mode, with the legacy texts as expectations. On the pilot's vehicle slice: 5 flows, 10 golden cases, 5 s. It does not reach the Rust commands through IPC (their own tests do); the native window needs `tauri-driver`, which runs on Windows and Linux only — run it in a Windows CI job when the target is Windows.
- **Shared controls first** ([starter](templates/starter/README.md)): reuse its windows, fields, tables and awaited dialogs, then configure the application's authorized skin and accepted visual policy. The older [skin stub](templates/ui-kit/) remains an alternative for existing consumers. Reuse does not replace screen/dialog checks: a slice closes only when every window and dialog it opens meets the adopted UI checks; a neutral preview alone does not prove a replica.
- **Visual score** with `scripts/visual_compare.py <dossier image> <screenshot> --out side-by-side.png --record docs/evidence/visual/<WINDOW>.json`: pixel similarity (colors, skin) and edge overlap (borders, text and lines at the same place within 2 px). The progress page shows it per screen as "looks like the original". On the pilot's client list: edges 50 % → 75 % and pixels 89 % → 97 % once built this way (80 % / 98 % against the designer view with no data rows); the rest is data, runtime-only controls and font rasterizing. The score ranks screens and shows progress; **the human approves the look** from the side-by-side image. Whether to replicate the skin at all is an owner decision (same look, or same layout with a clean style).

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
| Initial implementation wave | Focused worker checks, integrated verification and review under project policy; rows may remain `implemented` with named acceptance work |
| Functional acceptance (opt-in) | Validated `docs/functional-acceptance.json`: every required case has passed its exact real behavior checks with compatible run/OS/commit evidence; all screens/reports are assessed; strict parity, U questions and platform evidence remain separate |
| Strict parity acceptance | Golden scenarios of the slice; parity rows `verified` or approved `excluded`; native smoke on at least one target OS |
| Nightly | Full rebuild, all tests, all golden scenarios, report pushed to `reports` |
| Release | All of the above on every target OS + `parity_check.py --require-complete --seed docs/parity/parity-seed.csv` + reconciliation of a full import + cutover rehearsal |

## 8. What agents must not do

- Mark `verified` without a test that ran, or relax a comparison to make it pass.
- Delete or merge seed rows to improve the percentage.
- Treat "inferred" behavior as fact in code without flagging it in the handoff.
- Replace exact legacy messages, rounding or ordering with "better" ones without an ADR.
