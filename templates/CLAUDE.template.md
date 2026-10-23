# CLAUDE.md — <App>

@AGENTS.md

Claude-specific notes only; shared rules live in `AGENTS.md` (imported above).

- Guardrails (optional, installed by a human): when `.claude/settings.json` exists it runs `scripts/guard.py --hook` before edits and shell commands, and `git config core.hooksPath .githooks` runs the same rules at commit time. A block is deliberate: report it, do not work around it. Without them, run `python3 scripts/guard.py --staged` before each commit. Humans edit `.claude/` and `scripts/guard.py`.
- Skills: `skills/` (`.claude/skills/` mirrors it when installed) — review after each slice; map-element to map one window, report or procedure set; review-mapping to cross-review it.
- Use subagents to read legacy sources in parallel; keep their findings in `docs/`, not only in chat.
