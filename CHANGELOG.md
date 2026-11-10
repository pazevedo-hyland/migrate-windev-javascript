# Changelog

## 2026-11-10 — records of each kind of control read exactly; reports beyond geometry

- `windev_decode.py` reads, each checked against the dossier on the second migration's project: an edit control's input type (261 of 261 equal), input size, mask and returned format (270 of 270 equal each), alignment (270 of 270 equal) and caption width (281 of 294 equal; the rest one pixel off in the dossier); a static's alignment (74 of 74 equal); a button's image states (588 of 588 equal) and background stretching (580 of 580 equal); a table column's alignment, place and five options (1,375 of 1,375 equal) and its linked item; the column's cell (owner `content`, a whole control) with its input type and mask (243 of 243 equal, 240 of 240 equal); a report's type, data source and margins (26 of 26 equal each), page size, band types, and each report control's kind (493 of 493 equal).
- The skin's own style sheet: `Templates/<skin>/<skin>.sty` is an unpacked container of style records (1,203 styles in 3 skins here). `skin/<skin>.json` lists each style's fonts, colours, alignment, frames and images, and every control gets `differs_from_style`: what it changed from the style it names (291 of 1,015 controls changed something).
- Windows: opening mode (112 of 112 against the dossier), title bar, system menu, minimize and maximize icons, own HFSQL context (498 of 498), background image. The PDF extract mixes neighbouring tick marks for some windows; the evidence folder now takes these from the source.
- Query parameter names from the SQL (13 queries); `evidence_report.py` no longer lists an embedded query's SQL as missing when the decoder read it.
- **Captions were wrong for a third of the controls and no check showed it**: 292 of 822 captions (506 strings) are stored in UTF-8, not in the code page, and came out as `InÃ­cio`. The calibration compares ASCII letters only, because the PDF loses accents, so it reported them equal. Strings are now read as UTF-8 when they are valid UTF-8. Regenerate evidence made before this.
- Combo and list boxes: content in memory or from a file (44 of 44 against the dossier), browsed file, browsed, displayed and stored items (106 of 106), and the values typed in the designer in full — the dossier prints only the first (here six lists: document types, stock movement kinds, order states, months).
- Not in the dossier, now read: the skin style every control was created from (`170 AquaBlue.BTN_Ok`: 1,018 controls), the alignment kept in every font record, and frames (border type, background and border colours; read by shape, unverified).
- A window can keep four more bytes per control before the record of the control's kind (118 controls of one window here): the decoder now finds where the record starts instead of assuming it, which is what made fixed positions hold for every control.
- The evidence folder carries all of it in the dossier's shape (`input_type`, `input_mask`, `h_align`, `Inside X position`, `Return format`, column `flags` and `column_index`, report `bands`…), so `screen_layout.py` needs no PDF for them; layouts also carry `style` and `frames`, and the starter's `LegacyControl` types them.
- Measured with the PDF removed on four windows (287 controls): equal to the layouts made with the dossier on those fields but 9 caption widths and 2 column input types. Still PDF-only: the alignment and input type printed for combos, radio buttons and statics, a table's own options, the remaining tick-mark properties, check-box and radio images.
- The field map no longer learns what is read exactly (12 strong entries left); a column's cell is learned under its column's name. Unexplained differences: 376 of 1,148 window controls have none (was 332).
- `docs/windev-file-formats.md`: a table of the records of each kind, and the search that found them (every offset from the block end, the chunk end and the strings before, kept when it explains every control).

## 2026-11-10 — evidence levels, a learned field map and an audit of what is still unexplained

- `scripts/windev_fieldmap.py`: with every string of a chunk replaced by one byte, a position means the same in every element of a kind. `learn` finds the position that explains each dossier property, tests it on windows left out of the learning and keeps as `strong` only what predicted them all and fits nowhere else; `audit` lists, per element, the bytes that differ from the usual value of its kind and that nothing explains. `scripts/windev_fieldmap.json` ships the strong entries learned on the second migration (14 properties: input type, calendar button, return format, row height, table and column options); a dossier of some windows of another project completes it. Weak entries (79 here: properties the project never varies enough, or that always change together) are never applied.
- `windev_decode.py`: plane (1,144/1,144 against the dossier), fonts as `LOGFONT` records with the text colour, captions of radio/check-box/menu options, SQL of queries embedded in windows and reports (19 of 20; the dossier has none), learned `properties` per element, `audit.json`, and learned properties written into the evidence folder in the dossier's form.
- `prepare_evidence.py` learns a project map when a dossier exists and records `decoded_audit`; `unit_evidence.py` packs carry the unit's unexplained differences, fonts and embedded query SQL.
- `docs/extraction-strategy.md`: four levels of evidence (read exactly, learned strong, learned weak, unexplained), how each is proven, the procedure for a project that cannot print its dossier, how to close what is left (a small dossier, one changed property, the thumbnail, the running application) and rules for agents citing each level.
- `scripts/code_map.py` (run by `prepare_evidence.py`, carried in unit packs): per unit the tables read, written, deleted, assigned and bound with `path:line` sites, queries, procedures of other units, windows and reports, classes, project globals; per table its readers and writers; plus what a text search cannot see (`dynamic` sites, names in SQL that are no table of the analysis, procedures no other unit calls). On the second migration: 149 units, 32 of 32 tables referenced, 34 units changing data, 296 dynamic sites.
- `windev_decode.py` writes `project/`: the project's own code from a binary `.wdp` as text (220 lines: constants, connection set-up, schema update — until now only in the dossier), the project explorer's folders with their elements, and the files each element uses from the `.wdu`.
- Field map: properties between two optional records are learned per exact length; a numeric property is no longer skipped because its name contains a text word; two different properties at one position are both weak (17 strong entries, now with a button's number of image states and an edit's horizontal alignment).
- Brought in the WINDEV 28 English dossier and compile-folder fixes from the `fix/windev28-english-dossier-and-legend` branch, which this branch lacked.
- More read from the source: a control's order among its siblings (numbered 1..n in 148 groups), a window's menu tree, what each report control prints (`linked_item`, `content`), fonts passed into the evidence folder and into `screen_layout.py` (`font`, `fonts`). Report geometry and the order count as explained in the audit: 332 of 1,148 window controls now have no unexplained difference, the rest a median of 2.
- `scripts/audit_decisions.py`: one row per control with unexplained differences in `docs/evidence/audit-decisions.csv`, a gate (`--require-complete --unit`) and stale detection. The mapping and review skills, the window and report spec templates, the stage and kickoff prompts, 04 and 10 now use the decoded evidence, its citation forms and this gate.
- Starter UI kit: `LegacyControl.font` / `fonts` and `fontStyle()`; `controlBox()` applies the control's source font (face, pixel size, weight, style, colour) when the layout has one, nothing otherwise.
- Field map learning: a value a held-out round never saw abstains instead of counting as wrong, a mask the dossier prints as `0` equals an empty one, and a strong entry now always needs 3 of the rarer value (15 strong entries on the second migration).
- Measured with the PDF removed: plane and input type now also equal the validated layout. Still open without a PDF: alignment, input mask and size, caption width, image state counts, table options, check-box images. 262 of 1,148 window controls have no unexplained difference; the rest a median of 3 (p90: 9).

## 2026-11-09 — the sources decoded: no dossier needed for geometry, captions and SQL

- `scripts/windev_decode.py`: `internal_properties` is base64 of an 8-byte header, a fixed-key byte cipher and an LZW block of property chunks; binary `PCS` files (`.WDR`, `.wdp`, `.wda`, `.cpl` copies, `.cache`) hold the same LZW blocks without the cipher. The tool decodes both: per control position, size, caption, tooltip, state, tab order, anchors and rates, linked item, group, button type; column width and caption; report geometry in mm; every query's SQL; project code of a binary `.wdp`; a thumbnail of each window and report. `--dossier` counts agreement with a dossier extract per field; `--raw` and `--blocks` keep the bytes for mapping more.
- Measured on the second migration's project (file format 25): 3,993/3,993 values decoded, WINDEV's own bytes reproduced on re-encoding for 3,890; against the dossier every compared field equal (size 1,069, position 843, tab order 1,034, state 1,021, button type 588, anchor rates 1,130, report geometry 493) and captions 819/820 with the accents the PDF had lost; 5/5 queries. Until now these came from the PDF only, and a project too large to print had none of them.
- `docs/windev-file-formats.md`: the format, which chunk holds what, the common control block field by field, what each project file gives a migration (`.wdu` asset list, `.WPF` profiler run, `.REP` data locations…), how to name one more property, what stays outside the files, how the routine and key were obtained and the licence caveat.
- 00, 06, README and scripts/README: decode first, dossier as the check and for what is not named yet (masks, planes, tick-mark properties, full-size images).
- `prepare_evidence.py` runs the decoder and records `decoded`, `decoded_coverage` and (with a dossier) `decoded_calibration` in `analysis-local/latest.json`.
- The decoded values now feed every tool, with the dossier as the fallback. `windev_decode.py --evidence` writes a folder in the dossier extract's shape — decoded captions, titles, geometry, tab order, state, Visible, button type and images, anchors and SQL over a copy of the PDF extract, or alone when there is no PDF — and `prepare_evidence.py` records it as `dossier` in `latest.json` (the PDF extract as `dossier_pdf`), so `evidence_report.py`, `render_layouts.py`, `screen_layout.py` and `unit_evidence.py` read it unchanged. `inspect_windev.py` fills its layout geometry from `internal_properties` when the source has none readable; `screen_layout.py` takes a column's width from the source first (right for columns sharing a name across tables).
- More fields named and checked against a fresh dossier extract: Visible (802/802), window title (112/112), button image, background image and states (588/589), kinds from type codes, tab panes with their captions, and where a tab's panes start (two tab styles measured), which gives a window position to every control except those in table cells (1,126/1,126).
- Measured end to end on the same project with the PDF removed: the layout of a 77-control window equals the dossier-validated one on every position, size, kind, anchor, tab order, state, Visible tick and button image. Still PDF-only: planes, other tick-mark properties, alignment, masks, input types, caption widths, table options. Decoded captions keep trailing spaces the PDF text had lost (`"Moldes: "`). The encoded predefined actions decode but their records are not named.

## 2026-11-06 — lessons from a second migration (production management, WINDEV 28 / HFSQL Classic)

- HFSQL ANSI ODBC export: `scripts/windows/hfsql-export.ps1` + `HfSqlOdbcAnsi.cs` read HFSQL Classic files through the driver's ANSI entry points in 32-bit Windows PowerShell (hash-checked copy, temporary per-user DSN always deleted, rows = `COUNT(*)` before and after per table) when `export_odbc.py` crashes on HFSQL 28 (exit 139 / access violation); `hfsql_jsonl.py` converts its JSONL into `export_odbc.py`'s `data.sqlite` + CSV + `manifest.json` through the same `export()` (now with an optional `info`). Real run: 30 tables / 24,915 rows, counts agree. Method first used in the gestao-oficinas migration.
- Production-build smoke test: the packaged app of the second migration opened blank while the dev server and all flows passed — Vite inlined skin PNGs under 4 KiB as `data:` URLs in the build only and the starter's skin resolver refuses them. The starter sets `build.assetsInlineLimit: 0`, adds `npm run smoke:prod` (`vite preview` + `ui-check/prod.smoke.spec.ts`) to `verify` and a unit test pinning the setting; `templates/ui-check/prod.config.ts` + `prod.smoke.example.spec.ts` for other foundations.
- Starter window chrome: layouts without `RADTitle` and without extracted system buttons get a system title bar above the client area (`wd-frame--native`), as WINDEV control coordinates are client-relative — the close box no longer covers top-right buttons (layout match 32 → 79 % on a real form). Skinned buttons get `wd-button--skin` with a skin-specific caption colour (`--wd-skin-button-color`, `--wd-skin-button-text-shadow`; neutral default). Unit tests for both.
- UI check template: optional `url` per window and optional `open`, a `windowSelector` (`<W>` = window name) for windows that are not a `data-testid`, an `openWindow` hook module (`hooks`, `hooks.example.ts`) for login/launcher navigation, and a `globalSetup` warm-up (`warmup.ts`) because Vite's cold first load exceeded the first test's navigation timeout. Existing configurations behave as before.
- `scripts/functional_cases.py`: builds `docs/functional-acceptance.json` from one executed run (Vitest + Playwright JSON reports) and the parity rows' test citations, one `FC-<unit>` case per screen/report; verified only when every cited test ran and passed (stricter than the project version it comes from, which ignored absent tests); manual cases, platform entries and their runs are kept. Tests include the validator accepting its output.
- Verification wave packet in `templates/prompt-stage.md` (and 05): one agent per family moves `implemented` rows to `verified` with tests that fail without the behavior and fixes what they expose. Measured: 9 parallel families, 426 → 1,460 verified rows, 13 bugs the implementation wave missed. Pitfalls: quote CSV test titles containing commas (one agent broke 9 rows; `parity_check.py` flagged invalid statuses); worktrees lack `legacy/`, so `--check-files` runs only in the main checkout.
- Docs: Windows installer pattern for a Node/TS server + Tauri app (02: NSIS per-user setup with bundled `node.exe` and server, database in `%LOCALAPPDATA%`, `READY`/`FAILED` stdout protocol, first-run import wizard with staging and one-rename promotion, headless `--import-legacy --yes`); import rule: renumber duplicate unique ids only in unreferenced, allow-listed columns, each change in the import report (08); QA of the installed app through WebView2 remote debugging + Playwright `connectOverCDP`, which found the blank packaged window (02, 10); a server trusting client-sent sessions listens on 127.0.0.1 only until real authentication exists (02, 07).
- Second verification sweep (`templates/prompt-stage.md`): harness per behaviour kind (report models, temp folders, fake timers, fault injection), owner question files with the current choice, counted leave-reasons. Measured: 1,460 → 1,625 verified, 19 more bugs, 163 owner questions.
- Starter combo: "no selection" is re-applied after every render; with a dependency list React silently re-selected the first option on any unrelated re-render (seen when an async start-up step added one).
- `scripts/functional_cases.py` resolves a short SHA or ref to the full SHA: the validator accepts only 40-hex commits, and a short one left every case unassessed (0 %) without an error.
- WLanguage traps (09): `Complete` truncates (the reverse-pad idiom keeps the last characters); `int + "text"` concatenation is not proven.
- Skin QA against the running legacy app (10): `skin_assets.py` keeps one animation frame per button state (stacked frames drew striped buttons; tests added); window-background 9-slice measured on the image; unnamed skin pieces (table titles, combos, edits, `.sty` font); menu bar above the client; starter radio groups draw their caption above the options. "No caller" did not prove a dashboard widget dead.
- Dossier check marks of WINDEV 28 PDFs with an embedded subset font: these pages are scaled (`0.12 0 0 0.12 0 0 cm`), draw text as TJ arrays and stroke each half of a ✓ separately, so `controls_with_flags` stayed at 0 and planes, Visible ticks, column ticks and anchors never reached the layouts. `dossier_extract.page_content` rebuilds the plain form from pypdf's decoded text and transformed paths; the narrower window property grid (columns 170 pt apart) and rotated column headers (spans moved by the marks' median offset) are read; overview rows keep the plane and cut names ("edt_quantidade_proce") join their control. Real run: windows with flags 0 → 111/112, controls 0 → 1,069/1,415; the tick results matched the running legacy app (a column table's sort/search ticks, the front office's hidden buttons, a window without title bar). Tests rebuild such a page in a generated PDF.
- `screen_layout.py`: `plane` and dossier anchors (`anchoring`, `anchorRates` in percent, the UI kit's names); image names keep real spaces when the project folder has such a file ("SIXTIES TV0101.png" was turned into a missing "SIXTIESTV0101.png").
- Starter UI kit: table row lines start below the measured title row (they were offset by the title height in every table: "distorted lines"); a window whose dossier has no Title bar tick draws none; a button that is only a picture draws its state image at its own size, centred (WINDEV), not squeezed to 16 px; `LegacyControl.plane`.
- Lesson: a screen that renders all controls of a multi-plane window with hand-made boxes looks nothing like the original; check `coverage` in the dossier extraction before building screens, and treat `0/N` flags as an extraction bug to fix, not as missing evidence.
- Engineering baseline in the starter: ESLint + Prettier (`lint`, `format`, `format:check`, in `verify`), `.github/workflows/ci.yml` (Windows app checks, Rust), real-server flow examples (`templates/ui-check/server-*.example.ts`: built server per Playwright worker, PostgreSQL per worker on CI); chapter 10 lists the test layers. Measured on the second migration: 129 lint findings → 0 errors, 210 flows 55 → 19 min.
- Optional server add-on `templates/server/` (the UI starter still chooses no topology): named procedures that run unchanged on a Node server (PostgreSQL or embedded PGlite) and in the browser preview, one transaction per call; HAdd/HReadSeek/HModify/HDelete helpers checked against the catalogue and a Form/Table CRUD pattern with every legacy text as a parameter; ordered immutable migrations; `POST /rpc` server with a stdio `READY` control; HFSQL data import with quarantine, reconciliation against the export's counts and refusal to promote; `pg_schema.py` from the schema draft; 27 unit tests on in-memory PGlite. `ui-check/server-*.example.ts` now use `APP_*` variables. Lessons: PGlite runs one transaction at a time (a shared nesting counter ran concurrent work outside a transaction); imported automatic ids need their identity sequence advanced.
- Starter window runtime from the second migration (`src/runtime/windows.tsx`): Open with parameters resolving with Close(value), OpenChild, modal openers, the Closing event (ReturnToCapture), Esc = Abort button, ..Title at runtime. Tables sort on a column-title click and search with the magnifier by default; decimal edits follow the regional separator. `src/domain/wl/`: a first tested set of WLanguage built-ins (strings, dates and durations in ms, exact decimals, file paths).
- `scripts/merge_parity.py` (per-unit parity CSVs → aggregate, for parallel workers). `screen_layout.py` now fills geometry and column widths from the dossier control tables, sets dossier kinds, joins PDF-wrapped words and normalizes RAD kind names, so the separate per-project fix step is no longer needed (second migration: 55 layouts differed from the fixed ones before, 6 after, all deliberate).

## 2026-10-26 — reusable workflow verification

- Extract configurable Playwright CRUD/reopen, cancel, invalid-save, search/selection and confirmation assertions with independent persistence snapshots and explicit business expectations.
- Add two SQLite-backed synthetic consumers, automatic-ID/reload checks and negative tests detecting missing writes, unrelated mutations and rejected writes. Configure the same helpers against two existing application workflows during extraction.
- Point migration agents to the test contracts; keep application-specific expectations, parity witnesses and native acceptance explicit.

## 2026-10-26 — reusable migration starter

- Add a new-directory project generator and deterministic, ownership-checked RAD screen generation from extracted layouts; handwritten business bindings remain separate.
- Vendor reusable React/window/table/dialog controls and Paged.js/Chromium reporting behind application-neutral contracts, with synthetic demos and tests. No customer evidence, skins, credentials or business rules are distributed.
- Reuse existing packages for interaction, pagination and PDF output; generated scaffolds do not promote parity or native acceptance.
- Direct kickoff, framing, agent, roadmap and stage templates to the starter; preserve existing repositories and extend baseline checks with project acceptance gates.

## 2026-10-26 — functional acceptance and strict parity

- Define functional readiness against complete approved target scope and executed behavior assertions, independently of strict parity/source confidence and platform evidence.
- Recognize source-derived checks for readable legacy rules; retain encoded properties and native behavior as explicit evidence gaps.
- Align workflow and agent/stage instructions; passing tests and built links do not create an acceptance percentage.
- Add the portable acceptance validator, primary functional dashboard and synthetic pending template, with tests for missing scope, stale witnesses, independent parity and platform evidence.
- Read only authoritative aggregate/seed snapshots for progress history when present; normalize Git paths across platforms.

## 2026-10-26 — parallel implementation after a proven workflow

- Broad workflow-family waves with isolated writers, lean evidence packets, frozen deliveries and one integration owner for contracts, verification and tracking.
- Separate initial target implementation, acceptance and unresolved legacy knowledge; preserve final parity/native gates and disclose the accepted review policy.
- Reuse one active brief and rolling handoff; align kickoff/stage/roadmap templates and honor project-specific Git authorization.

## 2026-10-23 — a cold start that follows only the guide

A fresh agent given only the kickoff prompt and the guide, on a folder with the project dropped in as is, found 21 problems the earlier runs' detailed briefs had hidden. Fixed:

### Added
- Kickoff prompt: "Stop after: framing | foundation | everything", to review the analysis before any code is written.
- 06 §7 "wiring every later step relies on": scaffold, the `package.json` scripts (`verify`, `ui:check`, `parity`…), where the UI check, its config and the skin kit go, the browser-preview fake backend, CI once a remote exists.
- `scripts/py.mjs`: runs Python as `python3` or `py` so npm scripts, the UI check and the commit hook work on Windows.

### Fixed
- Agent-neutral wording: `AGENTS.md` lists `npm run ui:check` (not an undefined `test:e2e`) and says `py` on Windows; `CLAUDE.md` only for Claude Code.
- Commands that failed as written: map-element's validate block, two `parity_check.py` calls without the matrix, the skin-asset command in the roadmap.
- map-element covers table groups and queries (no evidence pack for them); specs go to `docs/screens/` or `docs/reports/`.
- Paths assumed `legacy/code/` and `legacy/docs/`; the project folder can sit anywhere under `legacy/`.
- Gaps are recorded in `docs/legacy-inventory.md` (the evidence report is regenerated).
- Pillow added to the setup; skills install without nesting; PowerShell install lines; portable pack diff and compiled-file search.
- Pull and push only when a remote exists and the project allows it; closing order: update, regenerate, then commit.
- A review fallback for agents that cannot start a separate session; the guard is the human's to install.
- The UI check's example config no longer hides controls; the parity template's rule row uses the unit as `element`; `assumed` listed with the confidences; ROADMAP rows 0–1 Done when created after stage 0; PromptInit skips steps the kickoff already did.

## 2026-10-23 — drop the project folder in as is

### Changed
- Sanitising is no longer a general step: demo or test data is used as is; only personal data is anonymised before it is committed or shared.
- 00 §E split into what is needed to start (project folder in text format with `.cpl`, dossier PDF, `.xdd`, the data files) and what comes later when a slice needs it (report samples, recorded scenarios, runtime screenshots); the SQL script and query exports are no longer asked for (schema draft, dossier).
- Kickoff prompt: when `legacy/` holds HFSQL files and no data copy, the agent exports them itself on Windows (ODBC data source on a copy, `export_odbc.py`).
- `prepare_evidence.py` finds the dossier PDF and the `.cpl` compile folder anywhere under `legacy/` (fixed layout first); `skin_assets.py` searches `legacy/` for images. The WINDEV project folder can be put in `legacy/` unchanged: on the real project, the same evidence as the structured layout (125 elements, 12 questions, 17 encoded actions).

## 2026-10-23 — lessons from a large agent-driven port (Bun, Zig → Rust) and a mapping review

### Added
- `docs/porting.md` in stage 0 (mapping prompt step 1b): the project's concrete layer over chapters 09 and 07 — for each construct the app uses, a link to its trap and where and how this code base ports it (command, component, example file); no repeated explanations. Slices follow it (AGENTS rule 12, stage prompt, review skill), which keeps 20–30 slices consistent.
- An independent adversarial review and one fixer for each unit's mapping and each slice; a second reviewer only where a mistake is costly and tests catch it poorly (money, stock or totals, the data import, deleting or overwriting data, or a multi-window workflow).
- AGENTS rule 11: several agents in one checkout never stash, reset, clean or rebase, commit only their own files, run slow commands one at a time.
- Reviewers run in a fresh context and do not read the implementer's handoff or reasoning; they assume the code is wrong. A finding repeated across slices becomes a rule in `docs/porting.md` or `AGENTS.md` (fix the process, not only the code).
- Review skill rejects stubs or mocks behind `verified` rows, skipped/deleted/weakened tests, and workarounds that need a paragraph to justify.
- Roadmap: a cleanup slice after the first 2–3 slices and then every few (port faithfully first, make idiomatic after).

### Changed
- `parity_check.py --element`: the summary covers only those units.
- The answer sheet's `Proposed` cell is refreshed on unanswered lines when the evidence is regenerated; answers are never touched.
- Review-mapping: checks on `parity.csv` with `--note`, a sorted JSON diff of packs, strings in compiled files, and finding units by name (a window's file name can differ: `WIN_WIN_Teclado.wdw` holds `WIN_Teclado_Alfa`); `assumed` label.

## 2026-10-23 — one prompt to start

### Added
- `templates/kickoff-prompt.md`: one prompt for an autonomous agent (Claude Code, Codex…) to run the whole migration — setup, evidence, data profile, mapping, framing with defaults, foundation, then slices in roadmap order — resuming from the roadmap and handoff when restarted; states whether the data is demo or personal.

## 2026-10-23 — profile the real data

### Added
- `scripts/data_profile.py`: profiles a copy of the legacy data (SQLite staging file or the ODBC exporter's CSV folder) against the schema draft — per column nulls, empty strings, shapes, lengths, values not parsing as the WINDEV type, zeros, constant columns, spaces, line breaks, binary composite keys; duplicates per unique key; orphans per link. Counts only, no records. 4 s on the real project's 180,000 rows.
- 08 "Profile the data before deciding the schema", with what the real data showed (composite keys exported as binary, unused generated link columns, stored totals always 0, 0 meaning empty, empty dates, orphans and duplicate identifiers, outliers, negative stock).
- `export_odbc.py` writes a lossless `data.sqlite` beside the CSV files (NULL apart from empty strings, bytes as BLOB) and checks rows read against each table's `COUNT(*)` (fails on a difference); the manifest adds null and binary counts per column, the driver and the Python architecture. The real project's first conversion damaged composite-key bytes, emptied a composite link column and kept no source counts; nothing irreplaceable was lost (all rebuildable from their parts).
- Windows export: matching Python and HFSQL ODBC architectures (32/64-bit), with the observed 32-bit workaround (PR #2).

## 2026-10-23 — fixes from a fresh agent building a slice alone

A fresh agent with no human mapped, built and scored the vehicle list and form on the pilot (verify green, pixels 97.8 %, layout 76 % / 89 %) and reported 20 frictions. Fixed here:

### Changed
- Every slice clicks through its golden scenarios in the UI (`ui-check/<slice>.flows.spec.ts`, example from the pilot's vehicle slice: 5 flows, all passing). The UI check alone only proved structure and look.
- One rule for silent evidence (`AGENTS.md`): an answer, else a proposal (confidence `assumed`, may be verified, counted apart on the progress page), else the safest option with a `U-` item. A proposal that makes something destructive easier takes the safe choice until answered. Never stop for a question.
- ADRs decided by evidence or default are Accepted at once; the owner may supersede them.
- `parity_check.py`: confidence `assumed`; renamed seed rows matched to their new ID; `--element A,B` scopes every check (rule rows by context); `--check-files` resolves seed paths under `legacy/`; note summaries printed.
- Progress page: rule rows counted under their screen; a block renamed by newer tools is not counted twice; "on assumptions" shown.
- UI check: score floor (pixels 90 %, layout 60 %); fails on an image that does not load (fetched and type-checked: dev servers answer missing files with HTML 200); refuses evidence paths outside the repository. Visual records store relative paths.
- Skin kit: `WdWindow onClose` — a child window's close box closes that window, not the application.
- `legacy/images/` (00 §E): the project's images; `skin_assets.py` reads it by default and fails on a missing asset.
- Dossier: `Displayed item`, `Display mask`; layouts give combos and lists their caption width.
- Roadmap template: schema v1 and golden data cover every column; the skin-kit slice provides a temporary menu; deferred items name their slice. Map-element: where rows go (per unit in stage 0, then `parity.csv`); `element` is the unit on rule rows.
- Tool updates (06): re-run evidence, verify and the parity check before committing. CLAUDE template no longer claims hooks that are optional.
- Validate-button proposal says what an early `RETURN` does; the delete-confirmation default is the safe button until answered.

## 2026-10-23 — nothing waits for the human

### Added
- Every encoded-action group, runtime question and embedded report query gets a proposed answer with its basis: skin-template button names shared by the group, button types, the button's own code (`..ReturnedValue` set ⇒ the window closes), the one report a window's compiled code names that no code calls, the browsing table of the window that prints a list report, WINDEV conventions, or a labelled default. On the real project all 17 groups and 12 questions are proposed (2 by default).
- Answer sheet `Proposed` column; mapping cites `proposed: A-xxxxxx` / `proposed: Q-nn` and says "assumed"; an answer that differs reopens those rows.
- The event legend records whether the project skins WINDEV's message and dialog boxes (`WINDEVMESSAGEBOX`/`WINDEVDIALOGBOX` in the compile folder).

### Fixed
- "Validate button with no Close()" looked at the whole window's code, case-sensitively: a lowercase `close(` was missed and any `Close(` elsewhere hid the question. It now reads the button's own code.

## 2026-10-23 — lessons from building one slice in the legacy skin

### Added
- `templates/ui-kit/`: the skin as React primitives (window frame and title bar driving the native window, buttons, captioned edits, memo, message boxes) and its CSS, measured on the MediaPlayer template.
- ROADMAP foundation slice "skin kit" before the first screen slice.
- UI check scores every configured window against its dossier image, records it, and fails on a drop; edit captions read from their labels.
- Evidence report asks one question for all message boxes (title, icon, labels, default button): 97 boxes on the real project.

### Changed
- A slice is done only when every window and dialog it opens is built from its generated layout with the skin kit, passes the UI check and is scored (stage prompt, review skill).
- Framing default: visually near-identical UI with the project's own skin.

### Fixed
- `.gitignore` entries anchored to the root: an unanchored `legacy/` hid `src/ui/legacy/` from Git in the pilot.

## 2026-10-23 — screens that look like the legacy ones

### Added
- `scripts/screen_layout.py` (layout JSON per window from the evidence), `scripts/skin_assets.py` (skin images per state, magenta transparent), `scripts/visual_compare.py` (pixel similarity, edge overlap, side-by-side image, recorded per screen). The progress page shows "looks like the original" per screen. CI installs Pillow for their tests.
- Pilot: the client list rebuilt this way — edges 50 % → 75 %, pixels 89 % → 97 % vs the dossier image; behavior tests unchanged.

## 2026-10-23 — decisions for non-technical owners, progress page

### Added
- `scripts/progress_dashboard.py`: one self-contained HTML page of migration progress for non-technical readers (behaviors verified, screens and reports by stage, questions and decisions waiting, progress over time from Git), regenerated at each stage.
- Compile folder evidence: embedded report query items; compiled references between elements (each list window names the report it prints).

### Changed
- Framing (PromptInit): technical decisions are made from evidence and recorded as ADRs the owner can overturn; the owner gets at most seven plain-language business questions with recommended defaults; the WINDEV person gets the answer sheet. ADRs record who decided (evidence, default, human).

## 2026-10-23 — one-command evidence, unit packs, answer sheet

### Added
- `scripts/prepare_evidence.py`: inspector, dossier, legend, evidence report, navigation, schema draft and layouts in one command (15 s on the real project), paths in `analysis-local/latest.json`.
- `scripts/unit_evidence.py`: one unit's evidence in one diffable JSON, including every slot that shares each encoded action ID.
- `docs/evidence/encoded-actions.md` answer sheet (action groups and runtime questions), written once and never overwritten.
- Dossier: table columns as controls (title, mask, binding, width, alignment, flags), table browsed file/items, window opening mode, size and close icon.
- `parity_check.py` reports `SRC-` rows the current seed no longer has.
- Skills and window spec: selection and display state, built-in control features, full dialog details, write failure paths, proposed changes kept for ADRs.

- `parity_check.py --note`: lints mapping notes and specs for open points written as prose ("not extracted", "unknown", "read from the image"…) without a `U-` id; `--check-files` for cited files.
- Round 6 checklist: keyboard row moves, refresh from other windows or users, second instance, records leaving the filter; interim defaults must be legacy behavior; window spec resize and style values.

### Changed
- Chapter 06 and the mapping prompt start from `prepare_evidence.py`; the inspector runs on `legacy/` so the XDD is included.

## 2026-10-23 — rounds 4–5 of the small-scale run

### Added
- `scripts/schema_draft.py`: XDD + dossier → type legend, draft SQLite DDL, per-column decisions.
- Encoded actions: code-less event slots with encoded properties listed per file, seeded as `encoded-action` rows and grouped by opaque action ID in the evidence report.
- `docs/navigation.md` generated from proven call sites (Mermaid), with unreached windows and reports listed.
- `review-mapping` skill (six ordered checks); window spec contract, layout and data edge cases; report spec edge cases.
- Dossier: report control checkboxes, margins, calculations and presets; analysis keys on wrapped rows; composite keys; `button_type`.
- Inspector: report bands in the layout; WINDEV number forms (`60.`, `4.e-003`).

### Fixed
- Seed IDs no longer depend on the folder given to the inspector (a root change orphaned every mapping row).
- Event legend: optional-event labels and Initialization (code 14).
- Window flags no longer polluted by headings and dates; tables continued on a new section page.

### Fixed (round 5, two harder windows)
- Encoded slots only inside event lists: columns' content, calendars and drop-downs were counted as actions (402 → 225 code-less slots, 80 → 14 distinct actions). Groups now include slots next to code.
- Event legend: elimination passes pair what is left once codes are known (Close, Resize, row and drop-down events), local procedures proven by their PROCEDURE line: 21 codes, no conflict.
- Dossier: CamelCase control kinds (`RadioButton`) no longer merge into the previous control; page margin found on pages with more headings than rows (controls with flags 771 → 877 of 877, analysis items with keys 135 of 135); the analysis JSON is named after its file, not its Windows path.
- Schema draft lists every column per table.
- Skill: inferred event codes go to `event-codes-inferred.md`; shared HFSQL context rule for cross-window effects.

### Changed
- `parity_check.py`: evidence must be `path:line`, a dossier/analysis/runtime reference or a file (JSON with its field); an `unmapped` row with described behavior must cite its `U-` item. Unresolved items are unit-scoped (`U-WFC-01`).

## 2026-10-23 — extraction fixes from the small-scale run

### Added
- Analysis item `keys` (Unique Key, Key with Duplicates) from drawn check marks: 126 of 128 items on the real project.
- Extraction `coverage` in the dossier `index.json`, with warnings when a dossier's layout or labels are not recognised (other WINDEV versions or UI languages).
- Report geometry in millimetres from the `.wde` sources (decimal positions were dropped).
- Callers give `<source file>:<line> (<function> in <caller>)`.

### Fixed
- Checkbox reader: column headers and text columns (Initial state, Button type, Plane, Nb. columns) no longer read as false flags; detail keys (Opacity) and code lines (IF …) no longer read as controls; the window name no longer read as a property; values centred or right-aligned under headers; tables continued on the next page; control names cut at 31 characters merged into the full name; layout measured from the page margin instead of fixed positions.
- report-spec: text-source column, start/end-of-document bands, orientation "not in dossier", shared borders; map-element skill: confirm "no caller" with a search, read `keys` and `coverage`.

## 2026-10-22 — small-scale mapping run with the dossier

A dossier-aware mapping run on two windows and one report (with the first pilot's window as an A/B case) drove these changes.

### Added
- Dossier checkbox properties read from drawn check marks: window `flags` for all 51 windows (e.g. `Indep. HFSQL ctx.` on in only 2) and per-control `flags` (Required input, Multiline, Password…).
- Caller index and "no caller" gaps in the evidence report; the project's first window from the dossier's overview page.
- `templates/report-spec.md`; a reports section in the map-element skill.
- Event legend covers reports (`.wce`): 327680 Open, 327692 Before printing, 327693 After printing.

### Fixed
- Dossier: capitalised control kinds (`Combo Box`), control details and report bindings parsed in page order, code listings no longer read as properties, report type, part overview pages kept, duplicate text removed (a third smaller).
- Callers matched case-insensitively (`open(win_sistema)`).

### Changed
- map-element skill: paths are defaults a stage prompt may override; read parsed fields and flags before raw lines; callers from the evidence report; a clear block with an unresolved outcome stays `specified` with the unresolved part as its own `unmapped` rule row.

## 2026-10-22 — evidence completeness

### Added
- `scripts/evidence_report.py`: coverage and gaps per element, platform-usage inventory with literal arguments, grouped runtime questions. On the real project: 4 gaps, 11 questions; it surfaced `servidor.ini`, the `WDModFic.EXE` startup schema update and two command-line modes.
- Dossier extraction now parses analysis items (captions, WINDEV types such as "8-byte real", sizes, defaults), supercontrol children (`SC_Form.EDT_Codigo`), control rows (initial state, input type) and report controls (type, millimetre geometry, bound item, data source).
- The inspector records each element's internal name, which can differ from its file name (`WIN_WIN_Teclado.wdw` holds `WIN_Teclado_Alfa`).

## 2026-10-22 — removed what did not work

### Removed
- The UI crawler (`plan_capture.py`, `windows/capture_app.py`, `templates/windows-capture-prompt.md`, `templates/github-capture.yml`, its WinForms CI test). On the real WINDEV 28 app it logged in but WINDEV exposed no menu items to UI Automation and it captured no windows; the dossier gives that evidence. Recorded in the README so agents do not retry it.
- The advice to decode `.fic` files from the schema: a homemade decoder was reliable for about a third of the real tables. Data export goes through the HFSQL ODBC driver.

### Changed
- `scripts/windows/` is now the ODBC data export only, with its honest status (tested on a real ODBC driver, not yet on HFSQL's).
- `render_layouts.py` and the UI check take captions and window images from the dossier extract; the UI check now fails on captions that differ from the legacy ones (it found 8 wrong captions in the pilot).

## 2026-10-22 — the dossier as primary evidence

### Added
- `scripts/dossier_extract.py`: WINDEV's project technical documentation PDF to per-element JSON and images (captions, tab order, masks, button types, images, query SQL/parameters/conditions). On the real project: 51 windows, 28 reports, 29 queries, 106 images.

### Changed
- The dossier is the first evidence source (00, 06, README, map-element skill); the capture kit becomes optional, for runtime behavior and data export, with the finding that WINDEV exposes no menu items to UI Automation.

## 2026-10-22 — build phase tested on a real WINDEV pilot

### Changed
- `AGENTS.template.md`: "No guessing" rules — unresolved legacy behavior is implemented as a flagged, reversible choice and its row stays `implemented`; no tests pinning unknowns or that cannot fail; new user-facing texts need approval; five checks before `verified`; re-read ADRs at the end of a stage.
- Review skill, stage prompt and chapter 10: a row whose behavior includes an implementer's choice is not `verified`.
- Chapter 05: mandatory review-fix stage per slice, with the pilot's numbers (8/18 over-claimed on first pass, 2/17 after rules and one fix stage); no ADR changes while a stage runs.
- PromptInit: evidence policy question for inferred event codes.
- Inspector lists every control and table column per window; `templates/ui-check/` is a Playwright control-coverage check with a new-vs-legacy screenshot report (validated on the pilot).
- `event_legend.py`: event-code meanings verified from WINDEV's own compiled labels in the `.cpl` folder (on the real project: 18 Click ×293, 17, 16, 15, 21, 33, 34, declarations), wired into the mapping prompt.
- Inspector extracts dialog resources (messages and buttons in every language, cancel button); WLanguage traps note the `cancel_button` ambiguity.
- `render_layouts.py` draws every legacy window to scale from source; the crawler matches controls by legacy position (estimating native frame offsets), labels captured trees with legacy names, identifies windows, and runs login steps by legacy names — all from running a real WINDEV 28 app on a GitHub Windows runner.
- `templates/github-capture.yml`: run the capture kit on a GitHub-hosted Windows VM from a private repository with fake data.
- Agent UI inspection: dev browser preview with the test fake backend, used in the pilot to click through the client list and form.
- Human runs every slice before Done (agents often cannot open GUI windows); foundations include an opt-in dev seed; spec-derived golden data is labelled as such; commit regenerated bindings with the change; README validation status.

## 2026-10-22 — unattended capture without WINDEV

### Added
- `scripts/plan_capture.py`: classifies every route to every window from the code (only-opens / review / writes) and whether windows write on open or close. On the test project: 22 windows reachable automatically, 42 with the review pass, 3 manual.
- Windows capture kit (`scripts/windows/`): `capture_app.py` drives the running app through UI Automation on a marked copy (screenshots, control trees, tab order, data-file hash guard); `export_odbc.py` exports every table to CSV through PC SOFT's HFSQL ODBC driver; step-by-step runbook.
- Windows end-to-end CI against a WinForms stand-in (login, menus, dialogs, data guard) and a real ODBC driver; it found and fixed five crawler bugs before any real run. `--probe` gives a go/no-go before a full capture.
- `templates/windows-capture-prompt.md`: lets a coding agent on the Windows PC run the whole kit (find install, safe copy, ODBC, export, capture, iterate, package).
- Chapter 10: historical data as golden checks when the legacy app cannot be run.

## 2026-10-22 — mapping skill tested on a real project

### Changed
- `map-element` skill rewritten from three real mapping runs plus a cross-review: unit rows by `element`, block definition, one level of callers/callees, encoded-property fallback, defined `confidence`/`status`/rule-ID/evidence conventions, shared event-code legend, controls only in the screen spec, self-validation.
- Mapping prompt starts with a shared `docs/mapping/event-codes.md` legend and merges per-unit parity files.
- `parity_check.py --element` validates one unit's file against its seed rows.
- 00: what can and cannot be done without a WINDEV machine.

## 2026-10-22 — validated on a real WINDEV 27 project

### Fixed
- Inspector: list items written as a bare `-` line (real WINDEV text format) gave every block the last event code of its list and leaked sibling control names into the path.
- Secret hints: `Password=`/`PWD=` only inside connection strings, not variables such as `sPassword=`; byte-identical sources (the `.ana` copy of the XDD) are marked `duplicate` and not seeded twice.

### Added
- WLanguage traps: SQL built by string concatenation (`HExecuteSQLQuery`) and `TableDisplay` refresh semantics, both heavily used in the test project.

## 2026-10-22 — agent-neutral guardrails

### Changed
- One guard rule set (`templates/agent/guard.py`) used by a Git pre-commit hook (`--staged`, every agent and human), the Claude Code hook (`--hook`) and other agents' hooks (`--command`, `--write`); also blocks `--no-verify`.
- Skills moved to agent-neutral `templates/agent/skills/` and named from `AGENTS.md`; short Claude Code / Codex setup in [04](04-project-memory.md#claude-code-codex-and-other-agents).
- Roadmap template has a Ticket column. Documentation tests also check `#anchor` links.

## 2026-10-22 — parity toolkit and full upstream coverage

### Added
- Chapters [09 — WLanguage traps](09-wlanguage-traps.md) and [10 — Parity and verification](10-parity-and-verification.md).
- Inspector: window/control path and raw event code per code block, procedure declarations, literal key counts, `--fallback-encoding`, `--extra-ext`, `--block-key`, a stable-ID `parity-seed.csv` and `secret-hints.json` (locations only).
- `scripts/parity_check.py` (closed-world parity gate) and `scripts/compare_exports.py` (golden master and import reconciliation).
- Deterministic guardrails: Claude Code `PreToolUse` hook guard with settings, and an agent-neutral Git pre-commit hook.
- Templates: CLAUDE pointer, local instruction files, mapping prompt, `map-element` and `review` skills, roadmap, parity CSV, window spec, golden scenario, compare config.
- Tests for every script and the hook guard; a relative-link check for all Markdown.

### Changed
- Restored upstream content that the first adaptation had condensed away: source collection layout and export how-tos, `/init_projet` tip, agent-VM rationale, nightly test machine guards, local instruction files, skills and hooks, roadmap fields, response preferences, anti-patterns, parallel mapping with cross-review, HFSQL feature table, platform services depth (telemetry, identity/Groupware, store, reports, jobs, mobile/real-time, DB admin) with glossaries.
- Architecture: one home per business rule, one save = one command = one transaction, generated IPC bindings, UI library/multi-window/global-state decisions.
- Review in four categories (adds parity gap). `docs/upstream-audit.md` now traces every upstream section.
- `templates/review-checklist.md` became `templates/claude/skills/review/SKILL.md`; `templates/behavior-parity.md` became `templates/parity.template.csv`.

## 2026-10-22

- Adapt the upstream French .NET playbook into an English TypeScript/Tauri desktop migration guide.
- Replace .NET/Velopack/VM assumptions with explicit TypeScript/Rust boundaries, native build verification, Tauri updates and deployment-specific persistence choices.
- Make planning and review assistant-neutral; provide agent instructions and parity templates.
- Add dependency-free WINDEV text/code and raw XDD schema inspection with synthetic tests.
- Keep upstream Git history, MIT license and provenance. No legacy business application data is included.
