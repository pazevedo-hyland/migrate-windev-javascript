import type { Migration } from "./migrate";

/**
 * The project's migrations (`server/migrations/*.sql`), bundled as text by Vite (`import.meta.glob`) so the browser
 * preview, the tests and the built server apply exactly the same files. Node scripts run with tsx (no Vite) read the
 * folder instead: `readMigrations` in tools/import.ts.
 */
const files = import.meta.glob("../../server/migrations/*.sql", { query: "?raw", import: "default", eager: true }) as Record<
  string,
  string
>;

export const MIGRATIONS: readonly Migration[] = Object.entries(files)
  .map(([path, sql]) => ({ name: path.split("/").pop()!, sql }))
  .sort((a, b) => a.name.localeCompare(b.name));
