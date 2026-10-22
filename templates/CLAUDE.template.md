# CLAUDE.md — <App>

@AGENTS.md

Claude-specific notes only; shared rules live in `AGENTS.md` (imported above).

- Guardrails: `.claude/settings.json` runs `.claude/hooks/guard.py` before edits and shell commands. A block is deliberate: report it, do not work around it. Humans edit `.claude/`.
- Skills: `/review` after each slice; `/map-element <legacy file>` to map one window, report or procedure set.
- Use subagents to read legacy sources in parallel; keep their findings in `docs/`, not only in chat.
