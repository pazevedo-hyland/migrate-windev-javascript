import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import type { Db } from "../src/backend/db";
import { openPglite } from "../src/backend/pglite-db";
import { EXAMPLE_CATALOGUE, EXAMPLE_MIGRATIONS } from "../src/backend/testing/example-schema";
import { setupEmpty, setupImport } from "./setup-core";

const dirs: string[] = [];
afterEach(() => {
  for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

/** A JSONL export as written by the playbook's scripts/windows/hfsql-export.ps1 (header line, then one array per row). */
function exportFolder(tables: Record<string, { columns: string[]; rows: unknown[][]; count?: number }>) {
  const root = mkdtempSync(join(tmpdir(), "app-setup-"));
  dirs.push(root);
  const jsonl = join(root, "jsonl");
  mkdirSync(jsonl);
  for (const [table, t] of Object.entries(tables)) {
    const header = { table, count: t.count ?? t.rows.length, columns: t.columns.map((name) => ({ name, type: "str", odbc_sql_type: 1 })) };
    writeFileSync(join(jsonl, `${table}.jsonl`), [header, ...t.rows].map((line) => JSON.stringify(line)).join("\n") + "\n");
  }
  return { jsonlDir: jsonl, workDir: join(root, "work") };
}

const clocking = {
  columns: ["Unique_Id", "Employee", "Clock_In"],
  rows: [
    ["10", "2", "2019-11-15 08:00:42.626"],
    ["11", "7", "2021-08-05 13:08:04.335"],
    ["11", "2", "2021-08-05 13:08:02.216"],
    ["9", "3", "2021-08-06 08:00:00.000"],
  ],
};

/** A start-up hook like a project's app.init: fills a one-record table only when the import did not bring it. */
const initialize = async (db: Db) => {
  const rows = await db.query("SELECT 1 FROM settings");
  if (rows.length) return { created: [] };
  await db.query("INSERT INTO settings (companyname) VALUES ('New company')");
  return { created: ["settings"] };
};
const base = { migrations: EXAMPLE_MIGRATIONS, catalogue: EXAMPLE_CATALOGUE, initialize };

describe("first-run setup", () => {
  it("empty database: migrations + the start-up hook", async () => {
    const db = await openPglite();
    const summary = await setupEmpty(db, base);
    expect(summary).toMatchObject({ ok: true, mode: "empty", init: { created: ["settings"] } });
    expect(await db.query("SELECT companyname FROM settings")).toEqual([{ companyname: "New company" }]);
    await db.close();
  });

  it("imports, renumbers a duplicated unique id by the configured rule, reconciles and runs the start-up hook", async () => {
    const db = await openPglite();
    const { summary, report } = await setupImport(db, {
      ...base,
      ...exportFolder({ Clocking: clocking, Customer: { columns: ["Code", "Name"], rows: [["001", "Acme"]] } }),
      renumberUnique: { clocking: "unique_id" },
    });
    expect(summary).toMatchObject({ ok: true, tables: 2, rowsRead: 5, imported: 5, quarantined: 0, problems: [] });
    expect(summary.renumbered).toEqual([{ table: "Clocking", column: "unique_id", oldValue: "11", newValue: "12", row: 3 }]);
    expect((await db.query("SELECT unique_id, employee FROM clocking ORDER BY unique_id")).map((r) => [r.unique_id, r.employee])).toEqual([
      [9, 3],
      [10, 2],
      [11, 7],
      [12, 2],
    ]);
    expect(report).toContain("| Clocking | unique_id | 11 | 12 | 3 |");
    expect(summary.init).toEqual({ created: ["settings"] });
    await db.close();
  });

  it("without the renumbering rule a duplicated unique id stops the promotion", async () => {
    const db = await openPglite();
    const { summary } = await setupImport(db, { ...base, ...exportFolder({ Clocking: clocking }) });
    expect(summary).toMatchObject({ ok: false, quarantined: 1, imported: 3 });
    expect(summary.problems.join("\n")).toContain("quarantined");
    expect(summary.init).toBeUndefined();
    await db.close();
  });

  it("stops before importing when a row is quarantined, and refuses an export whose counts disagree", async () => {
    const bad = await openPglite();
    const quarantined = await setupImport(bad, {
      ...base,
      ...exportFolder({ Clocking: { ...clocking, rows: [["1", "2", "2021-13-45 99:00:00"]] } }),
    });
    expect(quarantined.summary).toMatchObject({ ok: false, quarantined: 1, imported: 0 });
    expect(quarantined.summary.problems).toEqual(["Clocking: 1 row(s) quarantined."]);
    expect(quarantined.report).toContain("not a date-time");
    expect(await bad.query("SELECT 1 FROM information_schema.tables WHERE table_name = 'clocking'")).toEqual([]);
    await bad.close();

    const unknown = await setupImport(await openPglite(), { ...base, ...exportFolder({ Mystery: { columns: ["x"], rows: [["1"]] } }) });
    expect(unknown.summary.problems).toEqual(["Mystery: unknown table with 1 row(s)."]);

    const mismatch = await setupImport(await openPglite(), {
      ...base,
      ...exportFolder({ Customer: { columns: ["Code", "Name"], rows: [["001", "A"]], count: 2 } }),
    }).catch((error: Error) => error);
    expect(String(mismatch)).toMatch(/COUNT\(\*\) 2/);
  });
});
