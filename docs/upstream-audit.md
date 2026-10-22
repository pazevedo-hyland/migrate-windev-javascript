# Upstream adaptation audit

Source: https://github.com/migration-windev/windev-vers-dotnet — inspected base commit `2f3e04c808070bb5631299a10f287d47dffd2874` (README, chapters 00–08, six templates, CHANGELOG, CONTRIBUTING, MIT license). The upstream repository contains documentation and templates only, with no converter or application scaffold.

This table traces **every upstream section** to its place in this playbook, so nothing is lost silently. "Replaced" means a .NET-specific product was swapped for a TypeScript/Tauri equivalent; "Changed" means the guidance was deliberately altered, with the reason.

## Traceability

| Upstream section | Here | Status |
|---|---|---|
| README — one-sentence idea, two AIs + human roles table | [README](../README.md#the-idea-in-one-sentence) | Kept (assistant-neutral) |
| README — journey steps 0–4 and X | [README — The journey](../README.md#the-journey) | Kept |
| README — `origine/` layout (code, autres, data, screenshoot) with export how-tos | [00 §E](../00-prerequisites.md#e-collect-the-legacy-material) | Kept and extended (`legacy/` with queries, reports, golden; screenshots named per window) |
| README — WINDEV 2026 `/init_projet` tip | [00 §C](../00-prerequisites.md#c-the-legacy-windows-environment), README step 1 | Kept |
| README — audience, notation `<App>`, third-party system | [README](../README.md#notation) | Kept |
| 00 A — accounts (Claude, Microsoft) | [00 §A](../00-prerequisites.md#a-accounts) | Replaced (Microsoft account not required) |
| 00 B — software (Claude app, Visual Studio, Git) | [00 §B](../00-prerequisites.md#b-tools-on-the-development-machine) | Replaced (Node, Rust, Tauri prerequisites, Python) |
| 00 C — Git server, Gitea on NAS, Git replaces GDS | [00 §A](../00-prerequisites.md#a-accounts), [02 — Repositories](../02-infrastructure.md#repositories) | Kept (GitHub or self-hosted) |
| 00 D — dedicated agent VM and its three reasons; complete local dev env (DB engines, ODBC/OLE DB, data copy, never prod) | [00 §D](../00-prerequisites.md#d-an-isolated-machine-for-the-coding-agent) | Kept (VM, dev container or cloud sandbox) |
| 01 — two AIs table, human in control | [01 — The roles](../01-principles-and-roles.md#the-roles) | Kept; one agent may play both roles in separate passes |
| 01 — golden rule "prompt temporary, structure permanent" | [01](../01-principles-and-roles.md#the-golden-rule) | Kept |
| 01 — six non-negotiables | [01 — Non-negotiables](../01-principles-and-roles.md#non-negotiables) | Kept; added evidence labels, parity as done, machine judges |
| 01 — mindset (frame first, short stages, 3-category review, real data early) | [01 — The mindset](../01-principles-and-roles.md#the-mindset) | Kept; review extended to 4 categories (parity gap) |
| 02 — overview diagram | [02](../02-infrastructure.md#overview) | Kept, with CI runners |
| 02 — Gitea, two repositories, plain git, token in credential manager | [02 — Repositories](../02-infrastructure.md#repositories) | Kept |
| 02 — Velopack installer/auto-update, channels prod/test | [02 — Packaging](../02-infrastructure.md#packaging-updates-and-signing), [07 §C](../07-platform-replacements.md#c-distribution-and-updates--the-private-store) | Replaced by Tauri bundler + updater |
| 02 — read-only token injected and obfuscated in the client | [02 — Packaging](../02-infrastructure.md#packaging-updates-and-signing) | **Changed**: never embed a reusable token; serve updates from an endpoint needing no embedded secret |
| 02 — dev VM | [00 §D](../00-prerequisites.md#d-an-isolated-machine-for-the-coding-agent) | Kept |
| 02 — test VM: dedicated DB, third-party DB restore, nightly job, `reports` branch, machine marker, verified push, machine judges | [02 — Test machine](../02-infrastructure.md#test-machine-the-nightly-safety-net) | Kept; adds golden scenarios and native smoke |
| 02 — prompt flow, code flow, push from clone, anti-conflict rule | [02 — Synchronization](../02-infrastructure.md#synchronization-and-prompt-flow) | Kept |
| 03 — what the guide covers / does not decide / the one code requirement | [03](../03-scope-and-architecture.md#what-this-guide-decides-and-what-it-leaves-to-you) | **Changed**: a concrete default architecture is proposed (agents perform better with one default); every choice still confirmed by ADR |
| 04 — memory anatomy tree | [04](../04-project-memory.md) | Kept (AGENTS.md + CLAUDE.md pointer) |
| 04 — short root CLAUDE.md (~50–60 lines, 5 parts) | [04 — Root AGENTS.md](../04-project-memory.md#root-agentsmd--short) | Kept |
| 04 — local CLAUDE.md files (database, generated entities, build) | [04 — Local instruction files](../04-project-memory.md#local-instruction-files), [templates/local-instructions](../templates/local-instructions/README.md) | Kept (migrations, bindings, domain, CI, legacy) |
| 04 — docs/, ADRs, runbooks, rolling handoff | [04](../04-project-memory.md#docs--the-detailed-truth) | Kept |
| 04 — skills (review, handoff format) | [04 — Skills](../04-project-memory.md#skills--reusable-workflows), [review](../templates/claude/skills/review/SKILL.md), [map-element](../templates/claude/skills/map-element/SKILL.md) | Kept and extended |
| 04 — hooks (block DROP, forbidden commands); `.claude/` edited by the human | [04 — Hooks](../04-project-memory.md#hooks--deterministic-guardrails), [guard.py](../templates/claude/hooks/guard.py), [pre-commit](../templates/git-hooks/pre-commit) | Kept and implemented, with tests |
| 05 — roadmap fields | [05 — The roadmap](../05-work-loop.md#the-roadmap), [ROADMAP template](../templates/ROADMAP.template.md) | Kept |
| 05 — stage cycle diagram, prompt preamble and closing, 3-category review, ADR + status | [05 — Cycle](../05-work-loop.md#the-cycle-of-a-stage) | Kept |
| 05 — handoff format (5 sections), honest self-criticism | [05 — Handoff format](../05-work-loop.md#the-handoff-format), [template](../templates/handoff.md) | Kept |
| 05 — response preferences | [05](../05-work-loop.md#response-preferences-in-agentsmd), [AGENTS template](../templates/AGENTS.template.md) | Kept |
| 05 — anti-patterns | [05](../05-work-loop.md#anti-patterns-real-traps) | Kept and extended |
| 06 — infra → sources → parallel sub-agent mapping with cross-review → framing → loop | [06](../06-start-a-migration.md), [mapping prompt](../templates/mapping-prompt.md) | Kept; adds inspector, parity seed, foundations, rollout |
| 06 — UI style choice (designer-first WINDEV-like vs code-first) | [06 §6](../06-start-a-migration.md#6-frame-with-the-planner), [prompt-stage](../templates/prompt-stage.md#reusable-instructions-pick-according-to-accepted-choices) | Replaced (WINDEV-like replica vs modernized layout) |
| 07 — remaining PC SOFT services list | [07 — Quick map](../07-platform-replacements.md#quick-map) | Kept and extended (devices, files, INI/registry, Office, COM/DLL) |
| 07 — DevExpress XAF path | [07 §B](../07-platform-replacements.md#b-identity-oauth-and-rights), [§D](../07-platform-replacements.md#d-reports-and-printing) | **Not applicable** (.NET framework); the same trade-off (packaged commercial suite vs build) is kept for reports |
| 07 A — telemetry (OpenTelemetry + SigNoz) | [07 §A](../07-platform-replacements.md#a-telemetry-and-error-reporting) | Kept, + tauri-plugin-log and error tracker |
| 07 B — OAuth server, Keycloak, Groupware rights pattern (catalog, rights table, enforcement), OpenFGA/Casbin | [07 §B](../07-platform-replacements.md#b-identity-oauth-and-rights) | Kept; adds PKCE for native apps, keychain storage. Visual Guard dropped (.NET-only) |
| 07 C — private store (Velopack + portal + Keycloak), honest nuance | [07 §C](../07-platform-replacements.md#c-distribution-and-updates--the-private-store) | Replaced (Tauri updater + portal) |
| 07 D — reports: QuestPDF vs DevExpress/Syncfusion designers | [07 §D](../07-platform-replacements.md#d-reports-and-printing) | Replaced (HTML/pdfmake/Typst vs commercial JS designers) + printing |
| 07 E — scheduled tasks (Quartz.NET/Hangfire, Worker Service) | [07 §E](../07-platform-replacements.md#e-scheduled-tasks-and-batch) | Replaced (OS scheduler + headless CLI, or server worker) |
| 07 F — mobile replication, push, real-time (SignalR), DB admin | [07 §F](../07-platform-replacements.md#f-depending-on-your-profile--offlinemobile-real-time-database-admin) | Replaced (sync engine, notification plugin, WebSockets, DB tools) |
| 07 — summary table, glossary, links | [07](../07-platform-replacements.md#summary) | Kept |
| 08 — which HFSQL (Classic vs Client/Server) and target family | [08](../08-data-migration.md#first-which-hfsql) | **Changed**: decided by topology, since Classic files can be shared |
| 08 — ORM (EF Core, Dapper) | [08 — Data access](../08-data-migration.md#data-access-in-the-target) | Replaced (sqlx/rusqlite, Kysely/Drizzle) |
| 08 — HFSQL feature table (✅/🟧/⚠️) | [08](../08-data-migration.md#what-you-get-back-what-must-be-rebuilt) | Kept and extended (WLanguage triggers, currency, collation, locks, IDs) |
| 08 — three points (encryption, GDPR, SDD) | [08](../08-data-migration.md#three-points-that-deserve-a-real-decision) | Kept |
| 08 — where to start (4 steps), glossary, links | [08](../08-data-migration.md#where-to-start) | Kept |
| Templates — CLAUDE.template | [AGENTS.template](../templates/AGENTS.template.md), [CLAUDE.template](../templates/CLAUDE.template.md) | Kept (six rules → ten) |
| Templates — PromptInit (method, loop, deliverables, discipline, framing questions, order as choice, start) | [PromptInit](../templates/PromptInit.md) | Kept; questions adapted to Tauri; mapping and parity added |
| Templates — ADR, handoff (passation), stage prompt (+ writing reminders, reusable instructions), review skill | [templates/](../templates/) | Kept |
| CHANGELOG, CONTRIBUTING (spirit, neutral tone, PR flow, form) | [CHANGELOG](../CHANGELOG.md), [CONTRIBUTING](../CONTRIBUTING.md) | Kept |

## Additions beyond upstream

- [09 — WLanguage traps](../09-wlanguage-traps.md) and [10 — Parity and verification](../10-parity-and-verification.md).
- Inspector with window/control/event context, parity seed and secret hints; `parity_check.py`; `compare_exports.py`; tested hook guard and pre-commit hook.
- Templates: mapping prompt, map-element skill, roadmap, parity matrix, window spec, golden scenario, compare config.

The original files remain available in Git history (commit `2f3e04c`). The rewritten documentation is an adaptation, not a word-for-word translation. No claim is made that WINDEV windows, reports, authentication or database semantics translate automatically.

## Remaining deliverables for a real application migration

An actual Tauri scaffold, dependency locks, full legacy analysis, query exports, schema mapping, data import, workflow implementation, report/hardware adapters, native CI, installers and acceptance testing belong to each application project. This playbook is the framework for that work.
