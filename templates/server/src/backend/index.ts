/**
 * Backend entry: installs the generated catalogue, then registers every procedure module (./procedures/index.ts).
 * Import it once from each host: the server, the setup CLI and the local backend. Keep "./schema" the first import.
 */
import "./schema";
import "./procedures/index";

export { dispatch, initialize, procedures, register, UserError, INIT_PROCEDURE } from "./rpc";
export type { Context, ErrorKind, RpcResult, Session, Settings } from "./rpc";
export { migrate, createdNow, type Migration } from "./migrate";
export { MIGRATIONS } from "./migrations";
export type { Db, Queryable, Row, SqlValue } from "./db";
