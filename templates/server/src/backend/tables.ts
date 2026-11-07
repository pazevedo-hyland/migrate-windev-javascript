import { catalogue, type CatalogueColumn } from "./catalogue";
import type { Queryable, Row, SqlValue } from "./db";

/**
 * Catalogue-checked access to the migrated HFSQL files: ports of HReadSeekFirst, HAdd, HModify, HDelete and the
 * legacy MAX+1 numbering. Table and column names must exist in the catalogue (anything else throws before any SQL is
 * built); values are always bound parameters. Every row carries its primary key (`rowid_` for files without an
 * automatic identifier).
 */
export type Condition = SqlValue | { like: string } | { in: readonly SqlValue[] } | { gte?: SqlValue; lte?: SqlValue };
export type Where = Record<string, Condition>;
export interface ListOptions {
  where?: Where;
  orderBy?: string | string[];
  limit?: number;
}

export function table(name: string) {
  const key = name.toLowerCase();
  const definition = Object.hasOwn(catalogue(), key) ? catalogue()[key] : undefined;
  if (!definition) throw new Error(`Unknown table: ${name}`);
  return { name: key, ...definition };
}

export function column(tableName: string, name: string): string {
  const t = table(tableName);
  const lower = name.toLowerCase();
  if (lower === t.primary || t.columns.some((c: CatalogueColumn) => c.name === lower)) return lower;
  throw new Error(`Unknown column: ${tableName}.${name}`);
}

/** Escapes LIKE wildcards so a user value matches literally. */
export const escapeLike = (value: string) => value.replace(/[\\%_]/g, (c) => `\\${c}`);

/** HReadSeek generic search (the default, without hIdentical): starts with `value`, case-insensitive. */
export const startsWith = (value: string): { like: string } => ({ like: `${escapeLike(value)}%` });

function orderClause(tableName: string, orderBy?: string | string[]) {
  if (!orderBy) return "";
  const parts = (Array.isArray(orderBy) ? orderBy : [orderBy]).map((part) => {
    const [name, direction, ...rest] = part.trim().split(/\s+/);
    if (rest.length || (direction && !/^(asc|desc)$/i.test(direction))) throw new Error(`Bad order: ${part}`);
    return column(tableName, name) + (direction?.toUpperCase() === "DESC" ? " DESC" : "");
  });
  return ` ORDER BY ${parts.join(", ")}`;
}

/** Builds ` WHERE …` (all conditions joined with AND), appending the values to `params`. */
export function whereClause(tableName: string, where: Where = {}, params: SqlValue[] = []) {
  const parts: string[] = [];
  const bind = (value: SqlValue) => {
    params.push(value);
    return `$${params.length}`;
  };
  for (const [name, value] of Object.entries(where)) {
    const c = column(tableName, name);
    if (value === null) parts.push(`${c} IS NULL`);
    else if (typeof value !== "object") parts.push(`${c} = ${bind(value)}`);
    else if ("like" in value) parts.push(`${c} ILIKE ${bind(value.like)}`);
    else if ("in" in value) parts.push(value.in.length ? `${c} IN (${value.in.map(bind).join(", ")})` : "false");
    else {
      if (value.gte !== undefined) parts.push(`${c} >= ${bind(value.gte)}`);
      if (value.lte !== undefined) parts.push(`${c} <= ${bind(value.lte)}`);
    }
  }
  return { sql: parts.length ? ` WHERE ${parts.join(" AND ")}` : "", params };
}

export async function list<T extends Row = Row>(db: Queryable, tableName: string, options: ListOptions = {}): Promise<T[]> {
  const t = table(tableName);
  const { sql, params } = whereClause(t.name, options.where);
  const limit = options.limit ? ` LIMIT ${Math.max(1, Math.floor(options.limit))}` : "";
  return db.query<T>(`SELECT * FROM ${t.name}${sql}${orderClause(t.name, options.orderBy)}${limit}`, params);
}

/** HReadSeekFirst: the first row matching `where` (exact values), in `orderBy` order (default: primary key), or null. */
export async function seek<T extends Row = Row>(
  db: Queryable,
  tableName: string,
  where: Where,
  orderBy?: string | string[],
): Promise<T | null> {
  const rows = await list<T>(db, tableName, { where, orderBy: orderBy ?? table(tableName).primary, limit: 1 });
  return rows[0] ?? null;
}

/** HNbRec / SQL COUNT(*) with an optional filter. */
export async function count(db: Queryable, tableName: string, where?: Where): Promise<number> {
  const t = table(tableName);
  const { sql, params } = whereClause(t.name, where);
  const rows = await db.query<{ n: number }>(`SELECT count(*)::int AS n FROM ${t.name}${sql}`, params);
  return Number(rows[0]?.n ?? 0);
}

function writable(tableName: string, values: Row) {
  const t = table(tableName);
  return Object.entries(values)
    .filter(([name]) => name.toLowerCase() !== t.primary)
    .map(([name, value]) => [column(t.name, name), value] as const);
}

/** HAdd: items not given take their analysis default (the DDL default). Returns the stored row. */
export async function insert<T extends Row = Row>(db: Queryable, tableName: string, values: Row): Promise<T> {
  const t = table(tableName);
  const entries = writable(t.name, values);
  if (entries.length === 0) return (await db.query<T>(`INSERT INTO ${t.name} DEFAULT VALUES RETURNING *`))[0];
  const columns = entries.map(([c]) => c).join(", ");
  const placeholders = entries.map((_, i) => `$${i + 1}`).join(", ");
  return (
    await db.query<T>(
      `INSERT INTO ${t.name} (${columns}) VALUES (${placeholders}) RETURNING *`,
      entries.map(([, v]) => v),
    )
  )[0];
}

/** HModify of the record identified by its primary key. Returns the stored row, or null when it no longer exists. */
export async function update<T extends Row = Row>(db: Queryable, tableName: string, id: SqlValue, values: Row): Promise<T | null> {
  const t = table(tableName);
  const entries = writable(t.name, values);
  if (entries.length === 0) return seek<T>(db, t.name, { [t.primary]: id });
  const sets = entries.map(([c], i) => `${c} = $${i + 1}`).join(", ");
  const sql = `UPDATE ${t.name} SET ${sets} WHERE ${t.primary} = $${entries.length + 1} RETURNING *`;
  return (await db.query<T>(sql, [...entries.map(([, v]) => v), id]))[0] ?? null;
}

/** SQL UPDATE … WHERE (legacy code that modifies every matching record). Returns the number of rows changed. */
export async function updateWhere(db: Queryable, tableName: string, where: Where, values: Row): Promise<number> {
  const t = table(tableName);
  const entries = writable(t.name, values);
  if (entries.length === 0) return 0;
  const params: SqlValue[] = entries.map(([, v]) => v);
  const condition = whereClause(t.name, where, params);
  const sets = entries.map(([c], i) => `${c} = $${i + 1}`).join(", ");
  return (await db.query(`UPDATE ${t.name} SET ${sets}${condition.sql} RETURNING ${t.primary}`, condition.params)).length;
}

/** HDelete of the record identified by its primary key. */
export async function remove(db: Queryable, tableName: string, id: SqlValue): Promise<boolean> {
  const t = table(tableName);
  return (await db.query(`DELETE FROM ${t.name} WHERE ${t.primary} = $1 RETURNING ${t.primary}`, [id])).length > 0;
}

/** SQL DELETE … WHERE; refuses an empty condition (it would empty the table). */
export async function removeWhere(db: Queryable, tableName: string, where: Where): Promise<number> {
  const t = table(tableName);
  const { sql, params } = whereClause(t.name, where);
  if (!sql) throw new Error("removeWhere needs a condition");
  return (await db.query(`DELETE FROM ${t.name}${sql} RETURNING ${t.primary}`, params)).length;
}

/**
 * The legacy MAX+1 numbering (HReadLast on the key + 1, or SELECT MAX(...)+1). Run it inside the save's transaction;
 * two concurrent saves can still compute the same number, so keep a unique index on the column (the save then fails
 * and can be retried) or lock the table: decide which in the project's ADR.
 */
export async function nextNumber(db: Queryable, tableName: string, columnName: string, where?: Where): Promise<number> {
  const t = table(tableName);
  const c = column(t.name, columnName);
  const { sql, params } = whereClause(t.name, where);
  const rows = await db.query<{ n: number | string | null }>(`SELECT max(${c}) AS n FROM ${t.name}${sql}`, params);
  return Number(rows[0]?.n ?? 0) + 1;
}
