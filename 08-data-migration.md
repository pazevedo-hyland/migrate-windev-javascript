# 08 — HFSQL data migration

## Select a target from deployment needs

Use SQLite for a local database owned by one installed application, subject to actual write concurrency and data volume. Use a backend API with PostgreSQL for shared multi-workstation data. Classic HFSQL files can also be shared across a network, so their presence alone is not a SQLite recommendation.

Tauri offers an [SQL plugin](https://v2.tauri.app/plugin/sql/); this playbook instead recommends narrow Rust commands where a business operation must enforce validation and atomic multi-table writes. Whichever adapter is chosen, designate one migration owner and never apply competing migration histories.

## Schema inspection is not data extraction

XDD contains raw schema metadata, not customer records. The inspection tool preserves numeric WINDEV type/key codes without inventing TypeScript or SQL meanings. Resolve them against the applicable WINDEV documentation and actual exports. Review relationships, unique constraints, defaults and null behavior explicitly before writing a target schema.

Read `.fic`/`.ndx`/`.mmo` through supported HFSQL/WINDEV export tooling. Export explicit columns to CSV/JSON with a manifest recording source version, export time, encoding, decimal format, timezone/date rules and table counts. Preserve memo/blob data separately with checksums. Binary query definitions need SQL and parameter exports.

## Transformation checklist

- Preserve identifiers and foreign keys; represent 64-bit identifiers as decimal strings across JSON/TypeScript boundaries when needed.
- Use integer minor units or a deliberate decimal representation for money. Define rounding points, VAT/discount ordering and handling of negative amounts.
- Distinguish empty strings, nulls, zero and sentinel dates; do not normalize away meaning silently.
- Preserve leading-zero codes, accented text, case/collation behavior, timestamps and duration units.
- Identify duplicate records, orphan links and existing invalid values; quarantine and report them.
- Do not copy unknown legacy password formats into a new authentication scheme; define a reset or supported rehash path if needed.

## Import and reconciliation

Implement a dry run and repeatable import with explicit mappings and transaction boundaries. Import into a fresh isolated target, retain an old-to-new ID map if IDs change, validate references and enable SQLite foreign keys on each connection. Test failures, interruption and retry; do not silently replace existing rows.

Reconcile counts, keys, material quantities, balances, labor durations and report totals. Store a machine-readable reconciliation report plus approved exceptions. Test backup restoration with the selected database's supported tooling; copying an active database file without handling its journal is insufficient.

## Cutover

Rehearse on a copy. Schedule a write freeze, take a verified final backup/export, import, reconcile and perform acceptance tests. Define rollback triggers and who can authorize reopening writes. Once new-system writes begin, switching back requires a reconciliation strategy; restoring the old executable alone cannot restore data parity.
