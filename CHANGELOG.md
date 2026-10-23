# Changelog

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
