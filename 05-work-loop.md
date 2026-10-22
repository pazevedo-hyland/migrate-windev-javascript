# 05 — The work loop

1. Read project instructions, handoff, roadmap and relevant evidence.
2. Define one bounded change and its acceptance criteria, including the old behavior and intended new behavior.
3. Implement domain rules, persistence and UI needed for that slice.
4. Run relevant checks and compare against representative legacy examples.
5. Review the diff for broken behavior, convention drift and deliberate behavior changes.
6. Update parity status, decisions and handoff. Commit explicit files; push within the user's agreed workflow.

Useful checks include domain tests for money/time/stock rules, integration tests against a temporary database for transactions and migrations, browser workflow tests for keyboard/forms, and native smoke tests for IPC and OS integrations. Use the smallest meaningful set for the change; expand when failures or new risks justify it.

A typical application may define `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, and `npm run tauri -- build`. These commands are an application convention, not executable commands supplied by this playbook. Native checks require an actual scaffold and dependencies.

Do not mark a rule as migrated just because a screen exists. A repair-order save is complete when validation, material/time recording, failure handling, persistence after restart and report totals behave as agreed. Document test exclusions rather than treating missing native tests as passing.
