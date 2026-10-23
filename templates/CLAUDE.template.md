# CLAUDE.md — <App>

@AGENTS.md

Claude-specific notes only; shared rules live in `AGENTS.md` (imported above).

- Guardrails: `.claude/settings.json` runs `scripts/guard.py --hook` before edits and shell commands; the same rules run at commit time for every agent. A block is deliberate: report it, do not work around it. Humans edit `.claude/` and `scripts/guard.py`.
- Skills: `.claude/skills/` mirrors `skills/` — `/review` after each slice; `/map-element <legacy file>` to map one window, report or procedure set; `/review-mapping <unit>` to cross-review it.
- Use subagents to read legacy sources in parallel; keep their findings in `docs/`, not only in chat.
