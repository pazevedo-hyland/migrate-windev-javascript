# ROADMAP — <App>

Order follows dependencies: never start a slice whose dependencies are not `Done`. Status is updated when a slice closes; the handoff explains it.

| # | Phase | Slice | Parity rows | Owner | Prompt | Deliverable | Depends on | Status |
|---|---|---|---|---|---|---|---|---|
| 0 | Framing | Inventory, mapping notes, parity seed imported | all `SRC-*` | implementer + sub-agents | `templates/mapping-prompt.md` | `docs/legacy-inventory.md`, `docs/mapping/`, `docs/parity/parity.csv` | — | To do |
| 1 | Framing | Topology, persistence, OS targets, permissions, reports, UI libraries | — | human + planner | PromptInit | ADR-001…00n | 0 | To do |
| 2 | Foundation | Scaffold, CI `npm run verify`, guards, bindings generation | — | implementer | prompt-stage | green CI on target OSes | 1 | To do |
| 3 | Foundation | Schema v1 + import dry run on sanitized data | `table` rows | implementer | prompt-stage | migrations, reconciliation report | 2 | To do |
| 4 | Slice | <first complete workflow, e.g. customer → order → saved order> | RULE-…, SRC-… | implementer | prompt-stage | domain + command + UI + golden scenario | 3 | To do |
| … | | | | | | | | |
| n | Cutover | Rehearsal, final import, acceptance | all | human | `08-data-migration.md` | signed acceptance | all | To do |

Statuses: To do / In progress / Blocked (reason in handoff) / Done.
