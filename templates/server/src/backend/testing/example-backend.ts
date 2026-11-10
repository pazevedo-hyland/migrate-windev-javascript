import { installCatalogue } from "../catalogue";
import { migrate } from "../migrate";
import { openPglite } from "../pglite-db";
import { dispatch, type RpcResult, type Session } from "../rpc";
import { EXAMPLE_CATALOGUE, EXAMPLE_MIGRATIONS } from "./example-schema";

/**
 * The add-on's own tests run on the example schema, in memory, WITHOUT importing ../index.ts: the application's
 * procedure modules, catalogue and start-up procedure stay out of them, so they keep passing as the app grows.
 * Their procedure names start with "addonTest." to stay clear of the app's. Application tests use createLocalBackend.
 */
export async function exampleBackend() {
  installCatalogue(EXAMPLE_CATALOGUE);
  const db = await openPglite();
  await migrate(db, EXAMPLE_MIGRATIONS);
  const now = () => new Date();
  return {
    db,
    call: (name: string, input: unknown, session: Session = {}): Promise<RpcResult> =>
      dispatch({ db, session, now, settings: {} }, name, input),
    close: () => db.close(),
  };
}
