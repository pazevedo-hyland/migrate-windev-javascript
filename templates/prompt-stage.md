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
- Reuse: <adopted starter UI/reporting components, maintained adapter paths and packages/testing scenarios; read templates/starter/README.md in the playbook. Supply real UI drivers, independent persistence readers and this slice's explicit expected values. Generate structure with screen_layout.py → generate_screens.py; keep business handlers outside src/generated/. Extend shared components only for this slice's evidenced need>.
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

## Verification wave packet (implemented → verified)

After the implementation waves, run a separate wave whose only job is proof: one agent per family moves that family's `implemented` rows to `verified` with tests, and fixes the bugs the tests expose. Put this brief in `docs/runbooks/current-stage.md` and give each worker its family, worktree and port:

```text
You prove ONE family's parity rows with tests, in your own git worktree. Integration owner: the main session.
<OS notes: Python command, install step>. Browser flows: set <PORT_VARIABLE> to your port for every run.

Goal — for every row of your family's units (<family list file>) with status=implemented:
1. Read the row (legacy_behavior, target_behavior, evidence) and the code in implemented_in.
2. Write or extend a test that asserts exactly that behavior through the real path (the procedure/command with a real
   test database, or a click-through flow through the UI) and would FAIL if the behavior were removed. Group many rows per test.
3. If the code is wrong or missing, fix it in your family's files, then test it. That is the point: find bugs.
4. Mark the row verified only when the AGENTS.md "Before marking a row verified" checklist holds: test=<file>::<exact title>.
   Rows with confidence=assumed may be verified citing their proposal. Rows depending on an open U- item or
   confidence=unresolved: leave implemented (assert only the known part). New user-facing texts not in legacy: leave implemented.

You own: tests <family test globs>; fixes in <family source globs>; your units' docs/parity/<unit>.csv (status, test,
implemented_in columns only; keep IDs, never delete rows). In the test column, quote a cell whose titles contain a comma.
Never edit: docs/parity/parity.csv, other families' files, <shared runtime, schema/migrations, shared helpers>, scripts/,
skills/, legacy/, AGENTS.md. Shared fix needed → exact diff under "Shared changes requested".

Done: <typecheck commands> clean; your test files and <family>.flows green; commit on your branch (prefix <KEY>:), no push, no merge.
Return (≤25 lines): branch + last commit; rows verified (before → after) per unit; bugs found and fixed; rows left implemented
and why (U- item, new text, untestable); tests run (command → result); shared changes requested.
```

The coordinator merges the branches one by one, regenerates the aggregate matrix, runs `parity_check.py` (with `--check-files` in the main checkout) and the full `verify`, then reviews a sample of the new `verified` rows against the checklist.

Measured on a real migration (WINDEV 28, production management): 9 families in parallel took verified rows from 426 to 1,460, and the tests exposed 13 bugs the implementation wave had missed. Pitfalls seen:

- **Commas in CSV test titles.** A test title with a comma written unquoted into the `test` cell shifts every later column; one agent broke 9 rows this way. `parity_check.py` caught them as an invalid `status` — run it in each worktree before returning, and write the CSVs with a CSV library, not by string concatenation.
- **Worktrees lack `legacy/`** (it is ignored by Git), so `parity_check.py --check-files` cannot resolve legacy citations there. Workers run it without `--check-files`; the coordinator runs the full check after merging.
- Give each worker its own port (and database/profile) for browser flows, and let only one run the full suite at a time.

**Second sweep.** Run the same packet once more over what the first left (`implemented` and `specified`), adding to the brief:

- A harness per kind of behaviour, so "hard to test" stops being a reason: procedures with a real test database; screens by
  click-through flows; reports and labels by asserting the rendered report model (rows, groups, totals, empty-data branch),
  not a printer; files and folders in real temporary folders (or the native command's own test); timers with fake timers or
  the browser test clock; failure branches by fault injection (a dev-only driver, or routing a patched procedure in the flow).
- "Questions for the owner": every row left because of an open question gets one plain-language entry in
  `docs/mapping/_questions-<KEY>.md` (`- <rows> (<unit>): <question> — what we do now: <current choice>`), so the remaining
  rows become one list a person who uses the old program can answer (publish it as a page with one-click answers if useful).
- Leave-reasons counted: open question, new text, needs hardware/person, other. Requests outside the worker's columns
  (exclusions under the scope ADR, a `decision` to set) come back as "shared changes requested".

Measured (same migration): 165 more rows verified (1,460 → 1,625, strict 73.7 → 81.7 %), 19 more bugs, 163 owner
questions. Coordinator lessons: check every "assumed" row's proposal really answers it (an answer-sheet ID reused for a
different question had "verified" four message-box rows); a shared-control bug can surface only when a worker's change adds
a re-render (a combo lost "no selection"), so run the full suite after merging even when every branch was green.

## Reusable instructions (pick according to accepted choices)

- **WINDEV-like UI replica**: "Reproduce `docs/screens/<WINDOW>.md` and the dossier image: same fields, order, labels, tab order, masks, shortcuts and default button. Generate the layout with scripts/screen_layout.py <WINDOW> and read captions and positions from it; export the skin with scripts/skin_assets.py. Use the legacy control name as `data-testid`. Score it with scripts/visual_compare.py --record and attach the side-by-side image to the handoff. Do not redesign; propose improvements separately."
- **Modal flows**: "Legacy `Open()`/`YesNo()`/`Info()` block until closed. Implement as awaited promises and keep the code after them in the same order."
- **Atomic business save**: "The UI builds one command DTO; one Rust command validates, re-checks invariants (stock, uniqueness, version) and writes in one transaction; return the committed state."
- **Golden scenario**: "Replay `docs/golden/<GS-id>.md` through the application use cases and compare with `scripts/compare_exports.py`."
