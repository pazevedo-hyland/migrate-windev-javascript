# 08 — HFSQL data migration

The guide does not choose your database for you: decide with evidence and record it in an ADR. HFSQL offers a lot "in the box"; first find **what your application really uses**, then see what the target provides natively and what must be rebuilt.

## First: which HFSQL?

- **HFSQL Classic** (`.fic`/`.ndx`/`.mmo`/`.ftx` files, local, network share or embedded). If one installed application owns the data → **SQLite** (embedded, one file, no server). If several workstations share the files over the network today → a **TypeScript API + PostgreSQL**: Classic files can be shared, so their presence alone is not a SQLite recommendation.
- **HFSQL Client/Server** (a TCP service, multi-user) → **PostgreSQL** behind a server API.

> Simple rule: **one machine owns the data → SQLite in the Rust core**; **several workstations share it → server API + PostgreSQL**. Check actual write concurrency and volume before deciding.

## Data access in the target

- Rust: [sqlx](https://github.com/launchbadge/sqlx) (SQLite and PostgreSQL with one API, built-in migrations) or `rusqlite` (synchronous SQLite). TypeScript server: a query builder such as Kysely or Drizzle.
- Tauri offers an [SQL plugin](https://v2.tauri.app/plugin/sql/) callable from JavaScript; this playbook recommends **narrow Rust commands** for business operations so validation and multi-table writes stay atomic ([03](03-scope-and-architecture.md#command-pattern-one-save--one-invoke--one-transaction)).
- Whichever adapter is chosen, designate **one migration owner** and never apply competing migration histories.

## What you get back, what must be rebuilt

✅ native · 🟧 extension/effort · ⚠️ to rebuild

| HFSQL feature | SQLite (local) | PostgreSQL (shared) | Status |
|---|---|---|---|
| SQL, indexes, **ACID transactions**, views | yes | yes | ✅ |
| **Referential integrity**, cascade delete | foreign keys — `PRAGMA foreign_keys = ON` **on every connection** | yes | ✅ / 🟧 |
| **Triggers** (server-side) | yes | yes | ✅ |
| **WLanguage triggers** (`HDescribeTrigger`, client-side procedures run before/after H functions) | application code in the command/use case | same | ⚠️ find them all |
| **Stored procedures** (WLanguage server procedures) | none: Rust/TypeScript service code | PL/pgSQL or service code | ⚠️ / ✅ |
| **Encryption at rest** (AES) | SQLCipher build of SQLite (e.g. rusqlite's SQLCipher feature) | disk/volume encryption, pgcrypto for columns | 🟧 |
| **Password item type** (native salted hash) | Argon2id in Rust | same | ⚠️ |
| **GDPR** (personal-data items + audit) | convention: personal-data column registry, export/erase use cases | same + column-level privileges | ⚠️ |
| **SDD** (automatic schema update of deployed data) | ordered migrations run at startup, after an automatic backup | migrations on deploy | 🟧 |
| **Journaling** (before/after images, dated restore) | audit tables via triggers | audit triggers, logical decoding; **PITR** for dated restore | 🟧 |
| **Scheduler** (tasks in the database) | OS scheduler ([07 §E](07-platform-replacements.md#e-scheduled-tasks-and-batch)) | pg_cron or a worker | 🟧 |
| **Replication / offline** | custom sync engine ([07 §F](07-platform-replacements.md#f-depending-on-your-profile--offlinemobile-real-time-database-admin)) | native replication between servers; offline = custom | 🟧 / ⚠️ |
| **Hot / differential backup** | online backup API or `VACUUM INTO` | pg_dump, pg_basebackup | ✅ |
| **Full-text search** | FTS5 | `tsvector` full-text | ✅ |
| "**SQL injection impossible**" | parameterized queries (discipline, not magic) | same | ✅ |
| **Append-only table** | triggers rejecting UPDATE/DELETE | same, or privileges | 🟧 |
| **Automatic identifier** (8-byte) | `INTEGER PRIMARY KEY`; strings across IPC above 2^53 | `bigint identity` | ✅ / 🟧 |
| **Currency / numeric items** | no decimal type: integer minor units or TEXT decimals | `numeric(p,s)` | 🟧 |
| **Key options** (case/accent sensitivity per index) | `NOCASE` folds **ASCII only**: accented keys need a normalized column or custom collation | ICU collations | 🟧 |
| **"Null supported"** per item | nullable columns | same | ✅ — but see transformation checklist |
| **Memo / binary memo** | TEXT/BLOB or external files with checksums | `text`/`bytea` | ✅ |
| **Record locks** (`HLockRecord`, lock modes) | optimistic version column checked in the update | row locks or optimistic version | 🟧 |
| Multi-OS, Unicode, ODBC/OLE DB | standard | standard | ✅ |

## Three points that deserve a real decision

- **Encryption.** If the HFSQL files are encrypted, plan the equivalent from the start (SQLCipher for SQLite, disk/column encryption for PostgreSQL) and decide where the key lives (OS keychain, not a file next to the database). Not something to discover at the end.
- **GDPR.** HFSQL's personal-data marking has no turnkey equivalent: rebuild it by **convention** (a registry of personal-data columns, export and erase use cases, log redaction) plus an inventory of personal data.
- **Schema updates.** SDD's automatic in-place update is replaced by **versioned migrations** run at startup after a backup: less magic, but traceable and replayable — in line with this guide.

## Schema inspection is not data extraction

XDD contains raw schema metadata, not customer records. The inspector keeps numeric WINDEV type/key codes raw instead of inventing SQL or TypeScript meanings. Name them with evidence, then draft:

```sh
python3 scripts/schema_draft.py <inspect dir> --dossier <dossier dir> --out docs/schema/schema-draft.md   # run by prepare_evidence.py
```

It pairs each XDD type code with the type name the dossier prints for the same item (a legend backed by WINDEV, as for events), takes structure, key type, size, default and null support from the XDD (complete, unlike PDF parsing), and writes a draft SQLite DDL (`.sql`, loadable as is) plus the **decisions** it cannot make for you: unsigned 64-bit integers, binary reals that may be money, exact decimals, WINDEV date/time text formats, memos, password items. A code the dossier never names stays `unresolved`. The draft is input for the database ADR; it declares no foreign keys unless the analysis has links — when it has none, relations live in code (`HReadSeek` on shared items) and the mapping notes must name them. Review key options (case/accent), relationships and null behavior before writing migrations.

With `--decoded` (the output of `windev_decode.py`, passed by `prepare_evidence.py`) the draft also reads the analysis file itself: captions, the digits of each decimal, and **how each text key compares**. On the second project all 51 text keys ignore case and accents, and 22 of them spaces and punctuation too — so a search finds `abc` for `ABC` and a unique key refuses the second: the target's unique indexes and lookups need the same folding, decided in the database ADR. A project with no `.xdd` gets the same draft from the analysis file alone (null support excepted).

Read `.fic`/`.ndx`/`.mmo` through supported HFSQL/WINDEV export tooling, or with the toolkit's own reader (below), on a copy. Export explicit columns to CSV/JSON with a **manifest**: source version, export time, encoding (often Windows-1252), delimiter, decimal format, timezone/date rules and table counts. Preserve memo/blob data separately with checksums. Binary query definitions need SQL and parameter exports.

For HFSQL Classic files the toolkit's route is ODBC on a copy: `scripts/windows/export_odbc.py` (pyodbc). When it crashes while connecting (exit code 139 / access violation — seen with the HFSQL 28 driver, whose Unicode ODBC entry points fail), use the ANSI exporter `scripts/windows/hfsql-export.ps1` (32-bit Windows PowerShell; hash-checked copy, temporary DSN always deleted, row counts checked per table) and convert its JSONL with `hfsql_jsonl.py` into the same `data.sqlite` + `manifest.json`. Measured on a real application: 30 tables, 24,915 rows, every count agreeing ([Windows export](scripts/windows/README.md#when-export_odbcpy-crashes-the-ansi-exporter-hfsql-28)).

**Without any driver**: `scripts/hfsql_read.py <copy of the data folder> --analysis <project>.ana/<project>.wda --out legacy/data` reads the `.fic` and `.mmo` files directly and writes the same `data.sqlite` + CSV + `manifest.json`, on any operating system. It takes the record layout from the analysis file and refuses what it cannot vouch for — a file that does not follow the analysis (not rebuilt after a change, compressed or encrypted) and item types it was not measured on are listed in the manifest, not guessed. Measured against the ODBC driver on the same data: 29 of 30 files, 24,896 rows, 224,567 values, all equal; the 30th file was refused (with `--fit-integers`, which reads an integer item the file still stores in a larger size and says so in the manifest, all 30 files and 24,915 rows equal the driver's). Where both routes are available, run both once and compare (`compare_exports.py`): two independent readers agreeing is stronger evidence than either alone. The format is described in [docs/windev-file-formats.md](docs/windev-file-formats.md#data-files-fic-and-mmo-without-a-driver).

## No analysis (.wdd)? Recover the data anyway

The HFSQL ODBC driver needs the analysis: without `Analyse=` it answers `[01S00] Unable to connect: insufficient connection string`, and none of its other keywords (`RepFic`, `Password`, `LISTANA`…) opens a `.fic` alone. Applications whose developers are gone often ship only the data files. In this order:

1. **Find the `.wdd` first** — next to the application's `.exe`, in an `<App>.ana\` folder, on old development PCs, in source control or backups. With it, the ODBC export ([scripts/windows](scripts/windows/README.md)) is the lossless path, with row counts checked. The project's analysis file (`<project>.ana/<project>.wda`) serves too: `hfsql_read.py` (above) reads the data with it and no driver.
2. **Otherwise export with WDMap.** Each `.fic` carries its own description, and PC SOFT's WDMap (shipped with WINDEV) opens a `.fic` directly and exports it to XML with the real column names. [`wdmap_export.ps1`](scripts/windows/README.md#wdmap-export-without-the-analysis) runs it on a hidden desktop, table after table, without touching the user's screen; [`wdmap_xml_to_sqlite.py`](scripts/README.md#wdmap_xml_to_sqlitepy--wdmap-xml-exports-to-one-sqlite-copy) loads the XML into one SQLite copy, every value as TEXT, with a manifest of rows and export status per table.
3. **Memos come from the `.mmo` files.** WDMap's XML holds text memos but **no binary memos** (images, PDFs, attachments). [`hfsql_mmo.py`](scripts/README.md#hfsql_mmopy--memo-files-read-directly) reads the memo files directly; their layout is plain and documented in [the HFSQL Classic format notes](docs/hfsql-classic-format.md). A binary memo is linked to its row by the pointer the `.fic` record holds, never by export position: WDMap's row order is not the physical order.
4. Profile the SQLite copy ([below](#profile-the-data-before-deciding-the-schema)) and write the schema from the data, the dossier and the code: without the analysis there are no declared types, sizes or keys to check against.

> **Licensing.** WDMap also ships with the free WINDEV Express and runs without activation, but the Express licence forbids commercial use. A migration done for a client or a business is commercial: use a licensed WINDEV, or check your licence before relying on Express.

On a real WINDEV 28 database with no analysis (689 tables): 257 tables with rows exported (about 910,700 rows), 431 empty tables reported as such (confirmed empty against the `.fic` record area) and 1 table exported by hand earlier, about 7 s per table with 4 workers in parallel; 233 memo files read with no error (about 514,000 text and 19,000 binary memos: PNG, JPEG, BMP, GIF, PDF and others). The table description inside the `.fic` is scrambled and was deliberately **not** decoded: WDMap provides names and types.

## Profile the data before deciding the schema

The analysis says what the data should be; only the data says what it is. On a copy — `data.sqlite` from `scripts/windows/export_odbc.py` (lossless: NULLs, bytes, counts checked), its CSV folder, `data.sqlite` from `scripts/wdmap_xml_to_sqlite.py` (no analysis: pass a schema file holding `{"tables": []}` and name links with `--ref`), or another SQLite staging file:

```sh
python3 scripts/data_profile.py legacy/data/data.sqlite --ref ordem.matricula=Viaturas.matricula   # → docs/data/profile.md
```

Per column: nulls, empty strings, distinct values, value shapes, lengths, values that do not parse as the WINDEV type, zeros, constant columns, stray spaces and line breaks; per unique key (composite ones rebuilt from their parts): duplicates; per link (columns named after a table or its identifier, plus `--ref`): orphans, with `0` counted as "no link". The report holds counts, shapes and extremes, not records: review and commit it; mapping rows and ADRs cite `export: docs/data/profile.md#<table>`. Run it again on every new export.

What it found on the real project (17 tables, 180,000 rows, 4 s) — expect the same kinds elsewhere:

- **Composite keys arrive as binary columns** the analysis does not list: rebuild them as composite indexes, never import their bytes.
- **Generated link columns can be unused**: `…ID` columns at 0 in every row while the real links run on codes (`Viaturas.Cliente → Clientes.Codigo`, not `ClientesID`). Link on what the values match, not on names.
- **Stored totals can be always 0**: four of five totals on the repair orders were never written — the app computes them. Do not trust a stored figure the profile shows constant; find the code that computes it.
- **0 means empty**: a year and a month at 0 in 99.6 % of vehicles. Map to NULL only if the dossier's "Blank if zero" or the code says so.
- **Empty is not NULL**: 13 % of payment dates are `""`, 95 % of a date-time are zero dates.
- **No relation is enforced**: 52 repair orders point to deleted vehicles, 54 material lines to deleted articles; and 2 automatic identifiers are duplicated. Quarantine or keep without the constraint — an ADR, not a silent fix.
- **Outliers**: a mileage of 964 million, a line price of 401 million where 99 % are under 377. Keep, flag, or quarantine.
- **Business reality**: 44 % of articles have negative stock — a check constraint would reject real data.
- Text read through ODBC was clean UTF-8 (no mojibake); memos use CR LF; thousands of descriptions carry trailing spaces (decide trim or keep: WLanguage compares strings including them unless the code trims).

Feed the findings into the database ADR, the import's quarantine rules, the mapping notes (a constant column is a behavior question) and the golden data (its shapes and edge cases).

## Transformation checklist

- Preserve identifiers and foreign keys; represent 64-bit identifiers as decimal strings across JSON/TypeScript boundaries when needed.
- Use integer minor units or a deliberate decimal representation for money (see [09](09-wlanguage-traps.md#numbers-and-money)). Define rounding points, VAT/discount ordering and handling of negative amounts.
- Distinguish empty strings, nulls, zero and sentinel dates (`00000000`, empty date); do not normalize away meaning silently.
- Preserve leading-zero codes, accented text, case/collation behavior, timestamps and duration units.
- Identify duplicate records, orphan links and existing invalid values; **quarantine and report** them.
- Do not copy unknown legacy password formats into a new authentication scheme; define a reset or supported rehash path.

## Import and reconciliation

Implement a **dry run** and a repeatable import with explicit mappings and transaction boundaries. Import into a fresh isolated target, retain an old-to-new ID map if IDs change, validate references, enable SQLite foreign keys on each connection. Test failure, interruption and retry; never silently replace existing rows.

Reconcile counts, keys, quantities, balances, labor durations and report totals with `scripts/compare_exports.py` (legacy export vs target export, declared normalizations only — see [templates/compare.example.json](templates/compare.example.json)). Store a machine-readable reconciliation report plus approved exceptions. Test backup restoration with the selected database's supported tooling; copying an active SQLite file without handling its journal/WAL is insufficient.

With the [server add-on](templates/server/README.md), `tools/import.ts` converts the ODBC export (`data.sqlite` + `manifest.json`) by column kind (empty dates → NULL, exact decimals as text, durations → ms, booleans), quarantines every row with a value that does not convert or that the database refuses, writes a reconciliation report (manifest rows / `COUNT(*)` / read / converted / quarantined / imported per table) and imports one transaction per table only with `--apply`. `server/setup.ts` chains the same steps on a new staging database and reports it promotable only when nothing is quarantined and every count agrees; repairs such as renumbering duplicated ids are opt-in rules recorded in an ADR and listed in the report.

Validate on a **real subset** (volume, types, encoding) before generalizing.

Duplicate values in a column the target makes unique are common (a legacy numbering race, two inserts seconds apart). Renumbering is acceptable **only for an explicit allow-list of unique id columns that no other table references**: later rows (source order) get `MAX + 1`, `+ 2`…, every row is kept and each change (table, column, old, new, source row) is listed in the import report. Any other refused row is quarantined and blocks activation; never renumber a referenced key. Record the allow-list in the import ADR as an assumption for the owner to confirm.

## Cutover

Rehearse on a copy. Schedule a write freeze, take a verified final backup/export, import, reconcile and run acceptance tests (golden scenarios). Define rollback triggers and who can authorize reopening writes. Once the new system receives writes, switching back requires a reconciliation strategy: restoring the old executable alone cannot restore data parity.

## Where to start

1. **Inspect what the application really uses**: triggers (including `HDescribeTrigger`), stored procedures, encryption, journaling, replication, locks, full-text, key options. Many apps use only a fraction.
2. Choose the family from the topology: one owner → SQLite; shared → PostgreSQL behind an API.
3. For each feature **really used**, find its row above and decide (native / extension / build). **Record the database choice in an ADR.**
4. Dry-run the import on the real data copy and reconcile before writing business features on top.

## Glossary

- **ACID**: atomicity, consistency, isolation, durability — the guarantees of a reliable transaction.
- **FK** (*Foreign Key*): integrity link between two tables.
- **FTS** (*Full-Text Search*).
- **PITR** (*Point-In-Time Recovery*): restore a database to a precise date/time.
- **SDD**: HFSQL's automatic schema synchronization of deployed data.
- **WAL** (*Write-Ahead Log*): SQLite/PostgreSQL journal that must be included in consistent backups.

## References

HFSQL [features](https://pcsoft.fr/hfsql/fonctionnalites.htm) · [security](https://pcsoft.fr/hfsql/securite.htm) · [GDPR with WINDEV](https://pcsoft.fr/pcsoft/rgpd-windev-vous-aide.htm) · [SQLite](https://www.sqlite.org/) · [SQLite foreign keys](https://www.sqlite.org/foreignkeys.html) · [SQLCipher](https://www.zetetic.net/sqlcipher/) · [PostgreSQL](https://www.postgresql.org/) · [sqlx](https://github.com/launchbadge/sqlx)
