# WINDEV → TypeScript + Tauri migration playbook

An evidence-based, AI-driven method for rebuilding WINDEV/HFSQL business applications as modern desktop apps **with measurable feature parity**. Adapted from [windev-vers-dotnet](https://github.com/migration-windev/windev-vers-dotnet), with attribution and upstream history preserved.

**This is a playbook plus a source-inspection and verification toolkit, not an automatic transpiler or a finished application.** WLanguage behavior must be understood, reimplemented and proven. No customer application or database is distributed here.

## The idea in one sentence

> Two AI roles and you: a **planner/reviewer** (the brain: architecture, stage prompts, review, memory) and an **implementer** (the hands: code, tests, commits, handoff). **You validate every stage.** It is not magic: it is an engineering chain where **structure beats prompts**, and where **parity is counted, not claimed**.

| Planner / reviewer — the brain | Implementer — the hands | You — the pilot |
|---|---|---|
| frames, designs, **writes stage prompts**, **reviews**, keeps roadmap and memory | codes in the repository (on its isolated machine), **tests for real**, commits, pushes, writes the **handoff** | **validate** each stage, **decide**, **bridge** the two (paste prompts, `git pull`) |

One agent can play both AI roles in separate passes; the separation of concerns is what matters. Works with Claude Code, Codex or other coding agents: rules live in `AGENTS.md`, skills are plain Markdown and guardrails run in Git and CI ([04](04-project-memory.md#claude-code-codex-and-other-agents)).

## Proposed target

- React + TypeScript + Vite for the interface; legacy control names kept as `data-testid`.
- Framework-independent TypeScript for domain rules and use cases (one home per rule).
- Tauri 2 with a thin Rust layer: typed commands, one transaction per business save, migrations.
- SQLite when one installed application owns the data; a TypeScript API + PostgreSQL for shared multi-workstation data.
- Vitest for domain tests, browser workflow tests with mocked IPC, WebDriver/native smoke tests on each target OS, and golden scenarios recorded in the legacy app.

These are the recommended defaults the planner brings to framing; every choice is confirmed and recorded as an ADR. Tauri includes Rust: a TypeScript UI does not make the native app TypeScript-only, and Node libraries do not run in its webview.

## The journey

### Step 0 — Infrastructure *(once)*
Accounts, Git host (it replaces the WINDEV source manager), an isolated machine for the coding agent, a legacy Windows environment with WINDEV, and a nightly test machine if possible → [00](00-prerequisites.md), [02](02-infrastructure.md).

### Step 1 — Prepare the sources *(`legacy/`)*
Switch the WINDEV project to **text format**, generate the **SQL script** from the analysis, export queries and sanitized **CSV** data, take **screenshots named after each window**, keep sample **report PDFs** with their inputs → [00 §E](00-prerequisites.md#e-collect-the-legacy-material). Tip: WINDEV 2026's AI Companion `/init_projet` writes a project-context file — add it to `legacy/docs/`.

### Step 2 — Inspect and map *(before any code)*
If the project folder has WINDEV's documentation PDF (`<project>_Documentation.pdf`), extract it first: `python3 scripts/dossier_extract.py <pdf> --out analysis-local/dossier`.

```sh
python3 scripts/inspect_windev.py legacy/code --out analysis-local/inspect-1
```
The inspector inventories sources, extracts code blocks with their window/control/event context, reads raw XDD metadata, flags hardcoded-secret locations and writes a **parity seed** (one row per block, table and missing export). Then parallel sub-agents map every element and other agents cross-review them ([mapping prompt](templates/mapping-prompt.md)) → [06](06-start-a-migration.md).

### Step 3 — Framing *(the initialization prompt)*
Paste [templates/PromptInit.md](templates/PromptInit.md) into the planning session. It asks **the questions that change the plan** (topology, persistence, OS, rights, reports, UI fidelity, integrations, order — **your** choices), then sets up `AGENTS.md`, ADRs, guards, the parity matrix and the roadmap.

### Step 4 — The loop *(the core of the work)*
For each roadmap slice: the planner writes a bounded prompt → the implementer builds UI + domain + command + tests, runs `npm run verify` and golden scenarios, commits, pushes, writes the handoff → you `git pull` → the planner reviews in four categories → decisions become ADRs → parity and status updated → [05](05-work-loop.md), [01](01-principles-and-roles.md).

### Step 5 — Nightly test machine *(if possible)*
Rebuilds the database, replays every test and golden scenario, pushes a timestamped report — the safety net → [02](02-infrastructure.md#test-machine-the-nightly-safety-net).

### Step X — The Tauri application
At the end of the roadmap: `parity_check.py --require-complete` passes, golden scenarios and reconciliation are green on every target OS, cutover is rehearsed → [10](10-parity-and-verification.md), [08](08-data-migration.md#cutover).

## Guide

**Where to start:** follow [The journey](#the-journey) above; [06](06-start-a-migration.md) details each step.

| Chapter | Purpose |
|---|---|
| [00 — Prerequisites](00-prerequisites.md) | Accounts, tools, legacy Windows environment, isolated agent machine, source collection layout |
| [01 — Principles and roles](01-principles-and-roles.md) | Roles, golden rule, non-negotiables, mindset |
| [02 — Infrastructure](02-infrastructure.md) | Repositories, CI, nightly test machine, packaging, updates, prompt/code flow |
| [03 — Scope and architecture](03-scope-and-architecture.md) | What the guide decides vs you, rule homes, command pattern, IPC contracts, UI choices |
| [04 — Project memory](04-project-memory.md) | `AGENTS.md`, local instructions, docs, ADRs, handoff, skills, hooks |
| [05 — Work loop](05-work-loop.md) | Roadmap, stage cycle, review, definition of done, anti-patterns |
| [06 — Start a migration](06-start-a-migration.md) | Inspect → map → frame → foundations → first slice → rollout |
| [07 — Platform replacements](07-platform-replacements.md) | Telemetry, identity/Groupware, store/updates, reports, jobs, devices, integrations |
| [08 — Data migration](08-data-migration.md) | HFSQL feature map, SQLite/PostgreSQL, transformation, reconciliation, cutover |
| [09 — WLanguage traps](09-wlanguage-traps.md) | Semantics that silently break translations |
| [10 — Parity and verification](10-parity-and-verification.md) | Closed-world matrix, golden scenarios, UI/report/native checks, gates |
| [Scripts](scripts/README.md) | Inspector, parity gate, export comparator |
| [Upstream audit](docs/upstream-audit.md) | Where every upstream section lives now, and what was replaced |

**Templates** ([templates/](templates/)): `AGENTS.template.md`, `CLAUDE.template.md`, local instruction files, `PromptInit.md`, `mapping-prompt.md`, `prompt-stage.md`, ADR, handoff, roadmap, parity matrix, window spec, golden scenario, compare config, agent-neutral skills (`review`, `map-element`, `review-mapping`), shared guard with a Git pre-commit hook, and a Claude Code adapter (settings).

## Audience

WINDEV / WEBDEV / WINDEV Mobile developers and teams who want an AI coding agent to migrate an application to TypeScript + Tauri without losing behavior.

## Notation

Project-specific values are written in angle brackets: `<App>` (application name), `<repository>`, `<WIN_Name>`… Replace them when using a template. If your application **complements a third-party system** (ERP, accounting…), it is called the "third-party system"; otherwise ignore those mentions.

## Validation status

Tested on a real WINDEV 28 project (51 windows, 17 tables):

- **Inspector:** run on the full project; two parser bugs found on real files and fixed.
- **Mapping skill:** 3 windows mapped by parallel agents; an independent cross-review confirmed 14 of 15 key claims.
- **Build loop:** the client list and form built in Tauri through 4 stages with independent reviews. The first pass over-claimed 8 of 18 `verified` rows; after the "No guessing" rules and one fix stage, the final audit found 2 of 17.
- **Dossier extraction:** WINDEV's 2,303-page project documentation turned into per-element JSON (captions, tab order, masks, 29 queries' SQL) and 106 window/report images.
- **Event legend:** 15 event codes verified from the project's compile folder (18 = Click, 293 matches; also Initialization, optional mouse and keyboard events, report Open/Before/After printing), no conflict.
- **Schema draft:** 17 tables, 135 items from the XDD, type codes named by pairing with the dossier (14 codes, no conflict), a draft SQLite DDL that loads, 35 per-column decisions. The cross-check exposed dossier items the PDF parser dropped; all 133 keyed items now agree between XDD and dossier.
- **Encoded actions:** 225 code-less Click slots whose predefined action WINDEV encrypts (and 48 next to code), made visible as parity rows and grouped by equal encoded value into 14 distinct actions (nothing decoded): one human answer per group. A first version also counted the encrypted properties of table columns and calendars; two independent mappers caught it.
- **Measured on one list window (rounds 5 → 6):** with the evidence pack and checklists, a docs-only implementer found behavior-affecting silent gaps fall from about 8 to 3 (the rest cosmetic) and could build about 80% of the screen; the blockers left are runtime questions for the answer sheet.
- **Small-scale mapping runs (6 rounds):** dossier-aware mapping of a form and a report cut open questions from 10 to 5 (form), all remaining ones runtime-only; each round's harness feedback went into the tools. A docs-only implementer test and a cross-review shaped the spec templates and the review-mapping skill.
- **Not yet:** the ODBC export against the HFSQL driver, and golden scenarios recorded from the legacy app.
- **Tried and removed:** an automated UI crawler driving the running app through Windows UI Automation. On the real app it logged in but WINDEV exposed no menu items, so it captured no windows; the dossier provides that evidence instead.

## Verification and limits

`python3 -m unittest discover -s tests -v` runs the toolkit tests (inspector, parity gate, comparator, guard in all modes, documentation links and anchors). Native application checks belong to each application repository. This repository does not include a runnable Tauri app, a WLanguage compiler, an HFSQL reader or a query decoder.

See [NOTICE](NOTICE), [LICENSE](LICENSE), [CHANGELOG](CHANGELOG.md) and [CONTRIBUTING](CONTRIBUTING.md).
