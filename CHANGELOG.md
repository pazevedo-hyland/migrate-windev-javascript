# Changelog

## 2026-10-22 — build phase tested on a real WINDEV pilot

### Changed
- `AGENTS.template.md`: "No guessing" rules — unresolved legacy behavior is implemented as a flagged, reversible choice and its row stays `implemented`; no tests pinning unknowns or that cannot fail; new user-facing texts need approval; five checks before `verified`; re-read ADRs at the end of a stage.
- Review skill, stage prompt and chapter 10: a row whose behavior includes an implementer's choice is not `verified`.
- Chapter 05: mandatory review-fix stage per slice, with the pilot's numbers (8/18 over-claimed on first pass, 2/17 after rules and one fix stage); no ADR changes while a stage runs.
- PromptInit: evidence policy question for inferred event codes.
- Inspector lists every control and table column per window; `templates/ui-check/` is a Playwright control-coverage check with a new-vs-legacy screenshot report (validated on the pilot).
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
