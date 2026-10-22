---
name: map-element
description: Map one legacy WINDEV element (window, report, query, procedure set, class or table group) into a mapping note and parity rows. Use during stage 0 mapping or when a new legacy source appears.
---

# Map one legacy element

Input: one unit name and its sources (`legacy/…`, `analysis-local/code/<file>.json`, screenshots, exported SQL). Read them in full. Do not modify them and do not write application code.

Write `docs/mapping/<unit>.md` with:

1. **Purpose** — what the user does here, in one paragraph, from evidence.
2. **Entry and exit** — who opens it (menu, other window, parameters), modal or not, returned value, what it opens.
3. **Controls** (windows) — name, type, caption, linked file item, input mask, required, max length, initial state, visibility/enabled rules, tab order, shortcut. Copy into `docs/screens/<WINDOW>.md` (`templates/window-spec.md`).
4. **Events** — one entry per code block: path (`WIN/CONTROL`), raw event code, `path:line` range, behavior in plain language, HFSQL calls (files, keys, filters, locks, transactions), calls to procedures/windows/reports.
5. **Rules** — each business rule with inputs, outputs, rounding/date/text semantics, failure messages (exact text), and a concrete example. Check every construct against `docs/wlanguage-traps.md`.
6. **Data** — files/tables read and written, keys, implicit current-record use, queries with parameters (note which conditions are skipped when a parameter is null or not given).
7. **Unresolved** — binary parts, missing exports, unknown codes, references not found. Never guess.
8. **Secrets** — location of hardcoded credentials, never the value.

Then propose parity rows (CSV, same columns as `templates/parity.template.csv`): keep every `SRC-*` ID from `analysis-local/parity-seed.csv` for this unit, fill `legacy_behavior` and `confidence`, and add `RULE-*` rows for rules spanning several blocks. Status stays `unmapped` or `specified`.

Finish with a short list: blocks covered / total for this unit, and the questions for the human.
