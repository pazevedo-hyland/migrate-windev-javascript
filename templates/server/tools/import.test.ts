import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { openPglite } from "../src/backend/pglite-db";
import { EXAMPLE_CATALOGUE, EXAMPLE_MIGRATIONS } from "../src/backend/testing/example-schema";
import { convertValue, reconciliationMarkdown, runImport } from "./import";

/** A synthetic export in the format of scripts/windows/export_odbc.py (every value text, NULL as NULL, bytes as BLOB). */
function writeExport(dir: string) {
  const db = new DatabaseSync(join(dir, "data.sqlite"));
  const tables: Record<string, { columns: string[]; rows: (string | null | Uint8Array)[][] }> = {
    Customer: {
      columns: ["Code", "Name", "Balance", "Inactive", "Legacy_Only"],
      rows: [
        ["C1", "Table", "12.345", "1", "x"],
        ["C2", "Chair", "", "False", "y"],
        ["C3", "Bad", "1,5", "0", "z"],
      ],
    },
    Order_Line: {
      columns: ["OrderNo", "Line", "Customer", "Started", "Ended", "Quantity", "Closed"],
      rows: [
        ["7", "1", "C1", "2026-11-05T09:00:00", "2026-11-05T10:30:15.500000", "3.5", "True"],
        ["7", "2", "C1", "20261105140000000", "", "0", "0"],
        ["7", "3", "C1", "2026-02-30T09:00:00", null, "1", "0"],
      ],
    },
    Process_Step: {
      columns: ["Article", "Process", "Minutes", "Step"],
      rows: [
        ["A1", "CUT", "0:05:00", "1"],
        ["A1", "PAINT", "300000", "2"],
        ["A2", "CUT", "1 day, 2:00:00.250000", "1"],
      ],
    },
    Settings: { columns: ["CompanyName", "MorningStart", "Rate"], rows: [["Demo", "093000", "0.25"]] },
    Clocking: {
      columns: ["IDClocking", "Unique_Id", "Employee", "Clock_In"],
      rows: [
        ["5", "10", "2", "2019-11-15 08:00:42.626"],
        ["9", "11", "7", "00000000000000000"],
      ],
    },
    Photo: {
      columns: ["Code", "Picture"],
      rows: [
        ["P1", new Uint8Array([1, 2, 3])],
        ["P2", null],
      ],
    },
    Unknown_File: { columns: ["x"], rows: [["1"]] },
  };
  const manifest: { tables: Record<string, { rows: number; count: number }> } = { tables: {} };
  for (const [name, t] of Object.entries(tables)) {
    db.exec(`CREATE TABLE "${name}" (${t.columns.map((c) => `"${c}"`).join(", ")})`);
    const insert = db.prepare(`INSERT INTO "${name}" VALUES (${t.columns.map(() => "?").join(", ")})`);
    for (const row of t.rows) insert.run(...row);
    manifest.tables[name] = { rows: t.rows.length, count: t.rows.length };
  }
  db.close();
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest), "utf8");
}

let dir: string;
beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "app-import-"));
  writeExport(dir);
});
afterAll(() => rmSync(dir, { recursive: true, force: true }));

const options = () => ({ exportDir: dir, catalogue: EXAMPLE_CATALOGUE, migrations: EXAMPLE_MIGRATIONS });

describe("HFSQL value conversion", () => {
  it("dates, date-times, times, decimals, reals, booleans, durations, binary", () => {
    expect(convertValue("date", "00000000")).toEqual({ value: null, emptyDate: true });
    expect(convertValue("date", "")).toEqual({ value: null, emptyDate: true });
    expect(convertValue("date", "20261105").value).toBe("2026-11-05");
    expect(convertValue("datetime", "2026-11-05T10:30:15.500000").value).toBe("2026-11-05 10:30:15.500");
    expect(convertValue("datetime", "20261105143000120").value).toBe("2026-11-05 14:30:00.120");
    expect(convertValue("time", "093000").value).toBe("09:30:00.000");
    expect(convertValue("time", "09300050").value).toBe("09:30:00.500");
    expect(convertValue("decimal", "12.345").value).toBe("12.345");
    expect(convertValue("real", "-1.5e3").value).toBe(-1500);
    expect(convertValue("boolean", "True").value).toBe(true);
    expect(convertValue("boolean", "-1").value).toBe(true);
    expect(convertValue("duration", "1 day, 2:00:00.250000").value).toBe(26 * 3_600_000 + 250);
    expect(convertValue("duration", "-0:00:01").value).toBe(-1000);
    expect(convertValue("duration", "300000").value).toBe(300000);
    expect(convertValue("integer", "")).toEqual({ value: undefined, nullDefault: true });
    expect(convertValue("text", null)).toEqual({ value: undefined, nullDefault: true });
    expect(convertValue("binary", new Uint8Array([1])).value).toEqual(new Uint8Array([1]));
    expect(() => convertValue("decimal", "1,5")).toThrow("not a decimal");
    expect(() => convertValue("datetime", "2026-02-30T09:00:00")).toThrow("not a date-time");
    expect(() => convertValue("datetime", "2026-11-05T09:00:00.0005")).toThrow("sub-millisecond");
    expect(() => convertValue("bigint", "9007199254740993")).toThrow("2^53");
    expect(() => convertValue("integer", "3000000000")).toThrow("out of range");
    expect(() => convertValue("text", new Uint8Array([1]))).toThrow("binary value");
  });
});

describe("tools/import.ts on a synthetic export", () => {
  it("dry run: counts, quarantine and reconciliation report, nothing written", async () => {
    const result = await runImport(options());
    const t = Object.fromEntries(result.tables.map((x) => [x.source, x]));
    expect(t.Customer).toMatchObject({
      target: "customer",
      read: 3,
      converted: 2,
      quarantined: 1,
      nullDefaults: 1,
      droppedColumns: ["Legacy_Only"],
      imported: null,
    });
    expect(t.Order_Line).toMatchObject({ read: 3, converted: 2, quarantined: 1, emptyDates: 1 });
    expect(t.Clocking).toMatchObject({ converted: 2, emptyDates: 1 });
    expect(t.Unknown_File).toMatchObject({ target: null, note: expect.stringContaining("not imported") });
    expect(result.quarantine).toEqual([
      { table: "Customer", row: 3, column: "Balance", value: "1,5", reason: "not a decimal" },
      { table: "Order_Line", row: 3, column: "Started", value: "2026-02-30T09:00:00", reason: "not a date-time" },
    ]);
    expect(result.missingTargets).toEqual([]);
    const md = reconciliationMarkdown(result, "dry-run", dir);
    expect(md).toContain("| Customer | customer | 3 / 3 | 3 | 2 | 1 | — | 0 | 1 | Legacy_Only |");
    expect(md).toContain("## Quarantine (2)");
  });

  it("apply: migrates, one transaction per table, keeps automatic ids, refuses tables that already have rows", async () => {
    const db = await openPglite();
    try {
      const result = await runImport({ ...options(), apply: db });
      expect(result.tables.find((x) => x.source === "Customer")?.imported).toBe(2);
      expect(await db.query("SELECT code, balance, inactive FROM customer ORDER BY code")).toEqual([
        { code: "C1", balance: "12.345", inactive: true },
        { code: "C2", balance: "0", inactive: false },
      ]);
      expect(await db.query("SELECT line, started, ended, quantity, closed FROM order_line ORDER BY line")).toEqual([
        { line: 1, started: "2026-11-05T09:00:00", ended: "2026-11-05T10:30:15.5", quantity: "3.5", closed: true },
        { line: 2, started: "2026-11-05T14:00:00", ended: null, quantity: "0", closed: false },
      ]);
      expect((await db.query("SELECT minutes FROM process_step ORDER BY step, article")).map((r) => r.minutes)).toEqual([
        300000, 93600250, 300000,
      ]);
      expect(await db.query("SELECT morningstart, rate FROM settings")).toEqual([{ morningstart: "09:30:00", rate: 0.25 }]);
      expect(await db.query("SELECT idclocking, clock_in FROM clocking ORDER BY idclocking")).toEqual([
        { idclocking: 5, clock_in: "2019-11-15T08:00:42.626" },
        { idclocking: 9, clock_in: null },
      ]);
      // The identity continues after the imported automatic identifiers (a new HAdd does not collide).
      expect(await db.query("INSERT INTO clocking (unique_id) VALUES (12) RETURNING idclocking")).toEqual([{ idclocking: 10 }]);
      const photos = (await db.query("SELECT code, picture FROM photo ORDER BY code")) as unknown as { picture: Uint8Array | null }[];
      expect(Array.from(photos[0].picture!)).toEqual([1, 2, 3]);
      expect(photos[1].picture).toBeNull();
      const again = await runImport({ ...options(), apply: db });
      expect(again.tables.find((x) => x.source === "Customer")).toMatchObject({
        imported: 0,
        note: expect.stringContaining("already has rows"),
      });
    } finally {
      await db.close();
    }
  });

  it("renumbers duplicated unique ids only for the configured table; any other clash is quarantined by the database", async () => {
    const dup = mkdtempSync(join(tmpdir(), "app-import-dup-"));
    try {
      const source = new DatabaseSync(join(dup, "data.sqlite"));
      source.exec(`CREATE TABLE "Clocking" ("Unique_Id", "Employee"); CREATE TABLE "Photo" ("Code")`);
      for (const row of [
        ["10", "1"],
        ["11", "2"],
        ["11", "3"],
      ])
        source.prepare(`INSERT INTO "Clocking" VALUES (?, ?)`).run(...row);
      for (const code of ["P1", "P1"]) source.prepare(`INSERT INTO "Photo" VALUES (?)`).run(code);
      source.close();
      writeFileSync(
        join(dup, "manifest.json"),
        JSON.stringify({ tables: { Clocking: { rows: 3, count: 3 }, Photo: { rows: 2, count: 2 } } }),
      );
      const db = await openPglite();
      const result = await runImport({ ...options(), exportDir: dup, apply: db, renumberUnique: { clocking: "unique_id" } });
      expect(result.renumbered).toEqual([{ table: "Clocking", column: "unique_id", oldValue: "11", newValue: "12", row: 3 }]);
      expect((await db.query("SELECT unique_id, employee FROM clocking ORDER BY unique_id")).map((r) => [r.unique_id, r.employee])).toEqual(
        [
          [10, 1],
          [11, 2],
          [12, 3],
        ],
      );
      expect(result.tables.find((t) => t.source === "Photo")).toMatchObject({ converted: 1, quarantined: 1, imported: 1 });
      expect(result.quarantine[0]).toMatchObject({ table: "Photo", row: 2, reason: expect.stringContaining("refused by the database") });
      await db.close();
    } finally {
      rmSync(dup, { recursive: true, force: true });
    }
  });
});
