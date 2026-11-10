import { dispatch, initialize, MIGRATIONS, migrate, type Migration, type RpcResult, type Session, type Settings } from "./index";
import { openPglite } from "./pglite-db";
import { applySeeds, type Seed } from "./seed";
import "./seeds/index";

/**
 * In-process backend: the real procedures and SQL on an in-memory PGlite. Used by the browser preview (no server),
 * the UI checks and the unit tests of procedures: same migrations and procedures as the server.
 */
export interface LocalBackendOptions {
  /** false = empty database; true (default) = every registered demo family; a list = only those families. */
  seed?: boolean | readonly string[];
  extraSeeds?: readonly Seed[];
  singletons?: readonly string[];
  migrations?: readonly Migration[];
  now?: () => Date;
  settings?: Settings;
  /** Run the start-up procedure (app.init) when one is registered. Default: true. */
  init?: boolean;
}

export async function createLocalBackend(options: LocalBackendOptions = {}) {
  const db = await openPglite();
  await migrate(db, options.migrations ?? MIGRATIONS);
  if (options.seed !== false)
    await applySeeds(db, {
      families: Array.isArray(options.seed) ? options.seed : undefined,
      extra: options.extraSeeds,
      singletons: options.singletons,
    });
  const now = options.now ?? (() => new Date());
  const settings = options.settings ?? {};
  if (options.init !== false) await initialize({ db, session: {}, now, settings });
  return {
    db,
    call: (name: string, input: unknown, session: Session = {}): Promise<RpcResult> =>
      dispatch({ db, session, now, settings }, name, input),
    close: () => db.close(),
  };
}
