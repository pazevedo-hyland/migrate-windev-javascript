import pg from "pg";
import {
  inTransaction,
  int8,
  INT8_OID,
  normalizeTimestamp,
  TEXT_TYPES,
  type Db,
  type Queryable,
  type Row,
  type SqlValue,
} from "../src/backend/db";

// Same wire values as the PGlite adapter (src/backend/db.ts conventions).
const keep = (value: string) => value;
pg.types.setTypeParser(TEXT_TYPES.numeric, keep);
pg.types.setTypeParser(TEXT_TYPES.date, keep);
pg.types.setTypeParser(TEXT_TYPES.time, keep);
pg.types.setTypeParser(TEXT_TYPES.timestamp, normalizeTimestamp);
pg.types.setTypeParser(TEXT_TYPES.timestamptz, normalizeTimestamp);
pg.types.setTypeParser(INT8_OID, int8);

function wrap(client: Pick<pg.Pool | pg.PoolClient, "query">): Queryable {
  return {
    async query<T extends Row>(sql: string, params: readonly SqlValue[] = []) {
      return (await client.query(sql, params as unknown[])).rows as T[];
    },
    async exec(sql: string) {
      await client.query(sql);
    },
  };
}

/** PostgreSQL adapter for the shared server. The connection string comes from the environment (DATABASE_URL), never Git. */
export async function openPostgres(connectionString: string): Promise<Db & { close(): Promise<void> }> {
  const pool = new pg.Pool({ connectionString });
  return {
    ...wrap(pool),
    async transaction(work) {
      const client = await pool.connect();
      try {
        await client.query("BEGIN");
        const result = await work(inTransaction(wrap(client)));
        await client.query("COMMIT");
        return result;
      } catch (error) {
        await client.query("ROLLBACK");
        throw error;
      } finally {
        client.release();
      }
    },
    close: () => pool.end(),
  };
}
