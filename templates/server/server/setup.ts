/**
 * Setup CLI of a new database, bundled next to the server (server/build.mjs) for an installer or launcher:
 *
 *   node setup.js empty  --db <new staging PGlite folder>
 *   node setup.js import --db <new staging PGlite folder> --jsonl <HFSQL jsonl folder> --work <new folder> --report <file>
 *
 * Anything secret the start-up procedure needs (e.g. a first administrator password chosen in a wizard) comes from the
 * environment (APP_* variables, passed as ctx.settings), never from argv.
 * The last stdout line is `RESULT <json SetupSummary>`; exit code 0 only when the summary says ok (3 = refused, 1 = error).
 * The caller promotes the staging folder only on exit code 0.
 */
import { existsSync, readdirSync, writeFileSync } from "node:fs";
import { initialize, MIGRATIONS, type Db } from "../src/backend/index";
import { openPglite } from "../src/backend/pglite-db";
import { setupEmpty, setupImport, type SetupSummary } from "./setup-core";

const argv = process.argv.slice(2);
const arg = (flag: string) => {
  const i = argv.indexOf(flag);
  return i >= 0 ? argv[i + 1] : undefined;
};
const settings = Object.freeze(Object.fromEntries(Object.entries(process.env).filter(([name]) => name.startsWith("APP_"))));

async function main(): Promise<SetupSummary> {
  const mode = argv[0],
    dbDir = arg("--db");
  if ((mode !== "empty" && mode !== "import") || !dbDir) throw new Error("usage: empty|import --db <folder> [...]");
  if (existsSync(dbDir) && readdirSync(dbDir).length) throw new Error(`staging database folder must be new: ${dbDir}`);
  const db = await openPglite(dbDir);
  const options = {
    migrations: MIGRATIONS,
    initialize: (target: Db) => initialize({ db: target, session: {}, now: () => new Date(), settings }),
  };
  try {
    if (mode === "empty") return await setupEmpty(db, options);
    const jsonlDir = arg("--jsonl"),
      workDir = arg("--work"),
      reportPath = arg("--report");
    if (!jsonlDir || !workDir || !reportPath) throw new Error("import needs --jsonl, --work and --report");
    const { summary, report } = await setupImport(db, { ...options, jsonlDir, workDir });
    writeFileSync(reportPath, report, "utf8");
    return summary;
  } finally {
    await db.close();
  }
}

main().then(
  (summary) => {
    process.stdout.write(`RESULT ${JSON.stringify(summary)}\n`);
    process.exit(summary.ok ? 0 : 3);
  },
  (error) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stdout.write(`RESULT ${JSON.stringify({ ok: false, problems: [message] })}\n`);
    process.exit(1);
  },
);
