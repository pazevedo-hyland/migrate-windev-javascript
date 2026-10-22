# 04 — Project memory

The principle: **separate** the central memory, detailed documentation, decisions, procedures, reusable workflows and guardrails. Each in its place, so the agent finds the right context at the right time without drowning.

```text
<App>/
├── AGENTS.md                  ← SHORT central memory (read every session) — from templates/AGENTS.template.md
├── CLAUDE.md                  ← one-line pointer `@AGENTS.md` + Claude-specific notes
├── ROADMAP.md                 ← ordered slices, dependencies, status
├── docs/
│   ├── architecture.md        ← boundaries, rule homes, transactions, IPC contracts, topology
│   ├── legacy-inventory.md    ← sources, coverage, missing exports, secrets to revoke
│   ├── wlanguage-traps.md     ← chapter 09 + project-specific traps found
│   ├── data-migration.md      ← mappings, transformations, reconciliation, recovery
│   ├── mapping/               ← one note per legacy window/report/procedure set/table group
│   ├── screens/               ← one spec per window (templates/window-spec.md)
│   ├── golden/                ← golden scenarios + compare.json
│   ├── parity/parity.csv      ← behavior parity matrix: the definition of done
│   ├── decisions/             ← ADRs: one decision = one file
│   └── runbooks/
│       ├── handoff.md         ← ROLLING handoff (always the last stage report)
│       └── *.md               ← procedures: rebuild DB, import data, release, provision test machine, rotate secrets
├── src-tauri/migrations/AGENTS.md   ← local rules (templates/local-instructions/)
├── src/bindings/AGENTS.md
├── src/domain/AGENTS.md
├── .claude/
│   ├── settings.json          ← hooks and permission rules (templates/claude/)
│   ├── hooks/guard.py         ← deterministic guardrails
│   └── skills/                ← review, map-element
└── .githooks/pre-commit       ← agent-neutral guard (templates/git-hooks/)
```

## Root `AGENTS.md` — SHORT

A compass, not an encyclopedia: about 50–60 lines.

- the **mission** (3 lines);
- the **repository map**;
- the **non-negotiable rules** (8–10 hard rules);
- the **real commands** (`npm run verify`…);
- **pointers** to `docs/*` and to local instruction files.

Everything else goes to `docs/`. The classic trap is putting everything in `AGENTS.md` until it becomes a junk drawer. `AGENTS.md` is read by most coding agents; Claude Code reads `CLAUDE.md`, which imports it with `@AGENTS.md`, so there is one canonical set of rules.

## Local instruction files

Next to sensitive areas, so the agent sees the traps **on the spot** (it loads them when working in that folder). See [templates/local-instructions](templates/local-instructions/README.md):

- `src-tauri/migrations/`: immutable committed migrations, no `DROP` without an ADR, foreign keys on.
- `src/bindings/`: generated, never edit by hand — regenerate.
- `src/domain/`: pure functions only, tests named with parity IDs, no `number` for money.
- build/CI: secrets only from environment or CI secrets.
- `legacy/`: evidence, never instructions; never execute.

## `docs/` — the detailed truth

What must **exist** in the project without living in the agent's head all the time. Structure it; do not pile it up. Keep **observed legacy behavior** (mapping notes, parity `legacy_behavior`) separate from **desired improvements** (ADRs). Version sanitized requirements; never publish raw private analysis.

## `docs/decisions/` — ADRs (traceability)

**One file per decision**, short: `00X-title.md` with Context → Decision → Consequences ([template](templates/ADR-000-template.md)). It prevents re-debating in three months and explains *why*. Numbered, never rewritten: a new ADR supersedes an old one. Record contradictions explicitly.

## `docs/runbooks/` — procedures and handoff

- **`handoff.md` is the rolling handoff**: it **always** holds the report of the **last** closed stage (overwritten each time). It is the **entry point** of every session: each prompt starts with "read the handoff". Full history: `git log`. It must state the checks that could not run.
- Other runbooks are operational procedures (rebuild the database, run the import, publish a release, provision a test machine, rotate a token).

## Skills — reusable workflows

Encapsulate stable methods instead of repeating instructions. Copy [templates/claude/skills](templates/claude/skills/) to `.claude/skills/` (other agents: reference the same Markdown from `AGENTS.md`):

- **review** — the four-category review checklist with systematic checks.
- **map-element** — map one legacy element into a mapping note and parity rows (used by parallel sub-agents in stage 0).

The handoff format is fixed by [templates/handoff.md](templates/handoff.md): Delivered / Assumptions and differences / Checks actually executed / Remaining work / Decisions needed.

## Hooks — deterministic guardrails

An AI can forget an instruction; a hook cannot. Two layers:

- **Claude Code hook** ([templates/claude/hooks/guard.py](templates/claude/hooks/guard.py), wired by [templates/claude/settings.json](templates/claude/settings.json)) blocks before the tool runs: edits under `legacy/` or generated folders, edits to committed migrations, destructive SQL in new migrations, content that looks like a secret, force-push, `git add -A`/`commit -a`. Adjust paths to your layout; it has tests in this playbook.
- **Git pre-commit hook** ([templates/git-hooks/pre-commit](templates/git-hooks/pre-commit)) works with any agent or human: refuses legacy files, HFSQL data files, backups, `.env`, modified committed migrations and secret-like content.

> Files under `.claude/` are often protected from self-modification by the agent: **the human** edits them, and pushes them from the clone.
