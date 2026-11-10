/**
 * First-run setup of a database: shared by the setup CLI (server/setup.ts, run by an installer or launcher) and the
 * tests. Every step works on a NEW staging database; the caller promotes it (e.g. renames the folder) only when the
 * summary says `ok`, and discards it otherwise.
 *
 *   setupEmpty   migrations + the start-up procedure
 *   setupImport  HFSQL JSONL export → importer input → dry run → (stop on any problem) → apply → per-table count check
 *                in the database → the start-up procedure (it must fill only what the legacy data lacks)
 */
import { join } from "node:path";
import type { Catalogue } from "../src/backend/catalogue";
import type { Db } from "../src/backend/db";
import { migrate, type Migration } from "../src/backend/migrate";
import { convertJsonl } from "../tools/hfsql-jsonl";
import { reconciliationMarkdown, runImport, type ImportResult, type Renumbered } from "../tools/import";

export interface SetupSummary {
  ok: boolean;
  mode: "empty" | "import";
  tables: number;
  rowsRead: number;
  imported: number;
  quarantined: number;
  problems: string[];
  /** Duplicated unique ids renumbered by the opt-in rule (also listed in the report). */
  renumbered: Renumbered[];
  /** What the start-up hook returned (e.g. what it created), for the installer to show. */
  init?: unknown;
}

export interface SetupOptions {
  migrations: readonly Migration[];
  /** The project's start-up procedure (e.g. `db => initialize({ db, ... })`); runs after a successful import. */
  initialize?: (db: Db) => Promise<unknown>;
}

export interface ImportSetupOptions extends SetupOptions {
  jsonlDir: string;
  /** New folder for the converted export (work/export). */
  workDir: string;
  catalogue?: Catalogue;
  renumberUnique?: Readonly<Record<string, string>>;
}

const sum = (result: ImportResult, key: "read" | "quarantined") => result.tables.reduce((s, t) => s + t[key], 0);

/**
 * Problems that forbid promoting the imported database: an empty export, a table without counts, rows read ≠ COUNT(*)
 * ≠ rows exported, any quarantined row, an unknown table holding rows, or (after apply) rows converted but not imported.
 */
export function importProblems(result: ImportResult, mode: "dry-run" | "apply"): string[] {
  const problems: string[] = [];
  if (result.tables.length === 0) problems.push("The export contains no tables.");
  for (const t of result.tables) {
    if (t.manifestRows === null || t.manifestCount === null) problems.push(`${t.source}: no counts in the export manifest.`);
    else if (t.manifestRows !== t.manifestCount) problems.push(`${t.source}: ${t.manifestRows} rows read, COUNT(*) ${t.manifestCount}.`);
    else if (t.manifestRows !== t.read) problems.push(`${t.source}: ${t.manifestRows} rows exported, ${t.read} read.`);
    if (t.quarantined > 0) problems.push(`${t.source}: ${t.quarantined} row(s) quarantined.`);
    if (!t.target && t.read > 0) problems.push(`${t.source}: unknown table with ${t.read} row(s).`);
    if (mode === "apply" && t.target && t.imported !== t.converted)
      problems.push(`${t.source}: ${t.converted} converted, ${t.imported ?? 0} imported${t.note ? ` (${t.note})` : ""}.`);
  }
  return problems;
}

export async function setupEmpty(db: Db, options: SetupOptions): Promise<SetupSummary> {
  await migrate(db, options.migrations);
  const init = await options.initialize?.(db);
  return { ok: true, mode: "empty", tables: 0, rowsRead: 0, imported: 0, quarantined: 0, problems: [], renumbered: [], init };
}

export async function setupImport(db: Db, options: ImportSetupOptions): Promise<{ summary: SetupSummary; report: string }> {
  const exportDir = join(options.workDir, "export");
  convertJsonl(options.jsonlDir, exportDir);
  const common = { exportDir, catalogue: options.catalogue, renumberUnique: options.renumberUnique };
  const dry = await runImport(common);
  const base = {
    mode: "import" as const,
    tables: dry.tables.length,
    rowsRead: sum(dry, "read"),
    quarantined: sum(dry, "quarantined"),
    renumbered: dry.renumbered,
  };
  let problems = importProblems(dry, "dry-run");
  if (problems.length)
    return { summary: { ok: false, ...base, imported: 0, problems }, report: reconciliationMarkdown(dry, "dry-run", exportDir) };
  const applied = await runImport({ ...common, apply: db, migrations: options.migrations });
  problems = importProblems(applied, "apply");
  for (const t of applied.tables) {
    if (!t.target) continue;
    const rows = await db.query<{ n: number }>(`SELECT count(*)::int n FROM ${t.target}`);
    if (Number(rows[0]?.n) !== t.imported) problems.push(`${t.source}: ${t.imported} imported, ${rows[0]?.n} in the database.`);
  }
  base.quarantined = sum(applied, "quarantined");
  const imported = applied.tables.reduce((s, t) => s + (t.imported ?? 0), 0);
  const report = reconciliationMarkdown(applied, "apply", exportDir);
  if (problems.length) return { summary: { ok: false, ...base, imported, problems }, report };
  const init = await options.initialize?.(db);
  return { summary: { ok: true, ...base, imported, problems: [], init }, report };
}
