import type { Db } from "./db";

/**
 * Procedure registry. Every backend operation is a named procedure `(ctx, input) => output`. The same registry runs
 * in the Node server (shared database, `POST /rpc`) and in the browser (in-memory PGlite: preview, UI checks, unit
 * tests), so business rules have one implementation. A procedure that writes opens ONE transaction itself
 * (`ctx.db.transaction`): one user save = one call = one transaction. It replaces the WLanguage procedures that ran
 * HAdd/HModify/HDelete directly against shared HFSQL files.
 */

/**
 * Who is calling: the legacy globals the procedures need (logged-in user, workstation, mode…). Augment it in the app:
 *
 *   declare module "./rpc" { interface Session { user?: string | null; station?: string | null } }
 *
 * It travels in the request body and is asserted by the client: authenticate it before exposing the server beyond a
 * trusted network.
 */
export interface Session {
  [key: string]: string | number | boolean | null | undefined;
}

/** Server settings: the `APP_*` environment of the server process (empty in the browser preview). */
export type Settings = Readonly<Record<string, string | undefined>>;

export interface Context {
  db: Db;
  session: Session;
  now: () => Date;
  settings?: Settings;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- one registry of differently typed procedures; each declares its own types
export type Procedure<I = any, O = any> = (ctx: Context, input: I) => Promise<O>;
export type ProcedureMap = Record<string, Procedure>;

/**
 * How the UI shows a refusal: "info" = WLanguage Info(), "error" = Error(), "fatal" = an unexpected failure
 * (exception, unknown procedure, unreachable server).
 */
export type ErrorKind = "info" | "error" | "fatal";

/** A business refusal carrying the legacy message text, shown by the UI with the legacy dialog of its kind. */
export class UserError extends Error {
  constructor(
    message: string,
    readonly kind: ErrorKind = "info",
  ) {
    super(message);
    this.name = "UserError";
  }
}

const registry: ProcedureMap = {};

export function register(procedures: ProcedureMap) {
  for (const [name, procedure] of Object.entries(procedures)) {
    if (registry[name]) throw new Error(`Procedure registered twice: ${name}`);
    registry[name] = procedure;
  }
}

export function procedures(): Readonly<ProcedureMap> {
  return registry;
}

export type RpcResult = { ok: true; value: unknown } | { ok: false; error: string; kind: ErrorKind };

/** Runs one procedure; never throws. A UserError keeps its text and kind; anything else is "fatal". */
export async function dispatch(ctx: Context, name: string, input: unknown): Promise<RpcResult> {
  const procedure = Object.hasOwn(registry, name) ? registry[name] : undefined;
  if (!procedure) return { ok: false, error: `Unknown procedure: ${name}`, kind: "fatal" };
  try {
    return { ok: true, value: await procedure(ctx, input) };
  } catch (error) {
    if (error instanceof UserError) return { ok: false, error: error.message, kind: error.kind };
    return { ok: false, error: error instanceof Error ? error.message : String(error), kind: "fatal" };
  }
}

/**
 * Optional start-up procedure (the legacy project initialization code: base rows, version table…). When registered,
 * the server, the setup CLI and the local backend run it once at every start; it must be idempotent.
 */
export const INIT_PROCEDURE = "app.init";

export async function initialize(ctx: Context, name = INIT_PROCEDURE): Promise<unknown> {
  if (!Object.hasOwn(registry, name)) return undefined;
  const result = await dispatch(ctx, name, {});
  if (!result.ok) throw new Error(`${name} failed: ${result.error}`);
  return result.value;
}
