---
name: map-element
description: Map one legacy WINDEV element (window, report, query, procedure set, class or table group) into a mapping note, a screen or report spec and parity rows. Use during stage 0 mapping or when a new legacy source appears.
---

# Map one legacy element

Input: one unit name. Paths below are defaults; a stage prompt may give others. Never modify or run anything in `legacy/`, never copy credential values (locations only), do not write application code.

## Read

1. The unit's evidence pack — windows, reports and the project (`.wdp`): `python3 scripts/unit_evidence.py <unit> --out analysis-local/units/<unit>.json` (keep it: the reviewer diffs it later). For a **table group**: the tables' seed rows (`element` = each table), `docs/schema/schema-draft.md` and `docs/data/profile.md`, and validate with `--element <Table1>,<Table2>`. For a **query**: its SQL in the dossier extract (`query/<QRY>.json` in the `dossier` folder of `analysis-local/latest.json`) and its callers (`grep -rn <QRY> legacy/`). The window or report pack It holds the seed rows, code blocks with event meanings, encoded actions with every other slot sharing the same action ID, the parsed dossier fields, callers, calls out, gaps and runtime questions.
2. The unit's source in `legacy/` in full, and the callers' and callees' code one level out (call sites are in the pack).
3. `docs/wlanguage-traps.md`, `docs/mapping/event-codes.md` (generated, verified), `docs/evidence/encoded-actions.md` (answers, or proposals until answered), the images `docs/evidence/images/<unit>.*`.

Dossier fields: a field missing from the extract is "not extracted", never false (the extract's `index.json` → `coverage` says what was recognised). `tab_order` counts within each container. Open the extract's raw `lines` only for what parsed fields lack.

## Scope

- **Rows**: seed rows whose `element` is the unit. Keep every `SRC-*` ID.
- **Block**: a non-empty code block, one seed row.
- **Encoded action** (seed `kind` `encoded-action`): an event slot with no code whose predefined action (close, validate, print, open) WINDEV keeps encoded. It is behavior: describe what the evidence proves (caption, button type, the same action ID next to code elsewhere) and map it to the answer sheet's `Answer` for that ID (cite `runtime: A-xxxxxx`) or, while unanswered, to its `Proposed` answer (cite `proposed: A-xxxxxx`, and say "assumed" in `legacy_behavior`). Runtime questions work the same way (`proposed: Q-nn`). A proposal is never a reason to stop; a `U-` item is only for what has neither answer nor proposal. Blocks with `encoded_properties: true` may run an action besides their code. Template system buttons on every window may share one rule row.
- **Cross-window behavior** is where the risky rules are: shared file buffers and filters, globals, parameters, returned values. A window without an independent HFSQL context (`Indep. HFSQL ctx.` false) shares file positions and filters with the windows it opens and is opened from.

## Write `docs/mapping/<unit>.md`

1. **Purpose** — what the user does here.
2. **Entry and exit** — callers (`path:line`), parameters, modal or not, returned value and what callers do with it, what it opens, how it closes; the implicit contract (buffers, filters, globals read on entry or left behind).
3. **Events** — per block: control, raw event code and meaning, `path:line`, behavior in plain words, HFSQL calls (files, keys, filters, locks, transactions, error handling), calls out.
4. **Rules** — inputs, outputs, rounding/date/text semantics, exact message texts, a concrete example, traps involved. Quote literal values (a constant's value, a mask), and explain each WLanguage function once in plain words: the implementer will not read the legacy sources.
5. **Data** — files read and written, keys, current-record use, queries and parameters.
6. **Behavior checklist** — answer each, with evidence or a `U-` item: what is selected and shown on open, after a search or mode change, after add/modify/delete (also a record leaving the filter), on an empty result, on keyboard row moves; refresh when other windows or users change the data; two instances open; built-in control features (sort, per-column search, saved columns, Enter handling — dossier `flags`) and how they meet the code's filters; each dialog's title, default button, Esc result and labels per language; each write's failure path; numbers turned into text for SQL or display.
7. **Proposed changes** — what the target might do differently (a bug fix, a parameterized query), for an ADR. Never written as `target_behavior`.
8. **Unresolved** — `U-<UNIT>-nn` (same abbreviation as the rule rows, e.g. `U-WFC-01`). Every "not extracted", "unknown", "read from the image", "to be checked" or "probably" in your documents is one. Each says what would resolve it, whether it blocks implementation, and the interim default: the most likely legacy behavior, or "none: must be answered".

Controls go only in the screen spec.

## Write the spec

- **Window** → `docs/screens/<unit>.md` from `templates/window-spec.md`. Captions, masks, tab order, flags and button types come from the dossier; without one, write `unresolved (encoded)` per column instead of guessing.
- **Report** → `docs/reports/<unit>.md` from `templates/report-spec.md`: bands and geometry (inspector `layout`, millimetres), bound items, calculations, presets, page fit. Captions are often only in the image: say so. No caller in the pack is a finding: confirm with `grep -rnil "<unit>" legacy/` (a hit outside the report and the `.wdp` project file is a missed caller; a hit in a compiled file of the `<project>.cpl` folder names the window whose predefined action likely prints it — the evidence report already lists those).

## Write the parity rows

Columns of `templates/parity.template.csv`. During stage 0 (parallel mapping) in `docs/parity/<unit>.csv`, merged into `docs/parity/parity.csv` at its end; once `parity.csv` exists, directly in it. `element` is the unit's name, also on `RULE-*` rows (put the rule's title in `legacy_behavior`).

- `evidence`: `;`-separated, each `legacy/<path>:<line>` (seed evidence is relative to `legacy/`: prefix it), `dossier: <unit>/<field>` (e.g. `dossier: WIN_X/controls.BTN_Ok.flags`), `runtime: A-xxxxxx` (answered), `proposed: A-xxxxxx` or `proposed: Q-nn` (assumed until answered), or a committed file. Never a path inside `analysis-local/`.
- `confidence`: `verified` (read in code, schema, dossier or an answer), `inferred` (reasoning written in `legacy_behavior`), `assumed` (a `proposed:` answer or an ADR decided by default), `unresolved`. A row mixing them is split.
- `status`: `specified` with `target_behavior` = `Preserve legacy behavior` when understood; `unmapped` when a `U-` item blocks it, citing the item in `legacy_behavior`. A clear block with an unresolved outcome stays `specified`, the outcome in its own `RULE-*` row, `unmapped`.
- New rows: `RULE-<ABBR>-NNN`. A new event-code meaning goes in the mapping note, with its evidence.

Validate:

```sh
python3 scripts/parity_check.py docs/parity/<unit>.csv --seed docs/parity/parity-seed.csv --element <unit> \
  --check-files --note docs/mapping/<unit>.md --note docs/screens/<unit>.md
```

Once the rows are in `docs/parity/parity.csv`, check that file; for a report, `--note docs/reports/<unit>.md`.

Finish with: blocks and encoded actions covered / total, rows written, the riskiest rules, the unresolved list (blocking ones first), questions for the human.
