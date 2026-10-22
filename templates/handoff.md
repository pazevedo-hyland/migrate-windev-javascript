# Handoff — latest stage (<App>)

Entry point for the next session. Always holds the report of the **last** closed stage (overwritten each time). Full history: `git log`. Durable state: `AGENTS.md` + `docs/`.

## Stage — <name>

Branch/commit: <actual values>. Pushed: <yes/no>. Working tree clean: <yes/no>.
Parity: <rows moved, e.g. RULE-010..014 specified → verified>; matrix <n>% complete.

### 1. Delivered
<Files, behavior, commands, migrations.>

### 2. Assumptions and differences
<Every assumption cited against real source/schema; nothing invented. Differences between legacy and target, and whether an ADR approved them.>

### 3. Checks actually executed
<Exact commands, results, OS. e.g. `npm run verify` → pass; golden GS-003 → pass on Windows 11.>
Not run: <checks that could not run and why>.

### 4. Remaining work
1. <…>

### 5. Decisions needed from the human
<Open questions that affect scope or correctness, or "no blocking decision".>
