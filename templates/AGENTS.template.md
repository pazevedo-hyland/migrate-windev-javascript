# AGENTS.md — <App>

<2–3 lines: what the application does and for whom. Replaces the WINDEV/HFSQL application <legacy name>.>

Read `docs/runbooks/handoff.md`, `ROADMAP.md` and the ADRs touching your slice before changing anything.
Keep this file short (≈60 lines). Details live in `docs/`; local rules live in the nearest `AGENTS.md`.

## Repository map

- `src/ui/` — React screens. Control `data-testid` = legacy control name (e.g. `EDT_Customer`).
- `src/domain/` — pure TypeScript business rules. No React, Tauri, Node or I/O imports.
- `src/application/` — use cases and repository/command interfaces.
- `src/infrastructure/` — Tauri IPC (or API) adapters. `src/bindings/` is generated: never edit by hand.
- `src-tauri/src/commands/` — one Rust command per business operation, one transaction each.
- `src-tauri/migrations/` — ordered SQL migrations; committed ones are immutable. See local `AGENTS.md`.
- `docs/parity/parity.csv` — behavior parity matrix: the definition of done.
- `legacy/`, `analysis-local/` — private, ignored, read-only evidence. Never execute legacy code.
- `skills/` — playbooks to follow; `scripts/` — inspector, parity gate, status, comparator, guard. Humans own `scripts/guard.py`, `.githooks/` and agent configuration: do not modify them.

## Non-negotiable rules

1. Verify before coding: read the real legacy source, schema, exports and library APIs. Never invent a column, table, control, rule or API member.
2. Every business rule cites evidence (`path:line`, export, screenshot) and a confidence: verified, inferred or unresolved.
3. Preserve legacy behavior unless an accepted ADR records the change. A screen that renders is not parity.
4. Data-structure changes are proposed to the human first. No silent destructive "fixes"; no editing committed migrations.
5. One user save = one command = one transaction. Validate input at the native/server boundary; parameterize all SQL.
6. Money, quantities and durations use the representation fixed in ADR-<n>; IDs above 2^53 cross IPC as strings. Check `docs/wlanguage-traps.md` when translating WLanguage.
7. No secrets in Git (licences, connection strings, tokens → environment variables or ignored local config).
8. Generated files (bindings, scaffolds) are regenerated, not edited.
9. Never claim a check passed unless you ran it. Record checks you could not run.
10. Do not re-open accepted decisions without new evidence. Read whole files before concluding.
11. A guard block (`scripts/guard.py`, pre-commit) is deliberate: report it in the handoff; never bypass it (`--no-verify`, renames, other paths).

## No guessing

When the evidence does not say what the legacy app does (an unresolved `U-nn` in the mapping note, encoded designer properties, an unknown event code, a binary query):

- Do not pick a behavior silently. Implement the safest reversible option, mark it in code with `// UNRESOLVED U-nn: <choice>`, and list it under "Decisions needed" in the handoff with the evidence you have.
- The parity row stays `implemented`, never `verified`, until a human decision (ADR) or new evidence resolves it. If only part of a row is unresolved, keep the whole row `implemented` or split the unresolved part into its own row.
- Do not write tests that pin an unresolved detail (sort order, selection after delete, Esc behavior, inferred colors). Compare as sets or assert only what is known.
- A user-facing text that does not exist in legacy (a new error message) is a choice: it needs approval before the row is `verified`.

Before marking a row `verified`, check all of these and report them in the handoff:

1. The cited test asserts the row's `target_behavior` and would fail if that behavior were removed (no tests that only check absence or always pass; a test that would still pass with the feature deleted is not evidence).
2. The test exercises the real path (not a placeholder or a mock standing in for the behavior under test).
3. No part of the behavior depends on an unresolved item or on your own choice.
4. If the target differs from legacy, `decision` names the ADR.
5. Re-read `docs/decisions/` at the end of the stage: ADRs added while you worked apply to your code too.

Identifiers you invent (test ids for controls that do not exist in legacy, helper names) are documented in the screen spec as non-legacy.

## Project-specific rules (filled in at framing, each backed by an ADR)

<Topology (local SQLite / shared server API), supported OSes, permissions model, report engine, grid/form libraries, update channel, external system access mode (read-only / limited writes / none)…>

## Commands

```sh
npm run verify          # typecheck + lint + unit + parity check: must pass before every commit
npm run test:e2e        # browser workflow tests with mocked IPC
npm run tauri -- build  # native package for this OS
python3 scripts/parity_check.py docs/parity/parity.csv   # parity progress and validity
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
