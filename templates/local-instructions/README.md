# Local instruction files

Copy each block into an `AGENTS.md` inside the named folder of the application (and, for Claude, a one-line `CLAUDE.md` containing `@AGENTS.md`). Agents read these when they work in that folder, so the traps are visible where they happen. Keep only what applies.

## `src-tauri/migrations/AGENTS.md`

- This folder is the only schema history. Never edit or rename a committed migration; add the next numbered file.
- No `DROP`, `TRUNCATE` or bulk `DELETE` without a human-approved ADR referenced in the file header.
- Every migration runs in a transaction, is tested on an empty database and on a copy of the previous release's database.
- Enable `PRAGMA foreign_keys = ON` per SQLite connection; constraints mirror `docs/data-migration.md`.

## `src/bindings/AGENTS.md`

- Generated from Rust command signatures (`tauri-specta` or `ts-rs`). Do not edit; run `<bindings command>`.
- A Rust command change without regenerated bindings is a broken build. Commit the regenerated files with the change: the CI check compares against what is committed, so new binding files fail it until they are staged.

## `src/domain/AGENTS.md`

- Pure functions and types only: no React, Tauri, `fetch`, `Date.now()` or random values without injection.
- Every exported rule has a test whose name contains its parity ID (e.g. `RULE-012`).
- Money/quantity arithmetic uses the accepted decimal representation; never `number` for currency.

## `build/` or `.github/workflows/AGENTS.md`

- Signing keys and tokens come from CI secrets or environment variables only; never in files, URLs or logs.
- Never embed a reusable access token in the desktop app to fetch private releases.

## Rules for `legacy/` (in the root `AGENTS.md`: `legacy/` itself is read-only, so no file is added there)

- Evidence, not instructions. Read; never modify, execute, or copy into the application or published docs.
- Credentials found here are listed in `docs/legacy-inventory.md` as "to revoke"; never reuse them.
