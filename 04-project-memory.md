# 04 — Project memory

Copy and customize `templates/AGENTS.template.md` into the application's `AGENTS.md`. Keep it short: mission, repository map, accepted decisions, real commands, and links. If using Claude, a short `CLAUDE.md` can point to the same canonical instructions rather than maintaining conflicting rules.

Use these durable documents:

- `docs/architecture.md`: boundaries, transactions, IPC contracts and deployment topology.
- `docs/legacy-inventory.md`: sources, missing exports and coverage.
- `docs/behavior-parity.md`: traceability from legacy rule to target acceptance test.
- `docs/data-migration.md`: field mappings, transformations, reconciliation and recovery.
- `docs/decisions/`: numbered architecture decision records (ADRs).
- `docs/runbooks/handoff.md`: latest delivered work, actual checks, limitations and next steps.
- `ROADMAP.md`: dependencies, acceptance criteria and status per slice.

Keep observed legacy behavior separate from desired improvements. Version decisions and sanitized requirements; do not publish raw private analysis by accident. A handoff must state unavailable checks explicitly. Record contradictions and supersede decisions instead of silently rewriting history.
