# Changelog

## 2026-10-22 — agent-neutral setup and project tracking

### Added
- [GETTING-STARTED](GETTING-STARTED.md) checklist, [11 — Agents](11-agents.md) (Claude Code, Codex, others) and [12 — Project tracking](12-project-tracking.md) (Jira structure, generated stories, progress and trend reporting, estimating).
- `scripts/status.py`: parity and roadmap progress report (Markdown/JSON) and tracker-importable work items.
- `ticket` column in the parity matrix; `Ticket` column in the roadmap template.

### Changed
- One guard rule set (`templates/agent/guard.py`) used by a Git pre-commit hook (`--staged`, every agent and human), the Claude Code hook (`--hook`) and other agents' hooks (`--command`, `--write`); also blocks `--no-verify`.
- Skills moved to agent-neutral `templates/agent/skills/` and named from `AGENTS.md`; Claude Code copies them to `.claude/skills/`.
- Documentation tests also check `#anchor` links.

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
