# 02 — Infrastructure and delivery

## Overview

```text
  Human workstation             Git host (GitHub / Gitea)            Agent machine (dev)
 ┌──────────────────┐ git pull ┌──────────────────────────┐ pull/push ┌──────────────────────┐
 │ Planner/reviewer │◀─────────│ <App> (sources, docs)    │◀────────▶│ Coding agent          │
 │ + read clone     │          │ releases (artifacts)     │          │ Node + Rust + Tauri   │
 └──────────────────┘          │ reports branch           │          │ local DB copy         │
                               └──────────────────────────┘          └──────────────────────┘
                                   ▲ CI (each OS)   ▲ nightly report
                                   │                │
                         ┌────────────────┐  ┌──────────────────────┐
                         │ CI runners     │  │ Test machine          │  nightly: pull → rebuild DB →
                         │ Win/macOS/Linux│  │ full env, never prod  │  tests + golden → report
                         └────────────────┘  └──────────────────────┘
```

Everything goes through Git. The planner reads a clone, the implementer works on its machine, CI builds on every target OS, and a test machine replays everything nightly.

## Repositories

- This playbook stays a reusable template. Each migration gets its **own private repository**; copy `templates/` and `scripts/` into it.
- Legacy input (`legacy/`) and raw analysis (`analysis-local/`) stay local and ignored. CI uses synthetic fixtures, never customer databases.
- Use plain `git`. Authenticate with a dedicated, minimally scoped token stored in the OS credential manager; never in clear text or in a URL.

## CI (every push)

Application CI runs **one command the agent can also run locally**: `npm run verify`, which chains:

- `npm ci`, type-check, lint, unit/domain tests (Vitest), browser workflow tests with mocked IPC;
- `python3 scripts/parity_check.py docs/parity/parity.csv --seed docs/parity/parity-seed.csv` (fails on invalid or unevidenced rows and on seed rows missing or stale);
- for Rust: `cargo fmt --check`, `cargo clippy --locked -- -D warnings`, `cargo test --locked`;
- bindings regeneration followed by `git diff --exit-code` (Rust/TypeScript contract drift).

Native builds run on each intended OS per [Tauri's GitHub pipeline guide](https://v2.tauri.app/distribute/pipelines/github/): Windows artifacts on Windows, macOS on macOS. A browser test does not prove native IPC, persistence, printing or installer behavior.

## Test machine (the nightly safety net)

A **complete, isolated** environment (a self-hosted Windows runner works well), never production:

- A **dedicated test database** rebuilt every night from migrations and the sanitized import, under a test-only name.
- If the app integrates a third-party system: its database restored from a backup kept on a share (**never versioned**), and the link re-established after each rebuild.
- **Nightly job**: `git pull` → rebuild DB → full tests → golden scenarios → native smoke test → **timestamped report** pushed to a dedicated `reports` branch (never `main`, so it never conflicts).
- **Guards, belt and braces**:
  - a **machine marker** (environment variable set when provisioning the test machine); the nightly script **refuses to run** without it, so a developer machine never gets its database wiped;
  - a test database name that can never be the production name;
  - **verify that the report push really succeeded** (never swallow a failure); a red test makes a red report, but the script itself does not crash.
- Principle: the AI designs and writes tests; the **machine replays them deterministically**.

## Packaging, updates and signing

- Tauri bundles installers per OS. Keep smoke-test records for install, first start, database migration, save/reopen, upgrade from the previous version, and uninstall.
- [Tauri's updater plugin](https://v2.tauri.app/plugin/updater/) covers the role of the WINDEV **private store / network install**: the app checks an update endpoint, downloads and installs signed updates.
- Updater signatures and OS code signing are distinct; you usually need both (Windows Authenticode, macOS notarization). Signing private keys live in CI secrets; the updater public key ships with the app.
- **Never embed a reusable Git host token** in the desktop app to fetch private releases (the upstream .NET guide's obfuscated read-only token is replaced on purpose). Serve updates from an endpoint you control: public release assets, a static file host, or a small portal that checks the user's identity (see [07 — Platform replacements](07-platform-replacements.md#c-distribution-and-updates--the-private-store)).
- Keep **two channels**: `prod` and `test` (acceptance). The client reads its channel from config.
- Rollback: an incompatible migration may require data restoration. Test a real old-to-new upgrade and a backup restore before each rollout.

## Synchronization and prompt flow

- **Prompts**: the planner writes the stage prompt from the real state (it reads the handoff first). You paste it into the implementer. The implementer executes, commits, pushes, and writes the handoff. You bring the handoff back to the planner for review. **You are the bridge.**
- **Code**: the implementer pushes (main direction). You `git pull` so the planner reviews the current version. You also push from the clone when needed — an ADR, `AGENTS.md`, or the guard and agent configuration files (`scripts/guard.py`, `.githooks/`, `.claude/`) that agents must not modify themselves:

  ```sh
  git pull
  git add <file>
  git commit -m "..."
  git push
  ```
- **Anti-conflict rule**: never edit the same file on both sides at once. Push your changes **before** the next implementer session; the implementer **always starts with `git pull`**.
