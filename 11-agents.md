# 11 — Using Claude Code, Codex or another agent

The method is agent-neutral: everything that matters lives in **plain files in the repository** and in **deterministic scripts**, not in one tool's features. Agent-specific files are thin adapters over the same rules, so you can switch tools, or use two, without changing the method.

## What every agent uses

| Need | Agent-neutral mechanism |
|---|---|
| Instructions | `AGENTS.md` at the root + local `AGENTS.md` in sensitive folders |
| Reusable workflows | `skills/<name>/SKILL.md` — plain Markdown, named in `AGENTS.md` |
| Prompts | `templates/PromptInit.md`, `mapping-prompt.md`, `prompt-stage.md` — pasted or passed on the command line |
| Memory between sessions | `docs/runbooks/handoff.md`, `ROADMAP.md`, `docs/parity/parity.csv`, ADRs, Git history |
| Guardrails | `scripts/guard.py --staged` as a Git pre-commit hook; CI with `npm run verify` and the parity gate; branch protection |
| Progress | `scripts/status.py`, `scripts/parity_check.py` |
| Truth about green/red | Tests, golden scenarios and CI — never an agent's statement |

## Adapters per agent

Verify the details against your agent's current documentation; these tools evolve quickly.

| Capability | Claude Code | Codex | Any other agent |
|---|---|---|---|
| Root instructions | `CLAUDE.md` containing `@AGENTS.md` ([template](templates/CLAUDE.template.md)) | Reads `AGENTS.md` natively | Point its instructions file at `AGENTS.md`, or paste it |
| Local instructions | Add `CLAUDE.md` with `@AGENTS.md` next to each local `AGENTS.md` | Reads nested `AGENTS.md` (closer files take precedence) | Mention the local files in the root `AGENTS.md` |
| Skills | Copy or link `skills/*` into `.claude/skills/`; invoke `/review`, `/map-element` | If your version supports skills, place the same `SKILL.md` folders where it loads them; otherwise `AGENTS.md` tells it which file to follow | `AGENTS.md`: "to review, follow `skills/review/SKILL.md`" |
| Pre-tool guard | `.claude/settings.json` hook → `scripts/guard.py --hook` ([template](templates/claude/settings.json)) | If your version offers hooks, call `scripts/guard.py --command`/`--write`; otherwise rely on its sandbox/approval modes + the commit guard | Same as Codex |
| Commit guard | `.githooks/pre-commit` (same for all) | same | same |
| Parallel mapping | Sub-agents in one session | Several sessions in parallel (one unit each), or sequential units | Several sessions or sequential |
| Non-interactive runs (CI, nightly) | `claude -p "<prompt>"` | `codex exec "<prompt>"` | Its CLI/API |
| Sandbox | Permission rules in `.claude/settings.json` | Sandbox and approval modes | Container or VM ([00 §D](00-prerequisites.md#d-an-isolated-machine-for-the-coding-agent)) |

### Installing the adapters in an application repository

```sh
# all agents
cp -R templates/agent/skills skills
cp templates/agent/guard.py scripts/guard.py
mkdir -p .githooks && cp templates/agent/pre-commit .githooks/ && chmod +x .githooks/pre-commit
git config core.hooksPath .githooks          # each clone, each machine

# Claude Code
cp templates/CLAUDE.template.md CLAUDE.md
mkdir -p .claude && cp templates/claude/settings.json .claude/settings.json
cp -R skills .claude/skills                   # or symlink, if your setup follows symlinks
```

Agents rarely configure hooks themselves; the human installs them. Re-run `git config core.hooksPath .githooks` on every new clone, including the agent's machine and the test machine. CI still enforces the rules for anything that slips past a local hook.

## Using two agents together

The planner/implementer split ([01](01-principles-and-roles.md#the-roles)) works across tools, and **cross-model review is a strength**: a second model catches what the first one reads past. For example:

- implementer: Claude Code; reviewer: Codex with `skills/review/SKILL.md` — or the reverse;
- mapping split across tools: one tool maps windows, the other cross-reviews the notes.

Rules when mixing:

- one agent writes to a branch at a time; the other reads it;
- both read the same `AGENTS.md`, handoff and ADRs — never tool-specific copies of the rules;
- the handoff records which agent produced the stage.

## Prompting differences that matter

- Give every agent **file paths**, not summaries: "follow `skills/map-element/SKILL.md` for `legacy/code/WIN_Order.wdw`".
- Keep each session to **one slice**; start fresh from the handoff. Long sessions drift on every tool.
- Ask for the **exact commands run and their output** in the handoff; do not accept "tests pass".
- When an agent says a guard blocked it, that is the system working: decide as the human, do not ask the agent to work around it.
