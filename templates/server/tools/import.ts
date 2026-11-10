/**
 * Imports the HFSQL data into the new database from the playbook's export format (scripts/windows/export_odbc.py, or
 * tools/hfsql-jsonl.ts for the ANSI exporter): `data.sqlite` (every value as lossless text, NULL as NULL, bytes as BLOB)
 * + `manifest.json` (per table: rows read and the source's own COUNT(*)).
 *
 *   npx tsx tools/import.ts --export <export folder> [--report docs/data/reconciliation.md]        # dry run (default)
 *   npx tsx tools/import.ts --export <export folder> --apply --db <PGlite folder | postgres://…>   # import
 *   (--db may be omitted when DATABASE_URL is set; never write a connection string with a password in a script)
 *
 * Every value is converted by the column kind of the generated catalogue (src/shared/schema.generated.ts):
 * lower-case identifiers; "" / 00000000 dates → NULL; exact decimals as text; booleans; HFSQL durations → integer ms.
 * A row with a value that does not convert is quarantined (table, row, column, value, reason) and never imported.
 * `--apply` migrates the database, then imports one transaction per table and refuses tables that already hold rows.
 * Run the dry run first, read the reconciliation report, and promote the database only when nothing is quarantined
 * and every count agrees (server/setup-core.ts `importProblems`).
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import type { Catalogue, CatalogueColumn, ColumnKind } from "../src/backend/catalogue";
import type { Db, Queryable, SqlValue } from "../src/backend/db";
import { migrate, type Migration } from "../src/backend/migrate";
import { SCHEMA } from "../src/shared/schema.generated";

/** An import value: a SQL value, or bytes for a binary column (bound as bytea). */
type ImportValue = SqlValue | Uint8Array;
type ImportRow = Record<string, ImportValue>;
type Converted = { value: ImportValue | undefined; emptyDate?: boolean; nullDefault?: boolean };

export class ConversionError extends Error {}

const pad = (n: number | string, w = 2) => String(n).padStart(w, "0");
function realDate(y: number, m: number, d: number) {
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}
/** HFSQL's empty date / time / date-time ("" or all zeros, as the ODBC driver returns them). Counted in the report. */
const EMPTY_DATE = /^(|0+|0000-00-00(?:[T ]00:00(?::00(?:\.0+)?)?)?)$/;

/** Fraction of a second as exact milliseconds (HFSQL keeps ms; finer non-zero digits are not exact → error). */
function millis(fraction: string | undefined): string {
  const digits = (fraction ?? "").padEnd(3, "0");
  if (/[1-9]/.test(digits.slice(3))) throw new ConversionError("sub-millisecond precision");
  return digits.slice(0, 3);
}

/** Time: ISO "HH:MM[:SS[.fff]]" or WINDEV "HHMM[SS[CC]]" (CC = hundredths). */
function convertTime(text: string): string {
  const iso = /^(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?$/.exec(text);
  const legacy = /^(\d{2})(\d{2})(?:(\d{2})(\d{0,3}))?$/.exec(text);
  const m = iso ?? legacy;
  if (!m) throw new ConversionError("not a time");
  const [h, mi, s] = [Number(m[1]), Number(m[2]), Number(m[3] ?? 0)];
  if (h > 23 || mi > 59 || s > 59) throw new ConversionError("time out of range");
  const ms = iso ? millis(m[4]) : pad((m[4] ?? "").padEnd(2, "0").slice(0, 2), 2) + "0";
  return `${pad(h)}:${pad(mi)}:${pad(s)}.${ms}`;
}

/** Date: ISO "YYYY-MM-DD" or WINDEV "YYYYMMDD" (a midnight time part is accepted). */
function convertDate(text: string): string {
  const m = /^(\d{4})-?(\d{2})-?(\d{2})(?:[T ]00:00(?::00(?:\.0+)?)?)?$/.exec(text);
  if (!m || !realDate(Number(m[1]), Number(m[2]), Number(m[3]))) throw new ConversionError("not a date");
  return `${m[1]}-${m[2]}-${m[3]}`;
}

/** Date and Time: ISO "YYYY-MM-DD[ T]HH:MM[:SS[.fff]]" or WINDEV "YYYYMMDD[HHMMSS[mmm]]". */
function convertDateTime(text: string): string {
  const iso = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?$/.exec(text);
  const legacy = /^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2})(\d{2})(\d{0,3}))?$/.exec(text);
  const m = iso ?? legacy;
  if (!m || !realDate(Number(m[1]), Number(m[2]), Number(m[3]))) throw new ConversionError("not a date-time");
  const [h, mi, s] = [Number(m[4] ?? 0), Number(m[5] ?? 0), Number(m[6] ?? 0)];
  if (h > 23 || mi > 59 || s > 59) throw new ConversionError("time out of range");
  const ms = iso ? millis(m[7]) : (m[7] ?? "").padEnd(3, "0");
  return `${m[1]}-${m[2]}-${m[3]} ${pad(h)}:${pad(mi)}:${pad(s)}.${ms}`;
}

/** HFSQL Duration → integer ms: integer text (ms), Python timedelta text ("[-]D day[s], H:MM:SS[.ffffff]") or "[-]HH:MM:SS[.fff]". */
function convertDuration(text: string): number {
  if (/^-?\d+$/.test(text)) {
    const n = Number(text);
    if (!Number.isSafeInteger(n)) throw new ConversionError("duration above 2^53 ms");
    return n;
  }
  const m = /^(-)?(?:(-?\d+) days?, )?(\d+):(\d{2}):(\d{2})(?:\.(\d+))?$/.exec(text);
  if (!m) throw new ConversionError("not a duration");
  const ms = Number(millis(m[6]));
  const total = ((Number(m[2] ?? 0) * 24 + Number(m[3])) * 60 + Number(m[4])) * 60_000 + Number(m[5]) * 1000 + ms;
  return m[1] ? -total : total;
}

/** One value by its column kind. `value: undefined` = leave it to the column default (what HAdd writes). */
export function convertValue(kind: ColumnKind, raw: unknown): Converted {
  if (raw === null || raw === undefined) {
    return kind === "date" || kind === "datetime" || kind === "time" || kind === "binary"
      ? { value: null, emptyDate: kind !== "binary" }
      : { value: undefined, nullDefault: true };
  }
  if (raw instanceof Uint8Array) {
    if (kind === "binary") return { value: raw };
    throw new ConversionError("binary value in a non-binary column");
  }
  const text = String(raw);
  const t = text.trim();
  switch (kind) {
    case "text":
      return { value: text };
    case "integer":
    case "bigint": {
      if (t === "") return { value: undefined, nullDefault: true };
      if (!/^-?\d+(?:\.0+)?$/.test(t)) throw new ConversionError("not an integer");
      const n = Number(t.split(".")[0]);
      if (!Number.isSafeInteger(n)) throw new ConversionError("integer above 2^53");
      if (kind === "integer" && (n > 2_147_483_647 || n < -2_147_483_648)) throw new ConversionError("integer out of range");
      return { value: n };
    }
    case "real": {
      if (t === "") return { value: undefined, nullDefault: true };
      if (!/^-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$/.test(t)) throw new ConversionError("not a number");
      return { value: Number(t) };
    }
    case "decimal": {
      if (t === "") return { value: undefined, nullDefault: true };
      if (!/^-?\d+(?:\.\d+)?$/.test(t)) throw new ConversionError("not a decimal");
      return { value: t }; // exact text into a numeric column
    }
    case "boolean": {
      const b = t.toLowerCase();
      if (b === "") return { value: undefined, nullDefault: true };
      if (["1", "true", "-1"].includes(b)) return { value: true };
      if (["0", "false"].includes(b)) return { value: false };
      throw new ConversionError("not a boolean");
    }
    case "date":
      return EMPTY_DATE.test(t) ? { value: null, emptyDate: true } : { value: convertDate(t) };
    case "datetime":
      return EMPTY_DATE.test(t) ? { value: null, emptyDate: true } : { value: convertDateTime(t) };
    case "time":
      return EMPTY_DATE.test(t) ? { value: null, emptyDate: true } : { value: convertTime(t) };
    case "duration":
      return t === "" ? { value: undefined, nullDefault: true } : { value: convertDuration(t) };
    case "binary":
      throw new ConversionError("text in a binary column");
    default:
      throw new ConversionError(`unknown column kind ${String(kind)}`);
  }
}

export interface Quarantined {
  table: string;
  row: number;
  column: string;
  value: string;
  reason: string;
}
export interface TableReport {
  source: string;
  target: string | null;
  manifestRows: number | null;
  manifestCount: number | null;
  read: number;
  converted: number;
  quarantined: number;
  imported: number | null;
  emptyDates: number;
  nullDefaults: number;
  droppedColumns: string[];
  note?: string;
}
export interface Renumbered {
  table: string;
  column: string;
  oldValue: string;
  newValue: string;
  row: number;
}
export interface ImportResult {
  tables: TableReport[];
  quarantine: Quarantined[];
  renumbered: Renumbered[];
  missingTargets: string[];
  manifest: Record<string, unknown> | null;
}

export interface ImportOptions {
  exportDir: string;
  /** Import into this database (default: dry run, nothing written). */
  apply?: Db;
  /** Table/column catalogue (default: the generated src/shared/schema.generated.ts). */
  catalogue?: Catalogue;
  /** Migrations applied before an import (default: the files of <root>/server/migrations). */
  migrations?: readonly Migration[];
  root?: string;
  /**
   * Opt-in repair rule, per target table: a unique id column, referenced by no other table, whose duplicated values are
   * renumbered (later rows get MAX+1, MAX+2… in source order) instead of quarantined. Record the rule in an ADR; every
   * renumbering is listed in the report. Any other unique clash quarantines the row.
   */
  renumberUnique?: Readonly<Record<string, string>>;
}

/** The ordered migration files of a folder (Node scripts; bundles use src/backend/migrations.ts). */
export function readMigrations(folder: string): Migration[] {
  if (!existsSync(folder)) return [];
  return readdirSync(folder)
    .filter((f) => f.endsWith(".sql"))
    .sort((a, b) => a.localeCompare(b))
    .map((name) => ({ name, sql: readFileSync(join(folder, name), "utf8") }));
}

function targetOf(schema: Catalogue, source: string): string | null {
  const lower = source.toLowerCase();
  for (const [name, def] of Object.entries(schema)) if (name === lower || String(def.legacy ?? "").toLowerCase() === lower) return name;
  return null;
}

const quoteSqlite = (name: string) => `"${name.replace(/"/g, '""')}"`;

export async function runImport(options: ImportOptions): Promise<ImportResult> {
  const schema = options.catalogue ?? (SCHEMA as unknown as Catalogue);
  const sqlitePath = join(options.exportDir, "data.sqlite");
  if (!existsSync(sqlitePath)) throw new Error(`No export found: ${sqlitePath} (run the ODBC export first)`);
  const manifestPath = join(options.exportDir, "manifest.json");
  const manifest = existsSync(manifestPath)
    ? (JSON.parse(readFileSync(manifestPath, "utf8")) as { tables?: Record<string, { rows: number; count: number }> })
    : null;
  const source = new DatabaseSync(sqlitePath, { readOnly: true });
  const quarantine: Quarantined[] = [];
  const renumbered: Renumbered[] = [];
  const tables: TableReport[] = [];
  const names = (
    source.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name <> '__export' ORDER BY name").all() as { name: string }[]
  ).map((r) => r.name);
  if (options.apply)
    await migrate(options.apply, options.migrations ?? readMigrations(join(options.root ?? process.cwd(), "server", "migrations")));
  const seen = new Set<string>();
  try {
    for (const name of names) {
      const target = targetOf(schema, name);
      const info = manifest?.tables?.[name] ?? null;
      const report: TableReport = {
        source: name,
        target,
        manifestRows: info?.rows ?? null,
        manifestCount: info?.count ?? null,
        read: 0,
        converted: 0,
        quarantined: 0,
        imported: null,
        emptyDates: 0,
        nullDefaults: 0,
        droppedColumns: [],
      };
      tables.push(report);
      const rows = source.prepare(`SELECT * FROM ${quoteSqlite(name)}`).all() as Record<string, unknown>[];
      report.read = rows.length;
      if (!target) {
        report.note = "no table of this name in the schema: not imported";
        continue;
      }
      seen.add(target);
      const byName = new Map(schema[target].columns.map((c: CatalogueColumn) => [c.name, c]));
      const sourceColumns = (source.prepare(`PRAGMA table_info(${quoteSqlite(name)})`).all() as { name: string }[]).map((c) => c.name);
      report.droppedColumns = sourceColumns.filter((c) => !byName.has(c.toLowerCase()));
      const ready: { row: ImportRow; index: number }[] = [];
      rows.forEach((row, index) => {
        const out: ImportRow = {};
        let failed = false,
          emptyDates = 0,
          nullDefaults = 0;
        for (const [columnName, raw] of Object.entries(row)) {
          const def = byName.get(columnName.toLowerCase());
          if (!def) continue;
          try {
            const c = convertValue(def.kind, raw);
            if (c.emptyDate) emptyDates++;
            if (c.nullDefault) nullDefaults++;
            if (c.value !== undefined) out[def.name] = c.value;
          } catch (error) {
            failed = true;
            quarantine.push({
              table: name,
              row: index + 1,
              column: columnName,
              value: raw instanceof Uint8Array ? `<${raw.length} bytes>` : String(raw),
              reason: (error as Error).message,
            });
          }
        }
        if (failed) {
          report.quarantined++;
          return;
        }
        report.converted++;
        report.emptyDates += emptyDates;
        report.nullDefaults += nullDefaults;
        ready.push({ row: out, index });
      });
      const renumberColumn = options.renumberUnique?.[target]?.toLowerCase();
      if (renumberColumn) {
        const values = ready
          .map((r) => r.row[renumberColumn])
          .filter((v) => v !== null && v !== undefined)
          .map(Number);
        let next = values.length ? Math.max(...values) : 0;
        const used = new Set<string>();
        for (const r of ready) {
          const value = r.row[renumberColumn];
          if (value === null || value === undefined) continue;
          const key = String(value);
          if (!used.has(key)) {
            used.add(key);
            continue;
          }
          next++;
          const newValue = typeof value === "number" ? next : String(next);
          r.row[renumberColumn] = newValue;
          used.add(String(newValue));
          renumbered.push({ table: name, column: renumberColumn, oldValue: key, newValue: String(newValue), row: r.index + 1 });
        }
      }
      if (options.apply) {
        const existing = await options.apply.query<{ n: number }>(`SELECT count(*)::int n FROM ${target}`);
        if (Number(existing[0]?.n) > 0) {
          report.note = `target ${target} already has rows: not imported`;
          report.imported = 0;
          continue;
        }
        // One transaction per table; every value is a bound parameter (identifiers come from the catalogue).
        const insertRow = (tx: Queryable, row: ImportRow) => {
          const keys = Object.keys(row);
          return keys.length === 0
            ? tx.query(`INSERT INTO ${target} DEFAULT VALUES`)
            : tx.query(
                `INSERT INTO ${target} (${keys.join(", ")}) VALUES (${keys.map((_, i) => `$${i + 1}`).join(", ")})`,
                keys.map((k) => row[k]) as SqlValue[],
              );
        };
        // HFSQL automatic identifiers keep their values; the identity sequence then continues after the largest one.
        const primary = schema[target].primary;
        const restartIdentity = async (tx: Queryable) => {
          if (!ready.some(({ row }) => row[primary] !== undefined && row[primary] !== null)) return;
          await tx.query(`SELECT setval(pg_get_serial_sequence($1, $2), (SELECT max(${primary}) FROM ${target}))`, [target, primary]);
        };
        try {
          report.imported = await options.apply.transaction(async (tx) => {
            for (const { row } of ready) await insertRow(tx, row);
            await restartIdentity(tx);
            return ready.length;
          });
        } catch {
          // A row the database refuses (e.g. a duplicate on a unique index) is quarantined with the database's reason
          // instead of aborting the import: the table is retried with one savepoint per row.
          report.imported = await options.apply.transaction(async (tx) => {
            let imported = 0;
            for (const { row, index } of ready) {
              await tx.exec("SAVEPOINT import_row");
              try {
                await insertRow(tx, row);
                await tx.exec("RELEASE SAVEPOINT import_row");
                imported++;
              } catch (error) {
                await tx.exec("ROLLBACK TO SAVEPOINT import_row");
                report.converted--;
                report.quarantined++;
                quarantine.push({
                  table: name,
                  row: index + 1,
                  column: "—",
                  value: JSON.stringify(row, (_, v) => (v instanceof Uint8Array ? `<${v.length} bytes>` : v)).slice(0, 200),
                  reason: `refused by the database: ${(error as Error).message}`,
                });
              }
            }
            await restartIdentity(tx);
            return imported;
          });
        }
      }
    }
  } finally {
    source.close();
  }
  const missingTargets = Object.keys(schema).filter((t) => !seen.has(t));
  return { tables, quarantine, renumbered, missingTargets, manifest: manifest as Record<string, unknown> | null };
}

const cell = (value: string) => value.replace(/\|/g, "\\|").replace(/\r?\n/g, " ");

export function reconciliationMarkdown(result: ImportResult, mode: "dry-run" | "apply", exportDir: string): string {
  const lines = [
    "# Data import reconciliation",
    "",
    `Generated by \`tools/import.ts\` (${mode}) from \`${exportDir}\`. Conversions: empty dates → NULL, exact decimals, booleans, durations in ms.`,
    "A quarantined row is not imported: fix it in the source (or record a rule in an ADR) and run again.",
    "",
    "| Source table | Target | Manifest rows / COUNT(*) | Read | Converted | Quarantined | Imported | Empty dates → NULL | NULL → default | Dropped columns | Note |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
    ...result.tables.map(
      (t) =>
        `| ${t.source} | ${t.target ?? "—"} | ${t.manifestRows ?? "?"} / ${t.manifestCount ?? "?"}${t.manifestRows !== null && t.manifestRows !== t.read ? " ⚠ differs from read" : ""} | ${t.read} | ${t.converted} | ${t.quarantined} | ${t.imported ?? "—"} | ${t.emptyDates} | ${t.nullDefaults} | ${t.droppedColumns.join(", ") || "—"} | ${t.note ?? ""} |`,
    ),
    "",
    `Schema tables without a source table: ${result.missingTargets.join(", ") || "none"}.`,
    "",
    `## Quarantine (${result.quarantine.length})`,
    "",
  ];
  if (result.quarantine.length) {
    lines.push("| Table | Row | Column | Value | Reason |", "|---|---|---|---|---|");
    for (const q of result.quarantine.slice(0, 500))
      lines.push(`| ${q.table} | ${q.row} | ${q.column} | \`${cell(q.value).slice(0, 60)}\` | ${cell(q.reason)} |`);
    if (result.quarantine.length > 500) lines.push("", `… ${result.quarantine.length - 500} more.`);
  } else lines.push("None.");
  lines.push("", `## Renumbered duplicate unique ids (${result.renumbered.length})`, "");
  if (result.renumbered.length) {
    lines.push("| Table | Column | Old value | New value | Source row |", "|---|---|---|---|---|");
    for (const r of result.renumbered) lines.push(`| ${r.table} | ${r.column} | ${r.oldValue} | ${r.newValue} | ${r.row} |`);
  } else lines.push("None.");
  return lines.join("\n") + "\n";
}

async function openTarget(spec: string): Promise<Db & { close?: () => Promise<void> }> {
  if (/^postgres(ql)?:\/\//.test(spec)) {
    const { openPostgres } = await import("../server/pg-db");
    return openPostgres(spec);
  }
  const { openPglite } = await import("../src/backend/pglite-db");
  return openPglite(resolve(spec));
}

async function main(argv: string[]) {
  const arg = (flag: string) => {
    const i = argv.indexOf(flag);
    return i >= 0 ? argv[i + 1] : undefined;
  };
  const apply = argv.includes("--apply");
  const exportDir = arg("--export");
  if (!exportDir) throw new Error("usage: --export <folder> [--report <file>] [--apply [--db <PGlite folder | postgres://…>]]");
  const reportPath = arg("--report") ?? "docs/data/reconciliation.md";
  const dbSpec = arg("--db") ?? process.env.DATABASE_URL;
  if (apply && !dbSpec) throw new Error("--apply needs --db <PGlite folder> or DATABASE_URL");
  const db = apply ? await openTarget(dbSpec!) : undefined;
  try {
    const result = await runImport({ exportDir, apply: db });
    mkdirSync(dirname(reportPath), { recursive: true });
    writeFileSync(reportPath, reconciliationMarkdown(result, apply ? "apply" : "dry-run", exportDir), "utf8");
    const total = (k: "read" | "converted" | "quarantined") => result.tables.reduce((s, t) => s + t[k], 0);
    console.log(
      `${apply ? "apply" : "dry run"}: ${result.tables.length} tables, ${total("read")} rows read, ${total("converted")} converted, ${total("quarantined")} quarantined → ${reportPath}`,
    );
  } finally {
    await db?.close?.();
  }
}

if (process.argv[1] && /tools\/import\.ts$/.test(process.argv[1].replace(/\\/g, "/"))) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  });
}
