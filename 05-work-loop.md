# 05 — The work loop

## The roadmap

The planner keeps an **ordered list of slices** in `ROADMAP.md` ([template](templates/ROADMAP.template.md)): number, phase, slice, parity rows, owner (implementer / planner / sub-agent / human), prompt, expected deliverable, **dependencies**, **status** (To do / In progress / Blocked / Done).

- **Dependencies** dictate the order: never skip a foundation (schema, import, verify pipeline).
- **Status** is updated when each slice closes.
- A slice is one **complete workflow** (UI + domain + command + persistence + tests), not a layer.

## The cycle of a stage

Prompt → implement → verify and review/fix → update tracking and handoff → commit → synchronize if authorized. A parallel wave has the same integration boundary as a single slice.

**1. The prompt** ([template](templates/prompt-stage.md)) **always** starts with:

> "First read `docs/runbooks/handoff.md`, `AGENTS.md`, `ROADMAP.md` and the ADRs for this slice. Follow the non-negotiable rules. Synchronize only as project policy allows."

…and **always** ends with:

> "Run `npm run verify` and the slice's golden scenarios → review/fix → update `parity.csv`, `ROADMAP.md`, progress and `docs/runbooks/handoff.md` → commit explicit files; push only if authorized."

Each prompt is **bounded** ("do not build X yet") and lists its parity rows, evidence, normal/boundary/failure cases, and intentional changes.

**2. The implementer executes** in the repository and **tests for real** (not just "it compiles"). Workers return their bounded changes to the integration owner.

**3. The integration owner** assembles the delivery on the agreed base and verifies the combined result. Synchronize other clones only under the project's Git policy.

**4. The planner reviews** with the [review skill](templates/agent/skills/review/SKILL.md) and reports **only** real findings:

1. **Blocking error**;
2. **Parity gap** (behavior missing or changed without ADR, `verified` without executed test, WLanguage trap mistranslated);
3. **Naming/convention drift**;
4. **Business/cosmetic remark**.

No unrequested rewrites. The planner proposes; the human decides.

Review is not optional. In the pilot the first pass over-claimed 8 of 18 `verified` rows; after the "No guessing" rules and review fixes, an independent audit found 2 of 17. Review the integrated slice or wave. An accepted project ADR may defer independent review of initial implementations in favor of coordinator self-review and focused checks; disclose this, retain acceptance work and do not promote those rows to `verified` in that delivery. Review/fix remains required before final acceptance. Communicate any decision change to every affected worker before integration.

**5. Decisions → ADRs**, parity and roadmap status updated, next stage.

## The handoff format

Fixed, for efficient review ([template](templates/handoff.md)):

1. **Delivered** — what was produced.
2. **Assumptions and differences** — nothing invented; every assumption cited against the real source/schema.
3. **Checks actually executed** — commands, results, OS; and the checks that could not run.
4. **Remaining work**.
5. **Decisions needed from the human**.

Honest self-criticism ("I could not run this") is gold: it directs the review.

## Definition of done for a slice

A rule is not migrated because a screen exists. A slice is done when:

- every parity row in scope is `verified` (names the test that ran) or `excluded` (names the ADR);
- `npm run verify` passes, including the parity check;
- the slice's golden scenarios pass ([10](10-parity-and-verification.md));
- failure cases show the legacy messages; data persists after restart; report totals match;
- native checks ran on the target OS, or are listed as not run;
- **the human has run the slice** (`npm run dev:seed` or equivalent) and tried its workflows. Agents often cannot open GUI windows, so this is usually the first time the app is seen running.

Example: a repair-order save is complete when validation, material/time recording, failure handling, persistence after restart and report totals behave as agreed.

An **initial implementation** milestone may close with `implemented` rows and named acceptance work in the roadmap. It is not slice acceptance or migration completion; unavailable source/native confirmation need not block unrelated implementation.

## Checks to use

- Domain tests for money/time/stock rules, named with parity IDs.
- Integration tests against a temporary database for transactions and migrations (Rust `cargo test`).
- Browser workflow tests (Playwright or Vitest browser mode) with Tauri IPC mocked through `@tauri-apps/api/mocks`, using legacy control names as `data-testid`.
- Native end-to-end tests through [WebDriver](https://v2.tauri.app/develop/tests/webdriver/) with `tauri-driver` (Windows and Linux; macOS has no WebDriver support for WKWebView), plus manual smoke checks where automation is unavailable.
- Golden scenarios compared with `scripts/compare_exports.py`.
- **UI control coverage:** `npm run ui:check` ([templates/ui-check](templates/ui-check/), chapter 10 §3) in every UI slice.
- **UI inspection by the agent:** in dev mode outside Tauri, the app installs the test fake backend (`mockIPC` with the golden data) behind a visible "browser preview" banner. The agent opens the Vite dev server in a browser preview, clicks through the slice's workflows and checks layout, focus and exact messages before the human run. It proves UI behavior only, never the Rust commands. Wait for the screen to settle before trusting a screenshot.

Use the smallest meaningful set for the change; expand when failures or new risks justify it. The npm scripts are defined by the foundation slice ([06 §7](06-start-a-migration.md#7-foundations)).

## Parallel implementation waves

- Start after the first persisted workflow and shared primitives work together. Group related screens/reports into complete workflow families; do not assign all UI to one worker and all persistence to another. Keep real foundation dependencies.
- One coordinator owns the base commit, shared contracts, migrations, dependencies, generated outputs and aggregate tracking. Workers request shared changes from that owner. Size the wave to available slots, leaving capacity for integration; rotate workers as families finish.
- Give each worker a [lean packet](templates/prompt-stage.md#parallel-wave-packet), not the full chat history. Isolate writers in worktrees and use separate test databases, enrollment profiles, ports, caches and build outputs. Preserve untouched source/data backups and the owner's running demo.
- Workers implement real consuming paths and run focused checks. Return a frozen commit or explicit file/hash manifest, per-row implementation claims, executed checks and known gaps. A rendered screen, placeholder button or file-presence assertion is not behavior coverage.
- The coordinator checks the base and frozen files, integrates explicit changes, reviews/fixes the combined result and runs the full verification gate once for that result. Repeat affected checks after fixes; broaden when failures or shared changes justify it. Exercise an ordinary save/reopen/report journey through the built app; browser mocks do not prove native persistence, preview or printing. Label results with OS and commit.
- Only the coordinator updates parity, roadmap, progress and the rolling handoff. Preserve stable seed IDs and source provenance; report built targets, verified targets and unanswered source questions separately ([10](10-parity-and-verification.md#1-a-closed-world-inventory)). Claiming existing code or adopting a default is not a newly written feature or proof of legacy behavior.
- Keep one reusable `docs/runbooks/current-stage.md` brief and the latest closed handoff; Git retains history. Worker packets/manifests can be temporary. Put durable choices in the applicable ADR/spec/porting pattern, not a new runbook per worker.

## Running agents for long stretches

- Resume from durable state with a bounded slice or workflow-family packet; avoid requiring one fresh session per screen.
- Use sub-agents for implementation, source reading and review where useful; record durable conclusions in the canonical docs.
- When blocked by a human decision, record it in the handoff under "Decisions needed", mark the slice `Blocked`, and move to the next **independent** slice.
- Never relax a test, a parity status or a guard to get green. If a legacy behavior seems wrong, preserve it and raise it as a decision.

## Response preferences (in `AGENTS.md`)

**A preference, not a rule** — set yours. Some want **concise answers, no full listings unless asked**; others prefer a detailed, explanatory assistant.

The **method** does not change: do not challenge accepted choices, give the points to fix without replaying everything, and **read files completely before concluding**.

## Anti-patterns (real traps)

- ❌ Assuming instead of **checking the repository / inspecting the schema / reading the legacy source**.
- ❌ Translating WLanguage line by line without checking [09 — WLanguage traps](09-wlanguage-traps.md).
- ❌ Marking a parity row verified because the screen renders or the build passes.
- ❌ A `DROP` or corrective migration slipped into a schema change; editing a committed migration.
- ❌ Mixing the development machine and the test machine.
- ❌ Versioning a secret (token, connection string with password, `.bak`, HFSQL data file).
- ❌ Building a business module **before** the foundations (schema, import, verify pipeline).
- ❌ Inflating `AGENTS.md` instead of using `docs/`.
- ❌ Letting an AI judge green/red: the machine replays, deterministically.
- ❌ Redesigning screens nobody asked to change.
