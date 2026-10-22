---
name: map-element
description: Map one legacy WINDEV element (window, report, query, procedure set, class or table group) into a mapping note, a screen spec and parity rows. Use during stage 0 mapping or when a new legacy source appears.
---

# Map one legacy element

Input: one unit name. Paths are relative to the repository root. Read in full: the unit's source in `legacy/`, its extracted blocks in the inspector output (`<inspect dir>/code/…/<file>.json`), `docs/wlanguage-traps.md` and `docs/mapping/event-codes.md`. Never modify legacy files, never run anything from them, never copy credential values (locations only). Do not write application code.

## Scope

- **Rows of the unit**: seed rows whose `element` column equals the unit name — not every row that mentions it. Keep every `SRC-*` ID.
- **A block** is a non-empty code block (one seed row). Empty event slots are not rows; mention them only when meaningful (e.g. a Print button with no code).
- **Follow one level of callers and callees**: search all legacy code for the unit name (`Open(…)`, `OpenChild(…)`, `ExecuteProcess(…)`, `iPrintReport(…)`) and read those call sites, plus the windows, procedures and queries the unit opens or calls. Cross-window behavior (shared file buffers and filters, globals, parameters, returned values) is where the risky rules are.

## Write `docs/mapping/<unit>.md`

1. **Purpose** — what the user does here, from evidence.
2. **Entry and exit** — callers (`path:line`), parameters, modal or not, returned value, what it opens, how it closes.
3. **Events** — one entry per block: control path, raw event code and its legend meaning (or "unknown"), `path:line`, behavior in plain language, HFSQL calls (files, keys, filters, locks, transactions, error handlers), calls out.
4. **Rules** — each business rule: inputs, outputs, rounding/date/text semantics, exact message texts, one concrete example, and the traps from `docs/wlanguage-traps.md` it involves.
5. **Data** — files/tables read and written, keys, implicit current-record use, queries and their parameters (binary queries: intent inferred from name, call sites and schema — marked inferred).
6. **Unresolved** — numbered `U-01…`: binary parts, encoded designer properties, unknown codes, missing references. For each, the evidence that would resolve it (screenshot, designer export, query SQL export, running the legacy app).

Controls go **only** in the screen spec, not in the note.

## Write `docs/screens/<unit>.md` (windows only)

Follow `templates/window-spec.md`. Captions, masks, tab order, linked items and shortcuts are usually in encoded `internal_properties`: fill what readable text and code prove; otherwise write `unresolved (encoded)` once per column rather than guessing, and list the screenshots needed.

## Write `docs/parity/<unit>.csv`

Exact columns of `templates/parity.template.csv`.

- `evidence`: repository-relative `path:line` (seed evidence is relative to the inspected folder: prefix it, e.g. `legacy/code/`).
- `confidence`: `verified` (read directly in code/schema), `inferred` (reasoned; say how in `legacy_behavior`), `unresolved`.
- `status`: `specified` with `target_behavior` = `Preserve legacy behavior` when the legacy behavior is understood; `unmapped` when an unresolved item blocks it (cite `U-nn` in `legacy_behavior`). Changes to legacy behavior are decided later by ADR, not here.
- New rule rows: `RULE-<UNIT-ABBREVIATION>-NNN` (e.g. `RULE-ORF-001`), for rules spanning several blocks or windows.
- New event-code meanings you infer: add them to `docs/mapping/event-codes.md` with the evidence, labelled inferred.

Validate before finishing:

```sh
python3 scripts/parity_check.py docs/parity/<unit>.csv --seed <inspect dir>/parity-seed.csv --element <unit>
```

Finish with: blocks covered / total, rows written, the top risky rules, the unresolved list, and questions for the human.
