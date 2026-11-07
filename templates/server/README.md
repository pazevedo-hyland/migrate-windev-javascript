# Server add-on (optional): procedure server, PostgreSQL/PGlite, HFSQL data import

The UI starter does not choose a server topology. This add-on is one accepted answer, taken from a finished migration
(WINDEV 28, HFSQL Client/Server shared by back-office PCs and shop-floor stations): business rules run as **named
procedures** on a Node server, one transaction per call, against **PostgreSQL** — or an embedded **PGlite** folder (the
same PostgreSQL compiled to WASM, nothing to install). The same procedures run unchanged in the browser on an
in-memory PGlite for the preview, the UI checks and unit tests. It also brings the **data import**: HFSQL export →
conversion with quarantine → reconciliation against the export's counts → apply, refusing to promote a database when
anything is quarantined or a count disagrees.

## When to choose it

Choose it at framing, in the topology ADR ([03](../../03-scope-and-architecture.md), [08](../../08-data-migration.md)), when:

- several stations share the data today (HFSQL Client/Server, or Classic files on a network share with concurrent writers) → server + PostgreSQL;
- one PC owns the data but you want the same code path as a future shared install → the server bound to `127.0.0.1` on embedded PGlite.

Do not adopt it when the accepted topology is SQLite in the Rust core (one installed application owns the data), or
when the project already has another API stack. Adopting it is a data-structure decision: record it in an ADR first.

## What is in it

Paths are where the files land in an app created by `scripts/create_project.py`.

| Path | What it reproduces / does |
|---|---|
| `src/backend/rpc.ts` | Procedure registry (`register`, `dispatch`), `UserError` with kinds `info` (Info), `error` (Error), `fatal` (unexpected); `Session`, `Settings`; optional start-up procedure `app.init` (`initialize`) — the project initialization code |
| `src/backend/db.ts` | `Queryable` / `Db` port; wire values: numeric → exact string, date `YYYY-MM-DD`, time `HH:MM:SS[.mmm]`, timestamp `YYYY-MM-DDTHH:MM:SS[.mmm]`, bigint → number (refused above 2^53) |
| `src/backend/pglite-db.ts`, `server/pg-db.ts` | PGlite and PostgreSQL adapters with identical value conversions |
| `src/backend/catalogue.ts`, `schema.ts` | Run-time catalogue of tables/columns (the role of the WINDEV analysis); installed before any procedure module loads |
| `src/backend/tables.ts` | `seek` = HReadSeekFirst, `list` (+ `startsWith` = generic HReadSeek), `count` = HNbRec, `insert` = HAdd (column defaults), `update` = HModify, `remove` = HDelete, `updateWhere`/`removeWhere`, `nextNumber` = MAX+1. Only catalogue identifiers; values always bound parameters |
| `src/backend/crud.ts` | `defineCrud`: the Form/Table window pattern (`<name>.list/.get/.save/.delete`): rights hook, empty key, key rules, existing key, validation, WINDEV duplicate error, pre-delete guards, dependent-record guards, delete confirmation, deleted-meanwhile handling. Every text is a parameter |
| `src/backend/migrate.ts`, `migrations.ts` | Ordered, immutable SQL migrations (`server/migrations/*.sql`), one transaction each, bundled by Vite for browser and server |
| `src/backend/seed.ts`, `seeds/` | Synthetic demo data per feature family (preview, tests, `APP_DEV_SEED=1`) |
| `src/backend/local.ts` | `createLocalBackend`: real procedures on in-memory PGlite (preview, UI checks, procedure tests) |
| `src/backend/procedures/` | One module per feature family; `system.migrations` as an independent reader |
| `src/infrastructure/backend.ts` | Client: `httpTransport(serverUrl)` (`POST /rpc`) or `previewTransport()`, `call()` throwing `BackendError(kind)` |
| `server/main.ts` | HTTP server: `POST /rpc`, `GET /health`, stdio control (`READY` / `FAILED <reason>`, clean stop at stdin EOF) |
| `server/build.mjs` | Vite SSR build of `main` + `setup` into `dist-server/` (`--self-contained` bundles every dependency except PGlite) |
| `server/setup-core.ts`, `server/setup.ts` | First-run setup CLI on a new staging database: `empty` or `import` from an HFSQL JSONL export; `RESULT <json>` line; exit 0 only when promotable |
| `tools/import.ts` | Import from `data.sqlite` + `manifest.json` (`scripts/windows/export_odbc.py`): conversion, quarantine, reconciliation report, dry run / apply |
| `tools/hfsql-jsonl.ts` | Node twin of `scripts/windows/hfsql_jsonl.py` (ANSI exporter output → importer input), so an installer needs no Python |
| `tools/pg_schema.py` | Schema v1 (`server/migrations/0001_schema_v1.sql`) + catalogue (`src/shared/schema.generated.ts`) from the schema draft |
| `src/backend/testing/` | Example schema (and the draft it was generated from) for the add-on's own tests |
| `tsconfig.server.json` | Type checking of server, backend and tools (Node + Vite types) |

## Adopt it

1. Copy everything in this folder **except this README** into the app root (it adds files only; nothing in the starter is overwritten).
2. Add the dependencies, pinned as in the migration they come from:

   ```sh
   npm install --save-exact @electric-sql/pglite@0.5.10 pg@8.16.3
   npm install --save-exact --save-dev @types/pg@8.15.5
   ```

   For decimal arithmetic on the exact strings add a decimal library (that migration used `decimal.js@10.6.0`); never `Number()` money.
3. `package.json` scripts:

   ```json
   "typecheck": "tsc --noEmit && tsc --noEmit -p tsconfig.tools.json && tsc --noEmit -p tsconfig.server.json",
   "server:build": "node server/build.mjs",
   "server": "node dist-server/main.js",
   "dev:server": "npm run server:build && node dist-server/main.js",
   "flows:server": "playwright test -c ui-check/server/server.config.ts",
   "import:dry-run": "tsx tools/import.ts --export <export folder>"
   ```

4. `vitest.config.ts`: add `"server/**/*.test.ts", "tools/**/*.test.ts"` to `include`. `vite.config.ts`: `optimizeDeps: { exclude: ["@electric-sql/pglite"] }` (PGlite ships WASM and data files Vite must not pre-bundle). `.gitignore`: `/dist-server/`, `/app-data/`.
5. Generate the schema: `scripts/schema_draft.py <inspect> --dossier <dossier> --out docs/schema/schema-draft.md` (writes the `.json` too), decide every listed item in the database ADR, then `py -3.12 tools/pg_schema.py --draft docs/schema/schema-draft.json`. It refuses to overwrite an existing migration (pass `--overwrite` only while it was never committed) and refuses names that are SQL reserved words.
6. Wire the client at start-up: `configureBackend(httpTransport(url), "server")` when a server URL is configured (`?server=` in tests), else `configureBackend(await previewTransport(), "preview")` with a visible preview banner.
7. Write procedures in `src/backend/procedures/<family>.ts` and import them from `procedures/index.ts`. Every write opens one `ctx.db.transaction(tx => …)` and passes `tx` to every helper; messages are the legacy texts from the evidence, never invented.
8. For real-server flows, copy [`ui-check/server-*.example.ts`](../ui-check/server-fixtures.example.ts) and `warmup.ts` into `ui-check/server/` and adapt `TEST_SESSION`, `open` and `login` to the app.

## Configuration (environment only; no credentials in Git)

| Variable | Use |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string; unset = embedded PGlite |
| `APP_DATA_DIR` | PGlite folder (default `./app-data`) |
| `PORT` | default 4900 (the HFSQL Client/Server default port; change it when both run on one host) |
| `APP_HOST` | listening address; `127.0.0.1` for a single-PC server |
| `APP_CORS_ORIGIN` | default `*`; set the app's origin outside a trusted LAN |
| `APP_DEV_SEED=1` | seed demo data into a database this start created (tests and demos only) |
| `APP_STDIO_CONTROL=1` | `READY` / `FAILED <reason>` on stdout, stop at stdin EOF (launchers, test fixtures) |
| `APP_*` | every `APP_` variable reaches procedures as `ctx.settings` (and the setup CLI's start-up procedure) |
| `APP_TEST_DATABASE_URL` | tests only: admin connection to a PostgreSQL where each worker creates and drops its database |

The session travels in the request body and is **asserted by the client**: as long as that is so, keep the server on a trusted network, and add authentication (and authorization in every procedure) before exposing it further.

## Data import

```sh
py scripts\windows\export_odbc.py --dsn MigrationCopy --out C:\migration\data      # on Windows, from a COPY
npx tsx tools/import.ts --export C:\migration\data --report docs/data/reconciliation.md    # dry run: nothing written
npx tsx tools/import.ts --export C:\migration\data --apply --db C:\migration\staging-db    # into a new database
```

Conversions by catalogue kind: `""`/`00000000` dates and times → NULL (counted); exact decimal text; `1/true/-1` and `0/false` booleans; HFSQL durations (ms, `H:MM:SS`, `D days, H:MM:SS.ffffff`) → integer milliseconds; WINDEV `YYYYMMDD[HHMMSS[mmm]]` and ISO dates; binary memos as `bytea`. A value that does not convert (`1,5`, 30 February, sub-millisecond, integer above 2^53…) **quarantines its row** with table, row, column, value and reason; a row the database refuses (unique clash) is quarantined with the database's reason. `--apply` imports one transaction per table, refuses tables that already hold rows, and restarts identity sequences after imported automatic identifiers. `setupImport` (installers, via `server/setup.ts`) chains JSONL conversion → dry run → apply → per-table `count(*)` check → start-up procedure, and reports `ok: false` (exit 3) on any quarantine, unknown table with rows, or rows read ≠ `COUNT(*)` ≠ imported: the caller then discards the staging database. `renumberUnique` is an opt-in repair rule for duplicated unreferenced unique ids; adopt it only by ADR, and every renumbering is listed in the report.

## Test layers it enables

1. **Unit, add-on** (`src/backend/*.test.ts`, `tools/import.test.ts`, `server/setup-core.test.ts`): example schema on in-memory PGlite, independent of the app's schema and procedures (`testing/example-backend.ts`).
2. **Procedure tests of the app**: `createLocalBackend({ seed: [...] })` — the real migrations, seeds and procedures, no server.
3. **Browser preview flows**: the UI on the in-browser PGlite (fast, no server process).
4. **Real-server flows** (`ui-check/server/`): Chrome → HTTP `/rpc` → the built `dist-server/main.js` → a fresh database per worker (PGlite locally, PostgreSQL with `APP_TEST_DATABASE_URL` in CI). Few tests: they prove the layers between UI and database persist.
5. **Setup CLI**: `node dist-server/setup.js empty|import …` exit code and `RESULT` line, as an installer runs it.

None of these establishes legacy parity on its own; parity rows still need their evidence.

## Lessons carried in the code

- **PGlite runs one transaction at a time.** A shared "already in a transaction" flag let a concurrent request's transaction run without one (its writes survived its own failure). Here each `transaction` call is its own; nested work receives `tx` (`tx.transaction` reuses it). Inside a transaction never call the outer `db`: on PGlite it waits forever.
- **ES modules evaluate imports before the importing body**: the catalogue is installed by `schema.ts`, imported first, or `defineCrud` checks tables against an empty catalogue.
- **Imported automatic identifiers** need the identity sequence moved past them, or the first new HAdd collides.
- **Text order**: HFSQL keys sort case-insensitively; a PostgreSQL database with the `C` collation sorts every capital first. Decide the collation in the ADR (e.g. a migration that sets text columns to `COLLATE "und-x-icu"`, keeping exact equality) and test a list order against the legacy app.
- **MAX+1 numbering** in one transaction is still racy across stations: keep a unique index (and retry) or lock, by ADR.
