import { PGlite } from "@electric-sql/pglite";
import { inTransaction, int8, INT8_OID, normalizeTimestamp, TEXT_TYPES, type Db, type Queryable, type Row, type SqlValue } from "./db";

const keep = (value: string) => value;
const parsers = {
  [TEXT_TYPES.numeric]: keep,
  [TEXT_TYPES.date]: keep,
  [TEXT_TYPES.time]: keep,
  [TEXT_TYPES.timestamp]: normalizeTimestamp,
  [TEXT_TYPES.timestamptz]: normalizeTimestamp,
  [INT8_OID]: int8,
};

function wrap(target: Pick<PGlite, "query" | "exec">): Queryable {
  return {
    async query<T extends Row>(sql: string, params: readonly SqlValue[] = []) {
      const result = await target.query<T>(sql, params as unknown[]);
      return result.rows;
    },
    async exec(sql: string) {
      await target.exec(sql);
    },
  };
}

/**
 * PGlite adapter (PostgreSQL compiled to WASM: same SQL, no install). `dataDir` undefined = in memory;
 * "idb://name" in a browser; a folder path on Node (the embedded single-server database).
 */
export async function openPglite(dataDir?: string): Promise<Db & { close(): Promise<void>; raw: PGlite }> {
  const pg = await PGlite.create(dataDir, { parsers });
  return {
    ...wrap(pg),
    raw: pg,
    // PGlite runs one statement or transaction at a time: concurrent calls (server requests) wait their turn.
    transaction: (work) => pg.transaction((tx) => work(inTransaction(wrap(tx)))),
    close: () => pg.close(),
  };
}
