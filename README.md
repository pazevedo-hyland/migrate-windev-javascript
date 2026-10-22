# WINDEV → TypeScript + Tauri migration playbook

An evidence-based workflow for rebuilding WINDEV/HFSQL business applications as modern desktop apps. Adapted from [windev-vers-dotnet](https://github.com/migration-windev/windev-vers-dotnet), with attribution and upstream history preserved.

**This is a playbook and source-inspection toolkit, not an automatic transpiler or a finished application.** WLanguage behavior must be understood, reimplemented, and tested. No customer application or database is distributed here.

## Proposed target

- React + TypeScript + Vite for the interface.
- Framework-independent TypeScript for domain rules and application services.
- Tauri 2 with a small Rust layer for typed native commands and transactional database operations.
- SQLite for a genuinely local application; a TypeScript API + PostgreSQL for shared multi-workstation data.
- Vitest for domain tests, browser component/workflow tests, and native smoke tests on supported operating systems.

These are starting recommendations. Confirm deployment, concurrency, hardware, and reporting needs before committing to a project architecture. Tauri includes Rust: a TypeScript UI does not make the complete native application TypeScript-only. Node libraries and Node database drivers do not automatically run in its webview.

## Start here

1. Clone this playbook into a separate repository for your migration.
2. Collect legacy source, schema exports, screenshots, reports, and sanitized examples under local, ignored `legacy/`.
3. Run the optional dependency-free Python inspection tool:

```sh
python3 scripts/inspect_windev.py /path/to/legacy-project --out analysis-local
python3 -m unittest discover -s tests -v
```

It inventories recognized WINDEV files, extracts readable code blocks with source line numbers, and reads raw XDD schema metadata. Binary queries are explicitly marked unresolved. Outputs may contain business logic and embedded credentials: `analysis-local/` is ignored; review before sharing.

4. Use [the initialization prompt](templates/PromptInit.md) to turn evidence into a scope, architecture, and roadmap.
5. Implement one complete business workflow, compare it against the old application, then expand.

## Guide

| Chapter | Purpose |
|---|---|
| [00 — Prerequisites](00-prerequisites.md) | Local tools and legacy export environment |
| [01 — Principles and roles](01-principles-and-roles.md) | Evidence, human decisions, implementation and review |
| [02 — Infrastructure](02-infrastructure.md) | Repository, native builds, CI and releases |
| [03 — Scope and architecture](03-scope-and-architecture.md) | TypeScript/Rust boundary and project decisions |
| [04 — Project memory](04-project-memory.md) | Agent instructions, ADRs and handoffs |
| [05 — Work loop](05-work-loop.md) | Small, verifiable migration steps |
| [06 — Start a migration](06-start-a-migration.md) | Source collection through first vertical slice |
| [07 — Platform replacements](07-platform-replacements.md) | Reporting, identity, updates, hardware and jobs |
| [08 — Data migration](08-data-migration.md) | HFSQL semantics, SQLite/PostgreSQL, reconciliation |
| [Inspection tool](scripts/README.md) | Supported formats and explicit limitations |
| [Adaptation audit](docs/upstream-audit.md) | Upstream decisions retained, replaced and extended |

Templates cover agent instructions, initialization, an implementation step, decisions, handoffs, review, and behavior parity. The guides are assistant-neutral and can be used with a single coding assistant; separate planning and review sessions are optional.

## Verification and limits

Run `python3 -m unittest discover -s tests -v` for extractor tests. Native application checks belong to each generated project, whose dependencies and lockfiles must be committed there. This repository does not yet include a runnable Tauri app, a WLanguage compiler, an HFSQL reader, or a query decoder.

See [NOTICE](NOTICE), [LICENSE](LICENSE), and [CONTRIBUTING](CONTRIBUTING.md).
