---
name: map-element
description: Map one legacy WINDEV element (window, report, query, procedure set, class or table group) into a mapping note, a screen spec and parity rows. Use during stage 0 mapping or when a new legacy source appears.
---

# Map one legacy element

Input: one unit name. Paths are relative to the repository root; the locations named here are the defaults — when your stage prompt gives other paths, use those. Read in full: the unit's dossier extract if present (`<dossier dir>/<kind>/<unit>.json`: captions, tab order, masks, query SQL — cite it as `dossier: <unit>/<control>`), the unit's source in `legacy/`, its extracted blocks in the inspector output (`<inspect dir>/code/<path under legacy/>.json`, e.g. `code/code/WIN_X.wdw.json`), `docs/wlanguage-traps.md`, `docs/mapping/event-codes.md` and `docs/mapping/event-codes-inferred.md`. Never modify legacy files, never run anything from them, never copy credential values (locations only). Do not write application code.

Start from the unit's evidence pack: `python3 scripts/unit_evidence.py <unit> --out analysis-local/units/<unit>.json` — its seed rows, blocks with event meanings, encoded actions with every other slot holding the same action ID (often what settles one), parsed dossier fields, callers, calls out, gaps and runtime questions. Keep the pack: the reviewer diffs it against a newer one.

Read the parsed fields of the dossier extract first (`title`, `controls.<name>.caption`, `tab_order`, `input_mask`, `input_type`, `state`, `flags` — checkbox properties such as `Indep. HFSQL ctx.`, `Required input`, `Multiline` — for analysis items `keys` (`Unique Key`, `Key with Duplicates`), for reports `margins_mm`, per control `flags` (`Divisible`, `Auto.Resiz`, `Border`), `calculation` and `preset`, and for queries `sql`). `tab_order` numbers count within their parent container (a supercontrol has its own sequence). A field missing from the extract is "not extracted", never false: check `index.json` → `coverage` and its warnings; open `lines` only for what the parsed fields do not cover.

## Scope

- **Rows of the unit**: seed rows whose `element` column equals the unit name — not every row that mentions it. Keep every `SRC-*` ID.
- **A block** is a non-empty code block (one seed row). Empty event slots are not rows; mention them only when meaningful.
- **An encoded action** is an event slot with no code but encoded `internal_properties` (seed `kind` = `encoded-action`, listed in the inspector output's `encoded_slots`): WINDEV keeps a button's predefined action there (close, validate, print a report, open a window). It is behavior: keep its row, describe what the evidence proves (button type from the dossier, caption, what the window offers otherwise), and leave the action itself `unmapped` with a `U-<UNIT>-nn` naming its action ID (`A-xxxxxx`, in the seed `context`) — unless `docs/evidence/encoded-actions.md` already answers that ID: then the row is `specified`, `inferred` or `verified` as the answer says, with evidence `runtime: A-xxxxxx`. Blocks with `encoded_properties: true` may run such an action besides their code. Template system buttons repeated on every window (`BTN_SYST_FERMER`, `BTN_SYST_MINIMIZE`…) may all cite one shared rule row.
- **Follow one level of callers and callees**: take the callers from `docs/evidence-report.json` (`callers.<unit>`: `<source file>:<line> (<function> in <caller>)`, relative to the inspected folder) instead of searching, and read those call sites, plus the windows, procedures and queries the unit opens or calls. Cross-window behavior (shared file buffers and filters, globals, parameters, returned values) is where the risky rules are: a window without an independent HFSQL context (`Indep. HFSQL ctx.` false in the dossier `flags`) shares file positions and filters with the windows it opens and is opened from — read their file loops and searches for the effect.

## Write `docs/mapping/<unit>.md`

1. **Purpose** — what the user does here, from evidence.
2. **Entry and exit** — callers (`path:line`), parameters, modal or not, returned value, what it opens, how it closes, and the **implicit contract**: shared file buffers, filters and globals the window reads on entry or leaves for its callers (read the callers' code after the call returns).
3. **Events** — one entry per block: control path, raw event code and its legend meaning (or "unknown"), `path:line`, behavior in plain language, HFSQL calls (files, keys, filters, locks, transactions, error handlers), calls out.
4. **Rules** — each business rule: inputs, outputs, rounding/date/text semantics, exact message texts, one concrete example, and the traps from `docs/wlanguage-traps.md` it involves. Quote literal values (a global constant's value, a mask), not only where they are defined: the implementer will not have the legacy sources. Explain each WLanguage function you cite in plain words once (`HReset(Clientes)`: clears the file's current record buffer).
5. **Data** — files/tables read and written, keys, implicit current-record use, queries and their parameters (binary queries: intent inferred from name, call sites and schema — marked inferred).
6. **Before you list what is unresolved**, answer for this unit: what is selected and shown on open, after a search, after a mode change, after add or delete (including a record that no longer matches the active filter), when the result is empty, and when the user moves rows with the keyboard; whether it refreshes when other windows or users change its data, and what happens with two instances open at once; what built-in control features are on (table sort, per-column search, saved column configuration, Enter handling: dossier `flags`) and how they meet the code's filters; every dialog's title, default button, Esc result and labels in each language; every write's failure path (query error, lock, duplicate); numbers turned into text for SQL or display (masks, separators); and what callers do with each returned value. Each answer is evidence or a `U-` item.
7. **Proposed changes** — anything you think the target should do differently (a bug to fix, a parameterized query): listed here for an ADR, never written as the row's `target_behavior`, which stays `Preserve legacy behavior` until the ADR exists.
8. **Unresolved** — numbered `U-<UNIT>-01…` with the same abbreviation as the unit's rule rows (`U-WFC-01`), so IDs stay unique when notes are merged: binary parts, encoded designer properties, unknown codes, missing references, and every point you would otherwise mark "check", "untested" or "probably". For each: the evidence that would resolve it (designer export, query SQL export, running the legacy app), whether it blocks implementation, and the interim default an implementer may use meanwhile — the most likely **legacy** behavior, never an improvement (that goes to Proposed changes), or "none: must be answered". Every "not extracted", "unknown" or "read from the image" in your documents is one of these items.

Controls go **only** in the screen spec, not in the note.

## Write `docs/screens/<unit>.md` (windows only)

Follow `templates/window-spec.md`. Captions, masks, tab order and button types come from the dossier extract when it exists; the text sources keep them in encrypted `internal_properties`. Without a dossier, fill what readable text and code prove, otherwise write `unresolved (encoded)` once per column rather than guessing, and list the evidence needed.

## Reports

For a report (`.wde`), write `docs/reports/<unit>.md` from `templates/report-spec.md` instead of a screen spec: page format and the printable-width check, data source and sort, bands, columns with bound items (`controls.<name>.item` in the dossier extract, geometry in millimetres), calculations and presets. Report captions are usually visible only in the dossier image: read them there and say so. A report with no caller in `callers` is a finding (how is it printed today?), not an omission of yours: confirm it with a case-insensitive search of the sources for the report name (e.g. `grep -rni "RPT_List_Clientes" legacy/code`; a hit outside the report itself and the project file `.wdp`, which lists every element, is a caller the index missed — report it) before writing "no caller found".

## Write `docs/parity/<unit>.csv`

Exact columns of `templates/parity.template.csv`.

- `evidence`: `;`-separated items, each a repository-relative `path:line` (seed evidence is relative to the inspected folder: prefix it, e.g. `legacy/code/`), a JSON file with the field (`<dossier dir>/windev-window/WIN_X.json (controls.BTN_Ok.flags)`), or a screenshot/export file. `parity_check.py` rejects anything vaguer.
- `confidence`: `verified` (read directly in code/schema), `inferred` (reasoned; say how in `legacy_behavior`), `unresolved`.
- `status`: `specified` with `target_behavior` = `Preserve legacy behavior` when the legacy behavior is understood; `unmapped` when an unresolved item blocks it — cite its `U-<UNIT>-nn` in `legacy_behavior` (the validator requires it). Changes to legacy behavior are decided later by ADR, not here.
- A block whose code is clear but whose outcome depends on an unresolved item (e.g. the window may or may not close afterwards): keep the block's `SRC-*` row `specified` for what the code does, and put the unresolved part in its own `RULE-*` row, `unmapped`, citing the `U-<UNIT>-nn`.
- New rule rows: `RULE-<UNIT-ABBREVIATION>-NNN` (e.g. `RULE-ORF-001`), for rules spanning several blocks or windows.
- New event-code meanings you infer: add them to `docs/mapping/event-codes-inferred.md` with the evidence (`docs/mapping/event-codes.md` is generated by `event_legend.py` and would overwrite them).

Validate before finishing:

```sh
python3 scripts/parity_check.py docs/parity/<unit>.csv --seed <inspect dir>/parity-seed.csv --element <unit> --check-files --note docs/mapping/<unit>.md --note docs/screens/<unit>.md
```

Finish with: blocks covered / total, rows written, the top risky rules, the unresolved list, and questions for the human.
