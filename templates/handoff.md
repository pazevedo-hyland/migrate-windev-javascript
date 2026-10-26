# Handoff — latest stage (<App>)

Entry point for the next session. Always holds the report of the **last** closed stage (overwritten each time). Full history: `git log`. Durable state: `AGENTS.md` + `docs/`.

## Stage — <name>

Branch/commit: <actual values>. Pushed: <yes/no>. Working tree clean: <yes/no>.
Parity: <rows moved>; built <implemented + verified>/<all rows>, verified <n>, excluded <n>; unanswered source/U items <n>. State the denominator and keep assumption-backed targets separate from confirmed legacy behavior.

### 1. Delivered
<Files, behavior, commands, migrations. Distinguish newly implemented behavior from links to existing coverage or adopted defaults. For waves, name the integration owner and frozen worker commits/manifests.>

### 2. Assumptions and differences
<Every assumption cited against real source/schema; nothing invented. Differences between legacy and target, and whether an ADR approved them.>

### 3. Checks actually executed
<Exact commands, results, OS and tested commit (or base + frozen working-tree manifest). e.g. `npm run verify` → pass; golden GS-003 → pass on Windows 11. Name the review policy used.>
Not run: <checks that could not run and why>.

### 4. Remaining work
1. <…>

### 5. Decisions needed from the human
<Open questions that affect scope or correctness, or "no blocking decision".>
