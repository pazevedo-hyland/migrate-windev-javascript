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
├── skills/                    ← agent-neutral playbooks: review, map-element, review-mapping (templates/agent/skills/)
├── scripts/                   ← inspector, parity gate, status, comparator, guard.py (shared guardrails)
├── .githooks/pre-commit       ← runs scripts/guard.py --staged for every agent and human
└── .claude/settings.json      ← optional Claude Code adapter: hook → scripts/guard.py --hook; skills copied to .claude/skills/
```

Everything above `.claude/` works with any coding agent; agent-specific files are thin adapters over the same rules (see [Claude Code, Codex and other agents](#claude-code-codex-and-other-agents)).

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

Encapsulate stable methods instead of repeating instructions. Copy [templates/agent/skills](templates/agent/skills/) to `skills/` in the application. They are plain Markdown with a short front-matter header, so every agent can follow them: `AGENTS.md` names them ("to review a stage, follow `skills/review/SKILL.md`"), and agents with native skill support can also load them from their own skills folder (e.g. a copy in `.claude/skills/`):

- **review** — the four-category review checklist with systematic checks.
- **map-element** — map one legacy element into a mapping note and parity rows (used by parallel sub-agents in stage 0).
- **review-mapping** — cross-review one unit's mapping against the evidence in six categories, before any code (stage 0, another model or session).

The handoff format is fixed by [templates/handoff.md](templates/handoff.md): Delivered / Assumptions and differences / Checks actually executed / Remaining work / Decisions needed.

## Hooks — deterministic guardrails

An AI can forget an instruction; a hook cannot. One rule set, [templates/agent/guard.py](templates/agent/guard.py) (copy to `scripts/guard.py`; tested in this playbook), applied at three points:

| Layer | Applies to | How |
|---|---|---|
| **Commit** (mandatory) | every agent and human | [templates/agent/pre-commit](templates/agent/pre-commit) → `scripts/guard.py --staged`, installed with `git config core.hooksPath .githooks`. Refuses legacy files, HFSQL data files, backups, `.env*` (except `.env.example`), modified or deleted committed migrations, destructive SQL in new migrations, secret-like content |
| **Before each tool call** (where supported) | agents with pre-tool hooks | Claude Code: [templates/claude/settings.json](templates/claude/settings.json) → `scripts/guard.py --hook`. Other agents: call `--command "<cmd>"` or `--write <path>` (content on stdin) from their hook or wrapper; exit 2 means blocked. Also blocks force-push, `git add -A`, `commit -a`, `--no-verify`, edits to legacy and generated folders |
| **CI** (backstop) | everything pushed | `npm run verify` + parity gate; branch protection on `main` |

Pair the guard with the agent's own sandbox and approval settings (workspace-only writes, network off unless needed). Adjust the path constants at the top of `guard.py` to the accepted layout.

> Guard and agent configuration files are owned by **the human**: agents are told not to modify them (and some agents protect their own configuration from self-modification). Change them from your clone and push.

## Claude Code, Codex and other agents

The rules live in `AGENTS.md`, skills are Markdown files, guardrails run in Git and CI — so the method works with any coding agent. Install once per application repository:

```sh
cp -R templates/agent/skills skills && cp templates/agent/guard.py scripts/guard.py
mkdir -p .githooks && cp templates/agent/pre-commit .githooks/ && git config core.hooksPath .githooks   # every clone
# Claude Code only
cp templates/CLAUDE.template.md CLAUDE.md && mkdir -p .claude
cp templates/claude/settings.json .claude/ && cp -R skills .claude/skills
```

- **Codex** reads `AGENTS.md` (and nested ones) natively. If your version supports skills or hooks, point them at `skills/` and `scripts/guard.py --command/--write`; otherwise the commit guard, its sandbox/approval modes and CI cover it.
- **No sub-agents?** Run the mapping units as parallel sessions or one after another.
- **Two agents** work well together: one implements, the other reviews with `skills/review/SKILL.md` — a different model catches different misses.

