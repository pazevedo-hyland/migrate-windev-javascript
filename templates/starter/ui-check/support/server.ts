/** Test-only Vite middleware backed by fresh scratch SQLite. Never loaded by production Vite. */
import { randomUUID } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { createServer, type Plugin } from "vite";

const scratch = await mkdtemp(join(tmpdir(), "migration-workflow-tests-"));
const database = new DatabaseSync(join(scratch, "fixture.sqlite"));
database.exec(`CREATE TABLE members(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL,active INTEGER NOT NULL);
CREATE TABLE rooms(id TEXT PRIMARY KEY,code TEXT NOT NULL UNIQUE,capacity TEXT NOT NULL,notes TEXT NOT NULL);`);
const entities = new Set(["members", "rooms"]);
type Entity = "members" | "rooms";

function reset() {
  database.exec("BEGIN;DELETE FROM members;DELETE FROM rooms;");
  try {
    const members = database.prepare("INSERT INTO members VALUES(?,?,?,?)");
    members.run("9007199254740993", "Alpha reader", "alpha@example.invalid", 1);
    members.run("9007199254740994", "Beta reader", "beta@example.invalid", 0);
    const rooms = database.prepare("INSERT INTO rooms VALUES(?,?,?,?)");
    rooms.run("9007199254740995", "R-A", "12", "Quiet room");
    rooms.run("9007199254740996", "R-B", "8", "Project room");
    database.exec("COMMIT");
  } catch (error) { database.exec("ROLLBACK"); throw error; }
}
reset();

function list(entity: Entity): ({ id: string } & Record<string, unknown>)[] {
  // Entity is allowlisted before use as an SQL identifier; all record values are parameters.
  const rows = database.prepare(`SELECT * FROM ${entity} ORDER BY id`).all();
  return rows.map(row => {
    if (typeof row.id !== "string") throw new Error("Fixture identities must stay strings");
    return { ...row, id: row.id, ...(entity === "members" ? { active: row.active === 1 } : {}) };
  });
}
async function payload(request: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  let length = 0;
  for await (const chunk of request) {
    length += chunk.length;
    if (length > 65536) throw new Error("Invalid fixture payload");
    chunks.push(Buffer.from(chunk));
  }
  const result: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (!result || typeof result !== "object" || Array.isArray(result)) throw new Error("Invalid fixture payload");
  return result as Record<string, unknown>;
}
function validate(entity: Entity, fields: Record<string, unknown>): string | undefined {
  const keys = entity === "members" ? ["name", "email", "active"] : ["code", "capacity", "notes"];
  if (Object.keys(fields).sort().join() !== keys.sort().join()) return "Unexpected fixture fields";
  if (entity === "members") {
    if (typeof fields.name !== "string" || !fields.name.trim()) return "Name is required";
    if (typeof fields.email !== "string" || typeof fields.active !== "boolean") return "Invalid member fields";
  } else {
    if (typeof fields.code !== "string" || !fields.code.trim()) return "Code is required";
    if (typeof fields.capacity !== "string" || !/^[1-9][0-9]*$/.test(fields.capacity)) return "Capacity must be a positive integer";
    if (typeof fields.notes !== "string") return "Invalid room fields";
  }
}
function send(response: ServerResponse, status: number, value: unknown) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(JSON.stringify(value));
}
async function handle(request: IncomingMessage, response: ServerResponse) {
  const path = new URL(request.url ?? "/", "http://127.0.0.1").pathname;
  if (path === "/__workflow_fixture/reset" && request.method === "POST") { reset(); send(response, 200, { reset: true }); return; }
  const match = /^\/__workflow_fixture\/api\/(members|rooms)(?:\/([^/]+))?$/.exec(path);
  if (!match || !entities.has(match[1])) { send(response, 404, { error: "Unknown fixture route" }); return; }
  const entity = match[1] as Entity, id = match[2] ? decodeURIComponent(match[2]) : undefined;
  if (request.method === "GET" && !id) { send(response, 200, list(entity)); return; }
  if ((request.method === "PATCH" || request.method === "DELETE") && (!id || !list(entity).some(row => row.id === id))) {
    send(response, 404, { error: "Record does not exist" }); return;
  }
  if (request.method === "DELETE" && id) {
    database.prepare(`DELETE FROM ${entity} WHERE id=?`).run(id);
    send(response, 200, { deleted: id }); return;
  }
  if ((request.method !== "POST" || id) && (request.method !== "PATCH" || !id)) {
    send(response, 405, { error: "Unsupported fixture operation" }); return;
  }
  const fields = await payload(request), invalid = validate(entity, fields);
  if (invalid) { send(response, 422, { error: invalid }); return; }
  const key = id ?? randomUUID();
  if (entity === "rooms" && list(entity).some(row => row.code === fields.code && row.id !== key)) {
    send(response, 409, { error: "Code already exists" }); return;
  }
  if (entity === "members") {
    const values = [fields.name as string, fields.email as string, fields.active ? 1 : 0];
    if (id) database.prepare("UPDATE members SET name=?,email=?,active=? WHERE id=?").run(...values, key);
    else database.prepare("INSERT INTO members(name,email,active,id) VALUES(?,?,?,?)").run(...values, key);
  } else {
    const values = [fields.code as string, fields.capacity as string, fields.notes as string];
    if (id) database.prepare("UPDATE rooms SET code=?,capacity=?,notes=? WHERE id=?").run(...values, key);
    else database.prepare("INSERT INTO rooms(code,capacity,notes,id) VALUES(?,?,?,?)").run(...values, key);
  }
  send(response, id ? 200 : 201, list(entity).find(row => row.id === key));
}
const fixture: Plugin = { name: "isolated-workflow-fixture", configureServer(server) {
  server.middlewares.use((request, response, next) => {
    if (!request.url?.startsWith("/__workflow_fixture/")) { next(); return; }
    void handle(request, response).catch(() => send(response, 400, { error: "Invalid fixture request" }));
  });
} };
let closing = false;
const server = await createServer({ plugins: [fixture], server: { host: "127.0.0.1", port: 1421, strictPort: true } });
async function close() {
  if (closing) return;
  closing = true;
  try { await server.close(); } finally { database.close(); await rm(scratch, { recursive: true, force: true }); }
}
process.once("SIGTERM", () => { void close(); });
process.once("SIGINT", () => { void close(); });
try { await server.listen(); } catch (error) { await close(); throw error; }
