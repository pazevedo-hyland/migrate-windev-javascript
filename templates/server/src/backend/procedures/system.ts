import { register, type Context } from "../rpc";

/** Infrastructure procedures (no legacy counterpart): what a station, the setup or a test can ask about the database. */
register({
  /** The migrations applied to this database, in order: an independent reader for setup and smoke checks. */
  "system.migrations": async (ctx: Context) =>
    (await ctx.db.query<{ name: string }>("SELECT name FROM schema_migrations ORDER BY name")).map((row) => row.name),
});
