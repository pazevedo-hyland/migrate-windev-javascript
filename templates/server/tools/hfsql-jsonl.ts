/**
 * Converts the ANSI ODBC export (the playbook's scripts/windows/hfsql-export.ps1: one `<table>.jsonl` per table, first
 * line = header {table, count, columns}, then one JSON array of values per row; binary as {"base64": "..."}) into the
 * importer's input (tools/import.ts): `data.sqlite` (every value as text, NULL as NULL, bytes as BLOB) + `manifest.json`
 * (rows read and COUNT(*)). Node-only twin of scripts/windows/hfsql_jsonl.py, so an installed setup needs no Python.
 * Refuses an export whose row count differs from the source's COUNT(*).
 *
 *   npx tsx tools/hfsql-jsonl.ts --in <jsonl folder> --out <new folder>
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";

type Header = { table: string; count: number; columns: { name: string; type: string; odbc_sql_type: number }[] };
export interface JsonlManifest {
  exported: string;
  source: string;
  tables: Record<string, { rows: number; count: number; columns: Header["columns"] }>;
}

const quote = (s: string) => `"${s.replace(/"/g, '""')}"`;

export function convertJsonl(inDir: string, outDir: string): JsonlManifest {
  if (existsSync(outDir) && readdirSync(outDir).length) throw new Error(`output folder must be new or empty: ${outDir}`);
  mkdirSync(outDir, { recursive: true });
  const db = new DatabaseSync(join(outDir, "data.sqlite"));
  const manifest: JsonlManifest = { exported: new Date().toISOString(), source: "HFSQL ANSI ODBC (jsonl)", tables: {} };
  try {
    for (const file of readdirSync(inDir)
      .filter((f) => f.endsWith(".jsonl"))
      .sort()) {
      const lines = readFileSync(join(inDir, file), "utf8").split(/\r?\n/).filter(Boolean);
      if (!lines.length) throw new Error(`${file}: no header line`);
      const header = JSON.parse(lines[0]) as Header;
      db.exec(`CREATE TABLE ${quote(header.table)} (${header.columns.map((c) => quote(c.name)).join(", ")})`);
      const insert = db.prepare(`INSERT INTO ${quote(header.table)} VALUES (${header.columns.map(() => "?").join(", ")})`);
      db.exec("BEGIN");
      for (const line of lines.slice(1)) {
        const values = (JSON.parse(line) as unknown[]).map((v) =>
          v === null
            ? null
            : typeof v === "object" && "base64" in v
              ? Buffer.from(String((v as { base64: string }).base64), "base64")
              : String(v),
        );
        if (values.length !== header.columns.length)
          throw new Error(`${header.table}: row has ${values.length} values, header ${header.columns.length}`);
        insert.run(...values);
      }
      db.exec("COMMIT");
      const rows = lines.length - 1;
      if (rows !== header.count) throw new Error(`${header.table}: ${rows} rows read, COUNT(*) ${header.count}`);
      manifest.tables[header.table] = { rows, count: header.count, columns: header.columns };
    }
  } finally {
    db.close();
  }
  writeFileSync(join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2), "utf8");
  return manifest;
}

if (process.argv[1] && /tools\/hfsql-jsonl\.ts$/.test(process.argv[1].replace(/\\/g, "/"))) {
  const arg = (flag: string) => {
    const i = process.argv.indexOf(flag);
    return i >= 0 ? process.argv[i + 1] : undefined;
  };
  const inDir = arg("--in"),
    outDir = arg("--out");
  if (!inDir || !outDir) {
    console.error("usage: --in <jsonl folder> --out <new folder>");
    process.exit(2);
  }
  const m = convertJsonl(inDir, outDir);
  console.log(`${Object.keys(m.tables).length} tables, ${Object.values(m.tables).reduce((s, t) => s + t.rows, 0)} rows → ${outDir}`);
}
