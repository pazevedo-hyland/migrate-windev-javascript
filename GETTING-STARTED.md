# Getting started — the first two weeks

A concrete checklist. Each step links to the chapter with the details. Owners: **H** human, **A** coding agent, **P** planner/reviewer session.

## Day 1 — Set up (H)

- [ ] Read [README](README.md), [01 — Principles](01-principles-and-roles.md) and [10 — Parity](10-parity-and-verification.md) (30 minutes total: they explain why every later step exists).
- [ ] Create the private application repository; copy `templates/` and `scripts/` from this playbook; add `.gitignore` entries for `legacy/`, `analysis-local/`, HFSQL data files and `.env` (start from this repository's `.gitignore`).
- [ ] Install the guards and agent adapters ([11 — Agents](11-agents.md#installing-the-adapters-in-an-application-repository)); enable branch protection on `main`.
- [ ] Give the agent an isolated machine or container with Node, Rust, Tauri prerequisites and Python ([00 §D](00-prerequisites.md#d-an-isolated-machine-for-the-coding-agent)).
- [ ] Create the Jira project/epics of [12](12-project-tracking.md#ticket-structure) (empty for now).

## Days 2–3 — Collect the legacy material (H, on the WINDEV machine)

- [ ] Switch the project to text format and copy it to `legacy/code/` ([00 §E](00-prerequisites.md#e-collect-the-legacy-material)).
- [ ] Generate the SQL script and XDD from the analysis → `legacy/schema/`.
- [ ] Export sanitized CSV data with a manifest → `legacy/data/`.
- [ ] Screenshot every window and state, named after the window → `legacy/screenshots/`.
- [ ] Print every report to PDF with its input data → `legacy/reports/`.
- [ ] Optional: WINDEV 2026 `/init_projet` → `legacy/docs/`.

## Day 3 — Inspect (A or H)

```sh
python3 scripts/inspect_windev.py legacy/code --out analysis-local/inspect-1
```

- [ ] Check `inventory.json`: how many files are `binary-or-unsupported`? Open Jira tasks "export <file> from WINDEV" for each.
- [ ] Spot-check 3–5 entries of `code/*.json`: do `context.names` show the right window/control? Does `literal_keys` reveal other embedded sources (use `--block-key`)? If the structure differs from what the inspector expects, fix that before mapping.
- [ ] Open `secret-hints.json`: plan revocation of every credential found.

## Days 4–6 — Map (A with sub-agents or parallel sessions, then P reviews)

- [ ] Run [templates/mapping-prompt.md](templates/mapping-prompt.md).
- [ ] Gate: `python3 scripts/parity_check.py docs/parity/parity.csv --seed analysis-local/inspect-1/parity-seed.csv` passes.
- [ ] First report: `python3 scripts/status.py --roadmap ROADMAP.md` — everything is `unmapped`/`specified`; that is the baseline.

## Days 6–7 — Frame (P with H)

- [ ] Paste [templates/PromptInit.md](templates/PromptInit.md) into the planning session with the mapping notes; answer the framing questions; accept or change the recommended architecture ([03](03-scope-and-architecture.md)).
- [ ] ADRs written; `AGENTS.md`, local instruction files and `ROADMAP.md` created.
- [ ] Generate stories: `python3 scripts/status.py --work-items analysis-local/work-items.csv`; import into Jira; write the keys back into `parity.csv` ([12](12-project-tracking.md#generating-stories-from-the-parity-matrix)).

## Week 2 — Foundations and first golden scenarios

- [ ] (A) Scaffold the Tauri app, `npm run verify` in CI on the target OSes, bindings generation, schema v1, import dry run with reconciliation report ([06 §7](06-start-a-migration.md#7-foundations)).
- [ ] (H) Record golden scenarios for the first workflow in the legacy app ([template](templates/golden-scenario.md)).
- [ ] (P) Write the first slice's stage prompt from its story ([template](templates/prompt-stage.md)).

## Then — the loop, one slice at a time

Prompt → implement → verify → handoff → review → ADRs → parity/roadmap/Jira updated ([05](05-work-loop.md)). Post `status.py` weekly. The migration is done when `parity_check.py --require-complete --seed …` passes and cutover is rehearsed ([08](08-data-migration.md#cutover)).

## Signs something is going wrong

- Parity percentage rises but `unresolved` stays high → agents are implementing guesses.
- Many rows `implemented`, few `verified` → tests or golden scenarios are missing.
- Slices keep returning from review with parity gaps → stage prompts lack evidence; add screen specs and golden scenarios first.
- Human tasks pile up in "Waiting for human" → the bottleneck is exports and recordings, not coding.
