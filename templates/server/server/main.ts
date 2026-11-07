/**
 * Procedure server: the procedure registry over HTTP for every station (replaces the HFSQL Client/Server engine the
 * stations shared, and the business code that ran on each station against it).
 *
 *   POST /rpc   {"name": "<procedure>", "input": {...}, "session": {...}}  ->  RpcResult (always HTTP 200 when parsed)
 *   GET /health ->  "ok"
 *
 * Environment (no credentials in Git: set them in the service environment):
 *   DATABASE_URL       PostgreSQL connection string; when unset, an embedded PGlite folder is used
 *   APP_DATA_DIR       the PGlite folder (default ./app-data)
 *   PORT               listening port (default 4900, the HFSQL Client/Server default: change it if both run on one host)
 *   APP_HOST           listening address (default: all interfaces); 127.0.0.1 for an embedded single-PC server
 *   APP_CORS_ORIGIN    Access-Control-Allow-Origin (default "*": restrict it to the app's origin outside a trusted LAN)
 *   APP_DEV_SEED=1     seed the demo data into a database this start has just created (tests, demos; never production)
 *   APP_STDIO_CONTROL=1  for a launcher or a test fixture: print one stdout line `READY` once listening, or
 *                      `FAILED <reason>`, and shut down cleanly (close the database) when stdin reaches end of file
 * Every APP_* variable is passed to procedures as `ctx.settings`.
 *
 * Built with `npm run server:build` (server/build.mjs: Vite SSR, bundles the SQL migrations) and run with `npm run server`.
 */
import { createServer } from "node:http";
import { createdNow, dispatch, initialize, MIGRATIONS, migrate, type Db, type Session } from "../src/backend/index";
import { openPglite } from "../src/backend/pglite-db";
import { applySeeds } from "../src/backend/seed";
import "../src/backend/seeds/index";

const controlled = process.env.APP_STDIO_CONTROL === "1";
const MAX_BODY = 16 * 1024 * 1024;
const settings = Object.freeze(Object.fromEntries(Object.entries(process.env).filter(([name]) => name.startsWith("APP_"))));
const log = controlled ? console.error : console.log; // stdout is the control channel when controlled

async function openDb(): Promise<Db & { close(): Promise<void> }> {
  if (process.env.DATABASE_URL) {
    const { openPostgres } = await import("./pg-db");
    return openPostgres(process.env.DATABASE_URL);
  }
  return openPglite(process.env.APP_DATA_DIR || "./app-data");
}

async function start() {
  const db = await openDb();
  const applied = await migrate(db, MIGRATIONS);
  if (process.env.APP_DEV_SEED === "1" && createdNow(applied, MIGRATIONS)) await applySeeds(db);
  await initialize({ db, session: {}, now: () => new Date(), settings });
  const port = Number(process.env.PORT || 4900);
  const host = process.env.APP_HOST || undefined;
  const origin = process.env.APP_CORS_ORIGIN || "*";

  const server = createServer(async (request, response) => {
    response.setHeader("access-control-allow-origin", origin);
    response.setHeader("access-control-allow-headers", "content-type");
    if (request.method === "OPTIONS") {
      response.writeHead(204).end();
      return;
    }
    if (request.method === "GET" && request.url === "/health") {
      response.writeHead(200).end("ok");
      return;
    }
    if (request.method !== "POST" || request.url !== "/rpc") {
      response.writeHead(404).end();
      return;
    }
    const chunks: Buffer[] = [];
    let size = 0;
    for await (const chunk of request) {
      size += (chunk as Buffer).length;
      if (size > MAX_BODY) {
        response.writeHead(413).end();
        request.destroy();
        return;
      }
      chunks.push(chunk as Buffer);
    }
    let body: { name?: unknown; input?: unknown; session?: Session };
    try {
      body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    } catch {
      response.writeHead(400).end();
      return;
    }
    if (typeof body?.name !== "string") {
      response.writeHead(400).end();
      return;
    }
    const session = body.session && typeof body.session === "object" ? body.session : {};
    const result = await dispatch({ db, session, now: () => new Date(), settings }, body.name, body.input ?? {});
    response.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(result));
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => {
      server.off("error", reject);
      resolve();
    });
  });
  log(`server on ${host ?? "*"}:${port} (${process.env.DATABASE_URL ? "PostgreSQL" : "PGlite"}, ${applied.length} migrations applied)`);
  if (controlled) {
    process.stdout.write("READY\n");
    let stopping = false;
    const stop = async () => {
      if (stopping) return;
      stopping = true;
      server.close();
      server.closeAllConnections();
      try {
        await db.close();
      } finally {
        process.exit(0);
      }
    };
    process.stdin.on("end", stop);
    process.stdin.on("error", stop);
    process.stdin.resume();
  }
}

start().catch((error) => {
  const reason = error instanceof Error ? error.message : String(error);
  if (controlled) process.stdout.write(`FAILED ${reason.replace(/\s+/g, " ")}\n`);
  console.error(error);
  process.exit(1);
});
