# AGENTS.md — <App>

<2–3 lines: what the application does and for whom. Replaces the WINDEV/HFSQL application <legacy name>.>

Read `docs/runbooks/handoff.md`, `ROADMAP.md` and the ADRs touching your slice before changing anything.
Keep this file short (about 100 lines). Details live in `docs/`; local rules live in the nearest `AGENTS.md`.

## Repository map

- `src/ui/` — React screens. Control `data-testid` = legacy control name (e.g. `EDT_Customer`).
- `src/domain/` — pure TypeScript business rules. No React, Tauri, Node or I/O imports.
- `src/application/` — use cases and repository/command interfaces.
- `src/infrastructure/` — Tauri IPC (or API) adapters. `src/bindings/` is generated: never edit by hand.
- `src-tauri/src/commands/` — one Rust command per business operation, one transaction each.
- `src-tauri/migrations/` — ordered SQL migrations; committed ones are immutable. See local `AGENTS.md`.
- `docs/parity/parity.csv` — behavior parity matrix: the definition of done.
- `docs/porting.md` — this project's concrete pattern (file, function, component) for each WLanguage construct it uses, over `docs/wlanguage-traps.md`; every slice follows it.
- `legacy/`, `analysis-local/` — private, ignored, read-only evidence. Never execute legacy code.
- `skills/` — playbooks to follow; `scripts/` — evidence pipeline, parity gate, comparator, guard. Humans own `scripts/guard.py`, `.githooks/` and agent configuration: do not modify them.

## Where the legacy evidence is

For a slice touching window or report `<X>`, read: `docs/screens/<X>.md` or `docs/reports/<X>.md` (what to build), `docs/mapping/<X>.md` (behavior, rules, `U-` items), its rows in `docs/parity/`, and the images `docs/evidence/images/<X>.*` (designer image and layout drawing). Shared: `docs/schema/schema-draft.md` and the database ADR, `docs/navigation.md` (who opens what), `docs/evidence/encoded-actions.md` (answers, or the proposal used until answered), `docs/mapping/event-codes.md`.
Need more: `python3 scripts/prepare_evidence.py` regenerates `analysis-local/` from `legacy/` (paths in `analysis-local/latest.json`) and `python3 scripts/unit_evidence.py <X>` gathers everything about one unit. Cite evidence as `legacy/<path>:<line>`, `dossier: <X>/<field>` or a committed file — never a path inside `analysis-local/`.

## Non-negotiable rules

1. Verify before coding: read the real legacy source, schema, exports and library APIs. Never invent a column, table, control, rule or API member.
2. Every business rule cites evidence (`path:line`, export, screenshot) and a confidence: verified, inferred, assumed or unresolved.
3. Preserve legacy behavior unless an accepted ADR records the change. A screen that renders is not parity.
4. Data-structure changes are proposed to the human first. No silent destructive "fixes"; no editing committed migrations.
5. One user save = one command = one transaction. Validate input at the native/server boundary; parameterize all SQL.
6. Money, quantities and durations use the representation fixed in ADR-<n>; IDs above 2^53 cross IPC as strings. Check `docs/wlanguage-traps.md` when translating WLanguage.
7. No secrets in Git (licences, connection strings, tokens → environment variables or ignored local config).
8. Generated files (bindings, scaffolds) are regenerated, not edited.
9. Never claim a check passed unless you ran it. Record checks you could not run.
10. Do not re-open accepted decisions without new evidence. Read whole files before concluding.
11. Several agents in one checkout: never `git stash`, `git reset`, `git checkout -- .`, `git clean` or a rebase; stage and commit only the files you changed, by name; one writer per file; slow commands (full build, full test suite) run by one agent at a time. Separate sessions writing code get separate worktrees.
12. Port every WLanguage construct with its pattern in `docs/porting.md`; add a missing pattern there first.
13. If a guard is installed (`scripts/guard.py`, pre-commit), a block is deliberate: report it in the handoff; never bypass it (`--no-verify`, renames, other paths).

## Work autonomously; ask the human only for these

Run the stage end to end without asking for confirmation. Stop and ask (or record under "Decisions needed" and continue with other work) only when:

- a decision belongs to the human: an ADR choice, a change to legacy behavior, an unresolved `U-` item that blocks the slice and has no interim default;
- an action is destructive or irreversible: deleting or rewriting data, a destructive migration, force-pushing, deleting files you did not create;
- something needs a person or a machine you do not have: WINDEV, the running legacy app, credentials, a Windows or printer check;
- the evidence contradicts an accepted decision.

## No guessing

When the evidence does not say what the legacy app does (encoded designer properties, an unknown event code, a binary query), take the first of these that exists:

1. **An answer** in `docs/evidence/encoded-actions.md`: it is evidence (`runtime: A-xxxxxx`).
2. **A proposal**: the answer sheet's `Proposed` column, a `proposed:` line in `docs/evidence-report.md`, or an ADR decided by default. Build it; the row's `confidence` is `assumed` and cites it (`proposed: A-xxxxxx`, `proposed: Q-nn`, the ADR). Tests may pin it and the row may reach `verified`; the progress page counts it as "on assumptions" until a person confirms it. **Exception:** when the proposal makes something destructive easier (the default button of a delete confirmation, an overwrite), use the safe choice instead and keep the row `implemented` with a `U-` item until it is answered.
3. **Nothing**: implement the safest reversible option, mark it in code with `// UNRESOLVED U-nn: <choice>`, list it under "Decisions needed" in the handoff, and keep the row `implemented` (or split the unresolved part into its own row). Do not write tests that pin it (sort order, selection after delete, Esc behavior, inferred colors): compare as sets or assert only what is known.

Never stop for an unanswered question: one of the three always applies.
- A user-facing text that does not exist in legacy (a new error message) is a choice: it needs approval before the row is `verified`.

Before marking a row `verified`, check all of these and report them in the handoff:

1. The cited test asserts the row's `target_behavior` and would fail if that behavior were removed (no tests that only check absence or always pass; a test that would still pass with the feature deleted is not evidence).
2. The test exercises the real path (not a placeholder or a mock standing in for the behavior under test).
3. No part of the behavior depends on an unresolved item or on a choice of yours that no proposal or ADR covers (`assumed` rows cite theirs).
4. If the target differs from legacy, `decision` names the ADR.
5. Re-read `docs/decisions/` at the end of the stage: ADRs added while you worked apply to your code too.

Identifiers you invent (test ids for controls that do not exist in legacy, helper names) are documented in the screen spec as non-legacy.

## Project-specific rules (filled in at framing, each backed by an ADR)

<Topology (local SQLite / shared server API), supported OSes, permissions model, report engine, grid/form libraries, update channel, external system access mode (read-only / limited writes / none)…>

## Commands

Python scripts run as `python3` on macOS/Linux and `py` on Windows (npm scripts use `node scripts/py.mjs`).

```sh
npm run verify          # typecheck + lint + unit + parity check: must pass before every commit
npm run ui:check        # UI check and click-through flows, browser preview with mocked IPC
npm run tauri -- build  # native package for this OS
python3 scripts/parity_check.py docs/parity/parity.csv --seed docs/parity/parity-seed.csv   # parity progress and validity
python3 scripts/progress_dashboard.py --title "<App>"   # docs/progress/index.html for non-technical readers
<golden scenarios, bindings generation, migration commands…>
```

## Skills (follow the file when the task matches)

- Review a stage → `skills/review/SKILL.md`
- Map a legacy element → `skills/map-element/SKILL.md`
- Review a unit's mapping → `skills/review-mapping/SKILL.md`

## Work tracking

Ticket key of the current slice: in `ROADMAP.md`. Branch `<KEY>-<slug>`, commits start with `<KEY>:`.

## Pointers

Architecture `docs/architecture.md` · WLanguage traps `docs/wlanguage-traps.md` · Data `docs/data-migration.md`
Screens `docs/screens/` · Golden scenarios `docs/golden/` · Decisions `docs/decisions/` · Handoff `docs/runbooks/handoff.md`

## Response preferences (a preference, not a rule)

<e.g. concise, no full listings unless asked — or detailed and explanatory.>
