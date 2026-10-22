# Implementation stage prompt

Read AGENTS.md, docs/runbooks/handoff.md, ROADMAP.md and the accepted ADRs.

Stage: <one bounded workflow>.
Evidence: <legacy paths/lines, exported SQL, screenshot and parity rows>.
Expected behavior: <normal case, boundary case, failure case>.
Intentional changes: <none or approved differences>.
Dependencies: <completed prerequisites>.
Deliverables: <domain rules, native/API transactions, UI and relevant tests>.
Out of scope: <explicit limits>.

Implement the accepted architecture. Verify actual APIs and schema, preserve exact numeric semantics, validate commands and parameterize SQL. Run the meaningful checks for this change and state which native checks could not run. Review behavior and the diff. Update parity, roadmap and handoff with delivered work, assumptions, actual checks and next steps. Commit/push within the agreed repository workflow.
