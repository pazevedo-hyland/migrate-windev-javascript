# ROADMAP — <App>

Order follows dependencies: never start a slice whose dependencies are not `Done`. Status is updated when a slice closes; the handoff explains it.

| # | Phase | Slice | Ticket | Parity rows | Owner | Prompt | Deliverable | Depends on | Status |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Framing | Inventory, mapping notes, parity seed imported | MIG-1 | all `SRC-*` | implementer + sub-agents | `templates/mapping-prompt.md` | `docs/legacy-inventory.md`, `docs/mapping/`, `docs/parity/parity.csv` | — | To do |
| 1 | Framing | Topology, persistence, OS targets, permissions, reports, UI libraries | MIG-2 | — | human + planner | PromptInit | ADR-001…00n | 0 | To do |
| 2 | Foundation | Scaffold, CI `npm run verify`, guards, bindings generation | MIG-3 | — | implementer | prompt-stage | green CI on target OSes | 1 | To do |
| 3 | Foundation | Schema v1 + import dry run on sanitized data | MIG-4 | `table` rows | implementer | prompt-stage | migrations, reconciliation report | 2 | To do |
| 3b | Foundation | Skin kit: the legacy look as UI primitives (window frame and title bar, buttons, edits, memo, table, message boxes) from `templates/ui-kit/` and the project's skin images; layouts generated for every window | MIG-… | — | implementer | prompt-stage | `src/ui/legacy/`, `public/skin/`, ui-check scoring every window | 2 | To do |
| 4 | Slice | <first complete workflow, e.g. customer → order → saved order> | MIG-… | RULE-…, SRC-… | implementer | prompt-stage | domain + command + UI (every window and dialog it opens, scored) + golden scenario | 3, 3b | To do |
| … | | | | | | | | | |
| n | Cutover | Rehearsal, final import, acceptance | MIG-… | all | human | `08-data-migration.md` | signed acceptance | all | To do |

Statuses: To do / In progress / Blocked (reason in handoff) / Done. Parity progress: `python3 scripts/parity_check.py docs/parity/parity.csv --seed docs/parity/parity-seed.csv`. With a tracker, one slice = one ticket: put its key in the Ticket column, the branch name and commit messages.
