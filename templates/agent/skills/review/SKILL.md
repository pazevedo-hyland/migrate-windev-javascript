---
name: review
description: Review a migration stage (code, SQL, tests, docs) against legacy evidence and accepted decisions, reporting only real findings in four categories. Use after each stage the implementer delivers.
---

# Stage review

Read the changed files in full, the stage prompt, the accepted ADRs and the legacy evidence cited by the parity rows the stage moved. Report **only** real findings:

1. **Blocking** — build/test failure, data loss, wrong totals or rounding, broken transaction, violated permission, missing acceptance criterion, hard rule from `AGENTS.md` violated.
2. **Parity gap** — a legacy behavior missing or changed without an ADR; a row marked `verified` without an executed test; an `inferred` rule implemented as fact; a WLanguage trap mistranslated (`docs/wlanguage-traps.md`).
3. **Naming/convention** — drift from `AGENTS.md`, `docs/architecture.md`, local `AGENTS.md`; `data-testid` not matching the legacy control name.
4. **Business/cosmetic** — assumptions to validate, simplifications, readability, layout differences from screenshots.

No unrequested rewrites. Propose; the human decides. Do not reopen accepted decisions unless new evidence requires it: name that evidence.

## Systematic checks

- Real schema, columns and library APIs were used — nothing invented.
- Runtime input validation at the native/server boundary; SQL parameterized; one save = one transaction.
- No destructive schema change or edited committed migration; no secret committed.
- Money/quantity/date semantics and IDs above 2^53 follow the ADRs.
- Keyboard order, focus, masks and messages match `docs/screens/<WINDOW>.md`.
- Every row moved to `verified` cites a test that asserts its behavior, and no part of it is the implementer's own choice for an unresolved item (sort order, Esc, selection after delete…); otherwise it must be `implemented` with the choice in the handoff.
- Checks in the handoff were actually executed (commands and output); unavailable native checks are listed. Browser mocks are not proof of packaged native behavior.
- `parity.csv`, `ROADMAP.md` and the handoff reflect what was really delivered.

## Output

A short list grouped by the four categories. Each item: where (file:line or parity ID), what is wrong, the concrete fix.
