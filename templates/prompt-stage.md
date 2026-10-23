# Implementation stage prompt

Copy, fill the core, keep the **preamble** and **closing** unchanged.

```text
First read docs/runbooks/handoff.md, AGENTS.md, ROADMAP.md and the ADRs for this slice. Follow the non-negotiable rules. Start with git pull.

Stage "<name>" (roadmap #<n>):
- Parity rows: <IDs>. Evidence: <legacy paths:lines, exported SQL, screenshots, docs/screens/<WINDOW>.md, golden scenarios>.
- Expected behavior: <normal case, boundary case, failure case with exact legacy message>.
- Intentional changes: <none, or ADR references>.
- Deliverables: <domain rules + tests named with parity IDs, Rust command + transaction, UI, golden scenario, migration if any>.
- Constraints: inspect the real schema and library APIs before coding; port every construct with its pattern in docs/porting.md (and its trap in docs/wlanguage-traps.md); <architecture constraints from ADRs>.
- Out of scope: <explicit limits — "do not build X yet">.

Done means: npm run verify passes, the golden scenarios for these rows pass — also clicked through the UI in ui-check/<slice>.flows.spec.ts (templates/ui-check/flows.example.spec.ts) —, each row you mark verified names the test that proves it, and every window and message box the slice opens is built from its generated layout with the skin kit, configured in ui-check.config.json and passes npm run ui:check (controls, captions, visual score recorded and not lower than before) — attach the side-by-side images to the handoff. Unknown legacy behavior follows AGENTS.md "No guessing": a proposal makes the row `assumed` (it may be verified); a choice of your own with no proposal keeps it implemented, listed under "Decisions needed". List checks you could not run (e.g. native printing on Windows).

Before closing: two independent reviews of the slice with skills/review (separate sub-agents or sessions; one on behavior against the legacy evidence, one on conventions and docs/porting.md); one fixer applies their findings.

At the end: commit explicit files with a clear message, push, update docs/parity/parity.csv, ROADMAP.md and docs/runbooks/handoff.md, regenerate the progress page (python3 scripts/progress_dashboard.py --title "<App>") and commit it with them (Delivered / Assumptions and differences / Checks actually executed / Remaining work / Decisions needed).
```

## Writing reminders

- Always keep the preamble (handoff + instructions) and the closing (verify, commit, handoff).
- Give precise goals and constraints, not the detailed "how": the implementer chooses the implementation, the human arbitrates in review.
- Restate any decision made since the last session, or point to its ADR.
- One workflow per stage. If a stage needs more than one session, split it.

## Reusable instructions (pick according to accepted choices)

- **WINDEV-like UI replica**: "Reproduce `docs/screens/<WINDOW>.md` and the dossier image: same fields, order, labels, tab order, masks, shortcuts and default button. Generate the layout with scripts/screen_layout.py <WINDOW> and read captions and positions from it; export the skin with scripts/skin_assets.py. Use the legacy control name as `data-testid`. Score it with scripts/visual_compare.py --record and attach the side-by-side image to the handoff. Do not redesign; propose improvements separately."
- **Modal flows**: "Legacy `Open()`/`YesNo()`/`Info()` block until closed. Implement as awaited promises and keep the code after them in the same order."
- **Atomic business save**: "The UI builds one command DTO; one Rust command validates, re-checks invariants (stock, uniqueness, version) and writes in one transaction; return the committed state."
- **Golden scenario**: "Replay `docs/golden/<GS-id>.md` through the application use cases and compare with `scripts/compare_exports.py`."
