---
name: review
description: Review a migration stage (code, SQL, tests, docs) against legacy evidence and accepted decisions, reporting only real findings in four categories. Use after each stage the implementer delivers.
---

# Stage review

Run in a fresh context (a new session or sub-agent — Claude, Codex or another), never the one that wrote the code (if you cannot start one, clear your context and read only what follows; say so in the handoff). Read the diff and the changed files in full, the stage prompt, the accepted ADRs, `docs/porting.md` and the legacy evidence cited by the parity rows the stage moved — not the implementer's handoff or reasoning, which argue for the code. Assume the code is wrong and find how. Report **only** real findings:

1. **Blocking** — build/test failure, data loss, wrong totals or rounding, broken transaction, violated permission, missing acceptance criterion, hard rule from `AGENTS.md` violated.
2. **Parity gap** — a legacy behavior missing or changed without an ADR; a row marked `verified` without an executed test; an `inferred` rule implemented as fact; a WLanguage trap mistranslated (`docs/wlanguage-traps.md`).
3. **Naming/convention** — drift from `AGENTS.md`, `docs/architecture.md`, local `AGENTS.md`; `data-testid` not matching the legacy control name.
4. **Business/cosmetic** — assumptions to validate, simplifications, readability, layout differences from screenshots.

No unrequested rewrites. Propose; the human decides. A finding that already came up in an earlier slice is also a process finding: name the rule to add to `docs/porting.md` or `AGENTS.md` so later slices do not repeat it. Do not reopen accepted decisions unless new evidence requires it: name that evidence.

## Systematic checks

- Real schema, columns and library APIs were used — nothing invented.
- Runtime input validation at the native/server boundary; SQL parameterized; one save = one transaction.
- No destructive schema change or edited committed migration; no secret committed.
- Money/quantity/date semantics and IDs above 2^53 follow the ADRs.
- Keyboard order, focus, masks and messages match `docs/screens/<WINDOW>.md`.
- Every window and dialog the slice opens (modal forms and message boxes included) is configured in `ui-check.config.json`, scored in `docs/evidence/visual/`, and reads captions and positions from its generated layout — a caption or coordinate typed by hand is a finding.
- Every row moved to `verified` passes the five checks in `AGENTS.md` ("No guessing"); otherwise it must be `implemented` with the choice in the handoff.
- Checks in the handoff were actually executed (commands and output); unavailable native checks are listed. Browser mocks are not proof of packaged native behavior.
- `parity.csv`, `ROADMAP.md` and the handoff reflect what was really delivered.
- Every WLanguage construct is ported with its pattern in `docs/porting.md`; a new pattern was added there, not invented in place.
- **Reject**: stubs, placeholders, `todo!()`/`unimplemented!()` or a mock standing in for behavior a `verified` row claims; tests skipped, deleted or weakened to pass; a workaround that needs a paragraph-long comment to justify it — the code is wrong, fix the code.

## Output

A short list grouped by the four categories. Each item: where (file:line or parity ID), what is wrong, the concrete fix.
