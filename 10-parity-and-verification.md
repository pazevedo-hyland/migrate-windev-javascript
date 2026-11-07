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
- **Automated control coverage and visual score** ([templates/ui-check](templates/ui-check/)): a Playwright check opens each window in browser-preview mode (fake backend) through its configured route, asserts that **every legacy control** listed by the inspector (`controls` in its output, table columns included) exists as a `data-testid`, and fails on any gap that has no recorded reason in `ui-check.config.json`. With the dossier extract it also compares each control's visible text with its legacy **caption**. It screenshots every window, scores it against the dossier image with `scripts/visual_compare.py` (recorded in `docs/evidence/visual/`, shown on the progress page) and fails when a window scores below the floor (default pixels 90 %, layout 60 %, `visualFloor`), looks less like the legacy one than its last recorded score, or uses an image that does not load (a missing skin icon renders as a blank, and dev servers answer it with HTML and status 200, so each image is fetched and its type checked); evidence paths outside the repository are refused; edit captions are read from their `<label>`. Side-by-side report in `ui-report/`. In the pilot it found the only missing controls by itself (skin title-bar controls, a deferred picker button) in 3.5 seconds. Apps that log in or open windows from a launcher set, per window, a start `url`, or an `openWindow` hook module (`hooks`, [example](templates/ui-check/hooks.example.ts)), and `windowSelector` (e.g. `section[data-layout="<W>"]`) when the window's element is not its `data-testid`; existing configurations work unchanged. A `globalSetup` warm-up ([warmup.ts](templates/ui-check/warmup.ts)) loads the app once first: on a real migration Vite's cold first load outlasted the first test's navigation timeout.
- **Keyboard walkthrough tests** generated from the spec (tab order, Enter/Esc, shortcuts).
- **Reuse workflow assertions** ([starter testing contract](templates/starter/packages/testing/README.md)): configure the shared CRUD, search and confirmation scenarios with real UI actions, an independent database/API reader and expected values derived from this project's evidence. Keep business assertions and witness IDs explicit. The starter's SQLite consumers demonstrate the harness; they are not proof for another application's screens or native behavior.
- **Build the screen from the evidence, not by hand.** `scripts/screen_layout.py <WINDOW>` writes one JSON per window (pixel positions, captions, button types, icons and their states, background images and stretching, caption widths, table columns in order); the screen's markup reads captions and coordinates from it, so they cannot drift. `scripts/skin_assets.py` copies the skin images it names from the WINDEV project folder, one PNG per state (normal, hover, pressed…), with the skins' magenta made transparent; CSS uses them as 9-slice `border-image`, as WINDEV stretches them. Fonts and colors are the skin template's (`.sty`): its font names are readable, sizes and colors are sampled from the dossier image and marked as such.
- **Check the skin against the running legacy app, not only the designer images.** Designer images are usually unskinned, so the visual score cannot catch skin mistakes; one screenshot of the running program caught all of these in a second migration (AquaBlue):
  - Skinned buttons stack their **animation frames** vertically ("Nb. animation steps 6": a 400x144 strip is 5 states x 6 frames of 80x24). Using the whole state column draws six stacked buttons (stripes). `skin_assets.py` now keeps the first frame when the frames are near-identical.
  - The **window background** (`*_Bg_Menu.png`) is a 9-slice with large fixed parts: measure them on the image (AquaBlue: glare in the top 88 px kept at the right edge over 320 px, blue band in the bottom 32 px, plain middle). Stretching the image centre turns a 24 px band into a gradient over the lower window; slicing one row too low draws a line.
  - **Skin pieces no control names** still apply: table column titles (`*_Table_ColTitle.png`), combos (`*_Combo.png`, field plus arrow button), edits (`*_Edt.png`), the `.sty` font (AquaBlue: Trebuchet MS). Apply them to every window of the skin.
  - A **menu bar** sits above the client area; control coordinates are relative to below it.
  - **Radio groups** show their caption above the options; with "Auto height of options No" the options keep designer heights (measure them on the image) instead of sharing the height evenly.
- **"No caller" is not proof of dead code** when a window can be placed in a dashboard (or loaded dynamically): the second migration excluded a dashboard widget that the running app shows. Ask the owner for one screenshot of each start window before excluding such elements.
- **Click-through of the golden scenarios** ([flows example](templates/ui-check/flows.example.spec.ts)): per slice, a Playwright spec drives the screens like a user — search, open the form, save, the delete confirmation and its Esc, the close box — on the golden data, in browser-preview mode, with the legacy texts as expectations. On the pilot's vehicle slice: 5 flows, 10 golden cases, 5 s. It does not reach the Rust commands through IPC (their own tests do); the native window needs `tauri-driver`, which runs on Windows and Linux only — run it in a Windows CI job when the target is Windows.
- **Shared controls first** ([starter](templates/starter/README.md)): reuse its windows, fields, tables and awaited dialogs, then configure the application's authorized skin and accepted visual policy. The older [skin stub](templates/ui-kit/) remains an alternative for existing consumers. Reuse does not replace screen/dialog checks: a slice closes only when every window and dialog it opens meets the adopted UI checks; a neutral preview alone does not prove a replica.
- **Title bar outside the client area**: WINDEV control coordinates are relative to the client area. A window whose layout has no title control (`RADTitle`) and no extracted system buttons uses the system title bar, which sits above that area; the starter draws it there (`wd-frame--native`). Drawn inside, the close box covered a form's top-right buttons; moving it out raised that form's layout match from 32 % to 79 % (two others 50 → 69 % and 34 → 51 %).
- **Visual score** with `scripts/visual_compare.py <dossier image> <screenshot> --out side-by-side.png --record docs/evidence/visual/<WINDOW>.json`: pixel similarity (colors, skin) and edge overlap (borders, text and lines at the same place within 2 px). The progress page shows it per screen as "looks like the original". On the pilot's client list: edges 50 % → 75 % and pixels 89 % → 97 % once built this way (80 % / 98 % against the designer view with no data rows); the rest is data, runtime-only controls and font rasterizing. The score ranks screens and shows progress; **the human approves the look** from the side-by-side image. Whether to replicate the skin at all is an owner decision (same look, or same layout with a clean style).

## 4. Reports

- Keep a legacy PDF **with its input data** for every report.
- Compare extracted text (e.g. `pdftotext -layout`) for headers, lines, breaks, subtotals and totals; numbers must match exactly.
- Human review for layout, fonts, page breaks, barcodes and label dimensions; print on the real printers.

## 5. Native and platform behavior

A browser run with mocked IPC proves UI logic only. The dev server is not the shipped build either: run a **production-build smoke test** (`vite build` → `vite preview`, [templates/ui-check/prod.config.ts](templates/ui-check/prod.config.ts) and [prod.smoke.example.spec.ts](templates/ui-check/prod.smoke.example.spec.ts)) in `verify`. On a real migration Vite inlined small skin PNGs as `data:` URLs in the build only (`build.assetsInlineLimit`, default 4096); the skin resolver refused them and the installed app opened blank while every flow passed — fixed with `assetsInlineLimit: 0`. Drive the **installed** app too: on Windows, WebView2 remote debugging (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9229`, then Playwright `connectOverCDP`) lets the same browser tooling open every window of the packaged build on real data ([02](02-infrastructure.md#windows-installer-for-a-nodetypescript-server--tauri-app)). For each target OS, record a smoke test: install, first start, migration, save/reopen after restart, printing, device input, file dialogs, update from the previous version, uninstall. Automate with `tauri-driver` where supported; otherwise keep a signed checklist in `docs/runbooks/`.

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

### Engineering baseline (starter defaults)

- **Lint and format:** `npm run lint` (ESLint: JS/TS recommended + React hooks; tests may use `any`, Playwright helpers named `use…` are not hooks) and `npm run format:check` (Prettier, width 140). Reformat an existing repository once in its own commit, excluding generated files (`**/*.generated.ts`, `src/generated/`). Mark deliberate exceptions inline with a reason (`// eslint-disable-next-line rule -- why`): record buffers ported from WLanguage are typed by item name.
- **CI:** `.github/workflows/ci.yml` (starter): typecheck, lint, format, unit tests, build, production smoke, UI checks on Windows; Rust fmt/clippy/tests. legacy/ and analysis-local/ are private: CI runs the parity gate without `--check-files`.
- **Test layers:** (1) unit tests of procedures on an in-memory database; (2) click-through flows on the browser preview (procedures and PGlite inside the page, a fresh database per test: tests are independent, so they run in parallel); (3) **real-server flows**: each Playwright worker starts the built server with a fresh database (a PostgreSQL database per worker on CI, a PGlite folder locally) and the app talks to it over HTTP (`templates/ui-check/server-*.example.ts`). Layer 2 never exercises HTTP, the server bundle or PostgreSQL: keep a few layer-3 tests that write through the UI and read back through the server and from a second browser context; (4) smoke of the installed build (WebView2 remote debugging).
- **Large files:** a screen file that mirrors one big legacy window can stay large until the app is proven; split it later behind the click-through tests (refactoring under a full regression suite).

## 8. What agents must not do

- Mark `verified` without a test that ran, or relax a comparison to make it pass.
- Delete or merge seed rows to improve the percentage.
- Treat "inferred" behavior as fact in code without flagging it in the handoff.
- Replace exact legacy messages, rounding or ordering with "better" ones without an ADR.
