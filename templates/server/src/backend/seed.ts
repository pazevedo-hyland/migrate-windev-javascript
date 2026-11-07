import type { Db, Row } from "./db";
import { insert } from "./tables";

/**
 * Demo data for the browser preview, the UI checks and `APP_DEV_SEED=1` server runs: synthetic rows shaped like the
 * legacy data, never a copy of production data. Each feature family adds a module (`addSeed`) imported from
 * ./seeds/index.ts, so a family can be seeded alone in its tests.
 *
 * Families seed independently, so: rows of `singletons` tables (one-record configuration files) are merged into one row
 * (later non-empty values win), and a row whose unique key already exists is skipped (returned) instead of failing the
 * whole seed.
 */
export type Seed = Record<string, Row[]>;
const seeds: { family: string; seed: Seed }[] = [];

export function addSeed(family: string, seed: Seed) {
  seeds.push({ family, seed });
}

export function seedFamilies(): string[] {
  return [...new Set(seeds.map((s) => s.family))];
}

const isEmpty = (value: unknown) => value === null || value === undefined || value === "" || value === 0 || value === false;

export interface SeedOptions {
  /** Only these families (default: all registered). */
  families?: readonly string[];
  /** Extra seeds after the registered ones (tests). */
  extra?: readonly Seed[];
  /** One-record tables whose rows from several families are merged. */
  singletons?: readonly string[];
}

/** Seeds in one transaction. Returns the rows skipped because their unique key already existed. */
export async function applySeeds(db: Db, options: SeedOptions = {}): Promise<string[]> {
  const families = options.families;
  const chosen = families ? seeds.filter((s) => families.includes(s.family)) : seeds;
  const all = [...chosen.map((s) => s.seed), ...(options.extra ?? [])];
  const singletonNames = new Set((options.singletons ?? []).map((n) => n.toLowerCase()));
  const singletons = new Map<string, Row>();
  for (const seed of all)
    for (const [tableName, rows] of Object.entries(seed)) {
      const name = tableName.toLowerCase();
      if (!singletonNames.has(name)) continue;
      const merged = singletons.get(name) ?? {};
      for (const row of rows) for (const [k, v] of Object.entries(row)) if (!isEmpty(v) || !(k in merged)) merged[k] = v;
      singletons.set(name, merged);
    }
  const skipped: string[] = [];
  await db.transaction(async (tx) => {
    for (const [name, row] of singletons) await insert(tx, name, row);
    let n = 0;
    for (const seed of all)
      for (const [tableName, rows] of Object.entries(seed)) {
        if (singletonNames.has(tableName.toLowerCase())) continue;
        for (const row of rows) {
          const savepoint = `seed_${++n}`;
          await tx.exec(`SAVEPOINT ${savepoint}`);
          try {
            await insert(tx, tableName, row);
            await tx.exec(`RELEASE SAVEPOINT ${savepoint}`);
          } catch (error) {
            await tx.exec(`ROLLBACK TO SAVEPOINT ${savepoint}`);
            if (!/duplicate key|unique constraint/i.test(String((error as Error).message))) throw error;
            skipped.push(`${tableName}: ${JSON.stringify(row).slice(0, 120)}`);
          }
        }
      }
  });
  return skipped;
}
