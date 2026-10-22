# 01 — Principles and roles

## The roles

| | Planner / reviewer ("the brain") | Implementer ("the hands") | Human ("the pilot") |
|---|---|---|---|
| Where | Planning session (e.g. Claude chat/Cowork) with a read clone of the repository | Coding agent (e.g. Claude Code) in the working repository, on its isolated machine | Your workstation |
| Does | Architecture, slicing, **writes stage prompts**, **reviews** results, keeps roadmap and memory | **Executes**: code, SQL, tests, commits, pushes, **writes the handoff** | **Validates** each stage, **decides**, bridges the two (pastes prompts, `git pull`) |
| Does not | Write production code | Decide the architecture alone | Delegate decisions on scope or deliberate behavior changes |

One agent may play both AI roles in **separate passes** (plan, then implement, then review with fresh context). What matters is the separation of concerns, not the number of tools. The human always stays in control.

## The golden rule

> **The prompt is temporary; the structure is permanent.**

A good prompt improves one task. A good information structure (`AGENTS.md`, `docs/`, ADRs, runbooks, skills, hooks, the parity matrix) improves **every** session. Invest in structure, not giant prompts.

## Non-negotiables

1. **One decision = one ADR** in `docs/decisions/` (context → decision → consequences). Otherwise it gets lost and re-debated.
2. **One handoff per stage** in `docs/runbooks/handoff.md`: the entry point of the next session.
3. **The repository, the legacy sources and the database are the truth.** Verify, never assume. Read the handoff and the real repository state before writing a stage prompt; inspect the real schema before writing SQL; read the real library API before calling it.
4. **Evidence labels.** Every inferred rule is *verified*, *inferred* or *unresolved*, with `path:line` or export reference. A UI label is not a requirement; a schema is not the data; a successful build is not parity.
5. **Parity is the definition of done.** Legacy behavior is preserved unless a recorded decision changes it. Every behavior has a row in `docs/parity/parity.csv` that ends *verified* (by a test that ran) or *excluded* (by an ADR).
6. **No secret in Git.** Licences, connection strings, tokens → ignored local config or environment variables.
7. **Single source of truth.** One migration history for the schema; one home per business rule; details in `docs/`, not in an overloaded `AGENTS.md`.
8. **Separate development and test.** The test machine never touches production; explicit guards enforce it.
9. **The machine judges.** AI designs and writes tests; deterministic tools replay them. Never let an AI decide green or red.

## The mindset

- **Frame before coding**: inventory the legacy application, map it completely, validate the target schema and architecture — as you would without AI, only much faster.
- **Short, ordered, tested stages**, each closed by a handoff.
- **Systematic review** in four categories: (1) blocking, (2) parity gap, (3) naming/convention, (4) business/cosmetic. Accepted choices are not reopened without new evidence.
- **Real data early**: without representative data, nothing can be validated. *How* you get it is a framing question.
- **Visual decisions are validated by the human** from screenshots, with a fallback planned.
- **Honest self-criticism** ("I could not run this check") is worth gold: it directs the review.
- Routine reversible work proceeds within the agreed scope; data deletion, schema changes and cutover need an explicit, approved plan.
