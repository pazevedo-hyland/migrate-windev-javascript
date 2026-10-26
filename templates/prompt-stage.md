# Implementation stage prompt

Copy, fill the core, keep the **preamble** and **closing** unchanged.

```text
First read docs/runbooks/handoff.md, AGENTS.md, ROADMAP.md and the ADRs for this slice. Follow the non-negotiable rules. Synchronize only as project policy allows.

Stage "<name>" (roadmap #<n>):
- Parity rows: <IDs>. Evidence: <legacy paths:lines, exported SQL, screenshots, docs/screens/<WINDOW>.md, golden scenarios>.
- Expected behavior: <normal case, boundary case, failure case with exact legacy message>.
- Functional acceptance (if adopted): <docs/functional-acceptance.json required case IDs/units/requirements, exact check file/title and executed run/OS/commit evidence; retain pending cases and unassessed screens/reports>.
- Intentional changes: <none, or ADR references>.
- Deliverables: <domain rules + tests named with parity IDs, Rust command + transaction, UI, golden scenario, migration if any>.
- Constraints: inspect the real schema and library APIs before coding; port every construct with its pattern in docs/porting.md (and its trap in docs/wlanguage-traps.md); <architecture constraints from ADRs>.
- Reuse: <adopted starter UI/reporting components and maintained adapter paths; read templates/starter/README.md in the playbook. Generate structure with screen_layout.py → generate_screens.py; keep business handlers outside src/generated/. Extend shared components only for this slice's evidenced need>.
- Out of scope: <explicit limits — "do not build X yet">.

Done means: npm run verify passes, the golden scenarios for these rows pass — also clicked through the UI in ui-check/<slice>.flows.spec.ts (templates/ui-check/flows.example.spec.ts) —, each row you mark verified names the test that proves it, and every window and message box the slice opens is built from its generated layout with the skin kit, configured in ui-check.config.json and passes npm run ui:check (controls, captions, visual score recorded and not lower than before) — attach the side-by-side images to the handoff. Unknown legacy behavior follows AGENTS.md "No guessing": a proposal makes the row `assumed` (it may be verified); a choice of your own with no proposal keeps it implemented, listed under "Decisions needed". List checks you could not run (e.g. native printing on Windows).

If functional acceptance is adopted, update docs/functional-acceptance.json, run python3 scripts/functional_acceptance.py --check and report verified/required cases separately from strict parity/source confidence and platform acceptance. App/test changes invalidate affected run witnesses; ordinary report/status documentation changes do not. Count complete declared scope, not tests passed or built links. Source-derived expectations can prove readable rules; tested target choices do not answer encoded legacy questions or prove unexecuted native behavior.

Before closing: an independent review of the slice with skills/review (a separate sub-agent or session); a slice touching money, stock or totals, the data import, deleting or overwriting data, or a multi-window workflow gets a second, independent one. One fixer applies their findings. An agent that cannot start a separate session reviews in a separate pass after clearing its context, reading only the diff, this prompt, the ADRs and the evidence, and says so in the handoff.

For a parallel wave, apply closing reviews to the integrated delivery, not separately to every worker. An accepted project ADR may allow coordinator self-review for initial implementations; disclose it and keep those rows implemented until the acceptance review/checks. Workers return changes and claims; the coordinator owns the closing below.

At the end: update docs/parity/parity.csv, ROADMAP.md and docs/runbooks/handoff.md (Delivered / Assumptions and differences / Checks actually executed / Remaining work / Decisions needed), regenerate the progress page (python3 scripts/progress_dashboard.py --title "<App>"), then commit all of it as explicit files with a clear message; push only if the project allows it.
```

## Writing reminders

- Always keep the preamble (handoff + instructions) and the closing (verify, commit, handoff).
- Give precise goals and constraints, not the detailed "how": the implementer chooses the implementation, the human arbitrates in review.
- Restate any decision made since the last session, or point to its ADR.
- Bound work by a complete workflow or related workflow family. Parallelize independent families after shared prerequisites; keep an integration owner.

## Parallel wave packet

Add these fields to the core prompt for each implementation worker:

- Role/ownership: <family, exact parity IDs, base commit, owned files; shared files and tracking excluded>.
- Context: <source/spec/mapping references, unresolved questions and accepted target defaults; API/schema/UI contracts and dependency owners>.
- Runtime/checks: <isolated worktree, database/profile, ports/build namespace, focused normal/boundary/failure checks>.
- Return: <frozen commit or file hashes; one claim per ID: target behavior, file::symbol, test actually run, decision, known gaps>. Identify existing coverage separately from newly implemented paths; preserve source confidence and U questions.

The coordinator handles shared prerequisites before dependent workers consume them, then integration, combined verification and tracking. No worker edits aggregate parity or creates a permanent process runbook.

## Reusable instructions (pick according to accepted choices)

- **WINDEV-like UI replica**: "Reproduce `docs/screens/<WINDOW>.md` and the dossier image: same fields, order, labels, tab order, masks, shortcuts and default button. Generate the layout with scripts/screen_layout.py <WINDOW> and read captions and positions from it; export the skin with scripts/skin_assets.py. Use the legacy control name as `data-testid`. Score it with scripts/visual_compare.py --record and attach the side-by-side image to the handoff. Do not redesign; propose improvements separately."
- **Modal flows**: "Legacy `Open()`/`YesNo()`/`Info()` block until closed. Implement as awaited promises and keep the code after them in the same order."
- **Atomic business save**: "The UI builds one command DTO; one Rust command validates, re-checks invariants (stock, uniqueness, version) and writes in one transaction; return the committed state."
- **Golden scenario**: "Replay `docs/golden/<GS-id>.md` through the application use cases and compare with `scripts/compare_exports.py`."
