import type { Db } from "./db";

export interface Migration {
  /** File name, e.g. "0001_schema_v1.sql": migrations run in name order. */
  name: string;
  sql: string;
}

/**
 * Ordered, immutable migrations (the target's replacement for HFSQL's automatic data modification, HModifyStructure).
 * Each pending migration runs in its own transaction and is recorded in `schema_migrations`; a committed migration is
 * never edited: changes go in the next number. Returns the names applied by this call.
 */
export async function migrate(db: Db, migrations: readonly Migration[]): Promise<string[]> {
  const ordered = [...migrations].sort((a, b) => a.name.localeCompare(b.name));
  await db.exec("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamp(3) NOT NULL DEFAULT now())");
  const done = new Set((await db.query<{ name: string }>("SELECT name FROM schema_migrations")).map((row) => row.name));
  const applied: string[] = [];
  for (const migration of ordered) {
    if (done.has(migration.name)) continue;
    await db.transaction(async (tx) => {
      await tx.exec(migration.sql);
      await tx.query("INSERT INTO schema_migrations (name) VALUES ($1)", [migration.name]);
    });
    applied.push(migration.name);
  }
  return applied;
}

/** True when this `migrate` call created the database (it applied the first migration): seed demo data only then. */
export function createdNow(applied: readonly string[], migrations: readonly Migration[]): boolean {
  const first = migrations.map((m) => m.name).sort((a, b) => a.localeCompare(b))[0];
  return first !== undefined && applied.includes(first);
}
