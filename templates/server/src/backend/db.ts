/**
 * Database port. Procedures receive a `Db`; adapters exist for PGlite (browser preview, tests, single-server default)
 * and PostgreSQL (`pg`, shared server). SQL is PostgreSQL; every value is a bound parameter.
 *
 * Wire value conventions (both adapters, so the UI sees the same values in the preview and against the server):
 *   numeric   -> string, exact ("12.345"; arithmetic with a decimal library, never JS floats)
 *   date      -> "YYYY-MM-DD"
 *   time      -> "HH:MM:SS[.mmm]"
 *   timestamp -> "YYYY-MM-DDTHH:MM:SS[.mmm]"
 *   bigint    -> number (the importer refuses values above 2^53; send larger identifiers as strings)
 *   boolean   -> boolean, NULL -> null
 */
export type SqlValue = string | number | boolean | null;
export type Row = Record<string, SqlValue>;

export interface Queryable {
  query<T extends Row = Row>(sql: string, params?: readonly SqlValue[]): Promise<T[]>;
  exec(sql: string): Promise<void>;
}

export interface Db extends Queryable {
  /**
   * One user save = one transaction (BEGIN … COMMIT, ROLLBACK when `work` throws). `work` receives the transaction as a
   * `Db`: pass `tx` to every helper; `tx.transaction(...)` reuses the same transaction (no savepoint). Inside `work`
   * never use the outer `db` again: on PGlite that waits for the transaction to end (deadlock), on PostgreSQL it runs
   * on another connection, outside the transaction.
   */
  transaction<T>(work: (tx: Db) => Promise<T>): Promise<T>;
  close?(): Promise<void>;
}

/** A transaction handle as a `Db`: nested `transaction` calls run in it. */
export function inTransaction(tx: Queryable): Db {
  const db: Db = {
    query: <T extends Row = Row>(sql: string, params?: readonly SqlValue[]) => tx.query<T>(sql, params),
    exec: (sql: string) => tx.exec(sql),
    transaction: (work) => work(db),
  };
  return db;
}

/** PostgreSQL type OIDs whose text form is kept (see the conventions above). */
export const TEXT_TYPES = { numeric: 1700, date: 1082, time: 1083, timestamp: 1114, timestamptz: 1184 } as const;
export const INT8_OID = 20;

export function normalizeTimestamp(value: string): string {
  return value.includes("T") ? value : value.replace(" ", "T");
}

/** A bigint as a JS number, refusing silent precision loss. */
export function int8(value: string): number {
  const n = Number(value);
  if (!Number.isSafeInteger(n)) throw new Error(`bigint ${value} is above 2^53: select it as text`);
  return n;
}
