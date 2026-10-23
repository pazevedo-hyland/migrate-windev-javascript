---
name: review-mapping
description: Cross-review one unit's mapping (note, screen or report spec, parity CSV) against the legacy evidence before any code is written. Use in stage 0 after map-element, ideally with a different model or session than the mapper.
---

# Review one unit's mapping

Input: one unit name. Read its mapping note, its screen or report spec and its parity CSV, then the evidence they cite. Read-only: report findings, do not edit. Paths are the defaults of `map-element`; a stage prompt may give others.

## Checks, in this order

1. **Mechanical first.** `python3 scripts/parity_check.py docs/parity/<unit>.csv --seed <inspect dir>/parity-seed.csv --element <unit>`. Missing seed rows, duplicate or stale IDs, evidence in no recognised form, `unmapped` rows without their `U-` item: list them as they come.
2. **Newer evidence.** Compare the extract versions the mapping cites with the current ones (inspector output, dossier extract, evidence report, event legend). List what is new for this unit — encoded actions and their action IDs, flags, structured fields — and which statements or unresolved items it changes.
3. **Every slot has a row.** Each code block and each encoded action of the unit (`blocks` and `encoded_slots` in the inspector output) is covered. Empty, disabled slots without encoded properties need no row.
4. **Every `verified` claim.** Open the cited line: it states the claim, and nothing the claim depends on is still unresolved. A row mixing verified parts (code, structure) with inferred ones (an image reading, a button-type default) is split or downgraded.
5. **Every unresolved item.** Before it stays unresolved, look in the three places that often settle or narrow it: the encoded-action group (same ID elsewhere, with code or captions that explain it), the dossier flags and structured fields, and the same pattern in other windows' code. Narrowed is reported as `inferred` with that evidence, not as resolved.
6. **What an implementer cannot do without.** The implicit contract (shared buffers, globals, returned value and what callers read afterwards), quoted literal values, exact message texts with placeholders resolved, data edge cases. A gap here is a finding even when no evidence exists: it becomes a `U-` item.

## Labels

- `verified`: read directly in code, schema, dossier field or an answered runtime question.
- `inferred`: reasoned from evidence; the reasoning is written.
- `unresolved`: no evidence settles it; a `U-<UNIT>-nn` item names what would.

## Output

Per category, each finding with where (file:line or parity ID), the evidence, and the concrete fix:

1. **Mechanical** (from the validator)
2. **Missing rows or events**
3. **Misread rules**
4. **Wrong confidence labels**
5. **Unresolved items the evidence settles or narrows**
6. **Implementer blockers** (silent gaps)

End with the count per category. No rewrites of the mapping; the mapper or the human applies the fixes.
