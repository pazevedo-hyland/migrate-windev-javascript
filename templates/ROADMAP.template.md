# ROADMAP — <App>

Created after stage 0 and framing (kickoff prompt): mark rows 0–1 Done with their commits. Order follows dependencies: never start a slice whose dependencies are not `Done`. Status is updated when a slice closes; the handoff explains it.

| # | Phase | Slice | Ticket | Parity rows | Owner | Prompt | Deliverable | Depends on | Status |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Framing | Inventory, mapping notes, parity seed imported | MIG-1 | all `SRC-*` | implementer + sub-agents | `templates/mapping-prompt.md` | `docs/legacy-inventory.md`, `docs/mapping/`, `docs/parity/parity.csv` | — | To do |
| 1 | Framing | Topology, persistence, OS targets, permissions, reports, UI libraries | MIG-2 | — | human + planner | PromptInit | ADR-001…00n | 0 | To do |
| 2 | Foundation | Scaffold and its wiring (06 §7: npm scripts, ui-check, browser preview), `npm run verify`, bindings generation | MIG-3 | — | implementer | prompt-stage | `npm run verify` green locally; CI green when a remote exists | 1 | To do |
| 3 | Foundation | Schema v1 (every table with all its columns, from the schema draft) + golden data covering them + import dry run on the data copy | MIG-4 | `table` rows | implementer | prompt-stage | migrations, reconciliation report | 2 | To do |
| 3b | Foundation | Skin kit: the legacy look as UI primitives (window frame and title bar, buttons, edits, memo, table, message boxes) from `templates/ui-kit/` and the project's skin images (06 §7: `screen_layout.py` for every window, then `skin_assets.py --out public/skin src/ui/legacy/*.layout.json`; images it cannot find go under "Decisions needed" — ask for the skin template folder — and those windows' image checks wait); layouts generated for every window; a temporary menu that opens each built window until the legacy menu's slice | MIG-… | — | implementer | prompt-stage | `src/ui/legacy/`, `public/skin/`, ui-check scoring every window | 2 | To do |
| 4 | Slice | <first complete workflow, e.g. customer → order → saved order> | MIG-… | RULE-…, SRC-… | implementer | prompt-stage | domain + command + UI (every window and dialog it opens, scored) + golden scenario | 3, 3b | To do |
| 5 | Cleanup | After the first 2–3 slices, then every few: extract what slices repeated (list/form, search, dialogs) into shared components, update docs/porting.md; behavior and parity unchanged | MIG-… | — | implementer | prompt-stage | shared components, slices using them, verify green | 4 | To do |
| … | | | | | | | | | |
| n | Cutover | Rehearsal, final import, acceptance | MIG-… | all | human | `08-data-migration.md` | signed acceptance | all | To do |

A deferred item names the slice that will own it. Statuses: To do / In progress / Blocked (reason in handoff) / Done. Parity progress: `python3 scripts/parity_check.py docs/parity/parity.csv --seed docs/parity/parity-seed.csv`. With a tracker, one slice = one ticket: put its key in the Ticket column, the branch name and commit messages.
