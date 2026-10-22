# 05 — The work loop

## The roadmap

The planner keeps an **ordered list of slices** in `ROADMAP.md` ([template](templates/ROADMAP.template.md)): number, phase, slice, parity rows, owner (implementer / planner / sub-agent / human), prompt, expected deliverable, **dependencies**, **status** (To do / In progress / Blocked / Done).

- **Dependencies** dictate the order: never skip a foundation (schema, import, verify pipeline).
- **Status** is updated when each slice closes.
- A slice is one **complete workflow** (UI + domain + command + persistence + tests), not a layer.

## The cycle of a stage

```text
 (1) Planner writes the PROMPT ─▶ (2) Implementer EXECUTES ─▶ (3) Human: git pull
       preamble + closing            code, tests, verify,         (clone up to date)
       │                             commit, push, HANDOFF               │
       ▼                                                                 ▼
 (5) status + parity + ADR ◀─────── (4) Planner REVIEWS (4 categories) ◀─┘
```

**1. The prompt** ([template](templates/prompt-stage.md)) **always** starts with:

> "First read `docs/runbooks/handoff.md`, `AGENTS.md`, `ROADMAP.md` and the ADRs for this slice. Follow the non-negotiable rules. Start with `git pull`."

…and **always** ends with:

> "Run `npm run verify` and the slice's golden scenarios → commit explicit files → push → update `parity.csv`, `ROADMAP.md` and `docs/runbooks/handoff.md`."

Each prompt is **bounded** ("do not build X yet") and lists its parity rows, evidence, normal/boundary/failure cases, and intentional changes.

**2. The implementer executes** in the repository and **tests for real** (not just "it compiles"), commits, pushes, writes the handoff.

**3. The human** runs `git pull` on the clone.

**4. The planner reviews** with the [review skill](templates/agent/skills/review/SKILL.md) and reports **only** real findings:

1. **Blocking error**;
2. **Parity gap** (behavior missing or changed without ADR, `verified` without executed test, WLanguage trap mistranslated);
3. **Naming/convention drift**;
4. **Business/cosmetic remark**.

No unrequested rewrites. The planner proposes; the human decides.

Review is not optional. In the pilot (playbook validation on a real WINDEV app) the first implementation pass over-claimed 8 of 18 `verified` rows (guesses on unresolved behavior, a test that could never fail, placeholders); with the "No guessing" rules in `AGENTS.md` and one fix stage driven by the review findings, an independent audit found 2 of 17. Plan a review-fix stage after each slice, and never change ADRs while a stage is running — the implementer cannot apply decisions it never saw.

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
- native checks ran on the target OS, or are listed as not run.

Example: a repair-order save is complete when validation, material/time recording, failure handling, persistence after restart and report totals behave as agreed.

## Checks to use

- Domain tests for money/time/stock rules, named with parity IDs.
- Integration tests against a temporary database for transactions and migrations (Rust `cargo test`).
- Browser workflow tests (Playwright or Vitest browser mode) with Tauri IPC mocked through `@tauri-apps/api/mocks`, using legacy control names as `data-testid`.
- Native end-to-end tests through [WebDriver](https://v2.tauri.app/develop/tests/webdriver/) with `tauri-driver` (Windows and Linux; macOS has no WebDriver support for WKWebView), plus manual smoke checks where automation is unavailable.
- Golden scenarios compared with `scripts/compare_exports.py`.

Use the smallest meaningful set for the change; expand when failures or new risks justify it. These commands are conventions of the application, not executable commands of this playbook.

## Running agents for long stretches

- One slice per session; start each session fresh from the handoff rather than a long chat history.
- Use sub-agents to read legacy sources in parallel and to review; keep their conclusions in `docs/`, not only in chat.
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
