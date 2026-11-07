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

- A **dedicated test database** rebuilt every night from migrations and the data import, under a test-only name.
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

### Windows installer for a Node/TypeScript server + Tauri app

Pattern from a finished migration (procedure server in Node/TypeScript with an embedded database, Tauri 2 client, one PC). Record it in an ADR; adapt names and paths.

- **One NSIS setup from the Tauri bundler**, per-user install (no admin rights), WebView2 bootstrapper embedded. Its resources hold a `runtime\` folder: `node.exe` (the build machine's Node version, with its licence), the server and a setup CLI each bundled into one file, the embedded database package beside them, the data-export scripts, and a SHA-256 manifest. The packaging script refuses private files (`.env`, `.fic/.ndx/.mmo`, `.wdd`, `.sqlite`, database folders, local config) and smoke-tests the runtime from outside the checkout.
- **The app starts the bundled server as a child process** when no server address is configured and `runtime\` exists: listening on `127.0.0.1` only, database in `%LOCALAPPDATA%\<App>\data` (outside the install folder, kept on uninstall). Startup protocol on stdout: `READY` or `FAILED <reason>`; end of stdin = clean shutdown; a Windows job object kills the server if the app dies. A port already taken fails closed with a message. Release builds load the bundled UI, never the dev URL.
- **First-run wizard** when the database folder does not exist: import the legacy data (folder picker; HFSQL export as in [Windows export](scripts/windows/README.md#when-export_odbcpy-crashes-the-ansi-exporter-hfsql-28) → import dry run → apply → per-table count check) or start empty (administrator with a password shown once). Everything happens in a `staging-*` folder; the database is promoted by **one rename** only when nothing was quarantined and every count agrees, otherwise nothing is activated and the problems are shown. An existing database is never replaced or re-imported; the import report is kept and the staging copy of business data deleted.
- **Headless equivalent** of the wizard for support and tests: `<app>.exe --import-legacy <folder> --yes` / `--init-empty --yes`, same code path, a `RESULT {json}` line and distinct exit codes. It made the real 30-table import (24,915 rows, 33 s) testable without clicking.
- **Security**: while the server trusts the session the client sends (legacy-style login, no real authentication), it must listen on `127.0.0.1` only. Serving several PCs needs real authentication first (see [07 §B](07-platform-replacements.md#b-identity-oauth-and-rights)).
- **QA the installed app, not only the dev build**: WebView2 accepts Chromium flags from the environment, so start the installed app with `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9229` and drive it with Playwright's `chromium.connectOverCDP("http://127.0.0.1:9229")` (open every menu window, collect page errors and failed requests). This found a blank window that every dev-server test missed ([production-build smoke](10-parity-and-verification.md#5-native-and-platform-behavior)). Use it on a test machine only: the debugging port gives full control of the app.
- Not covered by that pattern: code signing, upgrades of an existing data folder between versions, backup/restore, several PCs.

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
