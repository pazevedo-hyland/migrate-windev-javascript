# ROADMAP — <App>

Created after stage 0 and framing (kickoff prompt): mark rows 0–1 Done with their commits. Order follows dependencies: never start a slice whose dependencies are not `Done`. Status is updated when a slice closes; the handoff explains it.

| # | Phase | Slice | Ticket | Parity rows | Owner | Prompt | Deliverable | Depends on | Status |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Framing | Inventory, mapping notes, parity seed imported | MIG-1 | all `SRC-*` | implementer + sub-agents | `templates/mapping-prompt.md` | `docs/legacy-inventory.md`, `docs/mapping/`, `docs/parity/parity.csv` | — | To do |
| 1 | Framing | Topology, persistence, OS targets, permissions, reports, UI libraries | MIG-2 | — | human + planner | PromptInit | ADR-001…00n | 0 | To do |
| 2 | Foundation | Reuse compatible `templates/starter/` packages after framing (06 §7); generate in a new directory and integrate without replacing maintained files; wire project lint/parity/bindings/native gates into baseline verification | MIG-3 | — | implementer | prompt-stage | project `npm run verify` green locally; CI green when a remote exists | 1 | To do |
| 3 | Foundation | Schema v1 (every table with all its columns, from the schema draft) + golden data covering them + import dry run on the data copy | MIG-4 | `table` rows | implementer | prompt-stage | migrations, reconciliation report | 2 | To do |
| 3b | Foundation | Reuse starter UI controls/windows/dialogs; `screen_layout.py` → `generate_screens.py` for layout/catalogue, maintained adapters for actions/data; apply authorized skin assets and accepted visual policy (06 §7). Neutral previews and unresolved metadata stay explicit; scaffolded windows await business implementation and proof. The older `templates/ui-kit/` is an alternative for existing consumers | MIG-… | — | implementer | prompt-stage | shared UI, generated layouts, maintained bindings, checked skin assets and configured per-window checks | 2 | To do |
| 4 | Slice | <first complete workflow, e.g. customer → order → saved order> | MIG-… | RULE-…, SRC-… | implementer | prompt-stage | domain + command + UI (every window and dialog it opens, scored) + golden scenario | 3, 3b | To do |
| 5 | Cleanup | After the first 2–3 slices, then every few: extract what slices repeated (list/form, search, dialogs) into shared components, update docs/porting.md; behavior and parity unchanged | MIG-… | — | implementer | prompt-stage | shared components, slices using them, verify green | 4 | To do |
| 6 | Initial implementation (optional wave) | <independent workflow families, each with an owner and disjoint files> | MIG-… | <exact IDs per family> | coordinator + workers | current-stage / worker packets | real consuming paths, focused checks, integrated verification, explicit acceptance backlog | 5 | To do |
| 7 | Acceptance | <wave families> | MIG-… | <same IDs> | implementer + reviewer + human | prompt-stage | verified/excluded rows, golden/native checks and user trial | 6 | To do |
| … | | | | | | | | | |
| n | Cutover | Rehearsal, final import, acceptance | MIG-… | all | human | `08-data-migration.md` | signed acceptance | all | To do |

A deferred item names the slice that will own it. Statuses: To do / In progress / Blocked (reason in handoff) / Done. Parity progress: `python3 scripts/parity_check.py docs/parity/parity.csv --seed docs/parity/parity-seed.csv`. With a tracker, one slice = one ticket: put its key in the Ticket column, the branch name and commit messages.

Row 6 closes an initial implementation milestone only; row 7 retains acceptance. Independent families may proceed on established contracts while unrelated acceptance checks wait. Required schema/import/security foundations remain dependencies.
