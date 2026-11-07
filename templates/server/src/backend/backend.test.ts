import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createdNow, migrate } from "./migrate";
import { openPglite } from "./pglite-db";
import "./procedures/system";
import { dispatch, initialize, register, UserError } from "./rpc";
import { addSeed, applySeeds } from "./seed";
import { count, insert, list, nextNumber, remove, removeWhere, seek, startsWith, update, updateWhere } from "./tables";
import { exampleBackend } from "./testing/example-backend";
import { EXAMPLE_MIGRATIONS } from "./testing/example-schema";

register({
  "addonTest.echo": async (_ctx, input: { text: string }) => input.text,
  "addonTest.refuseInfo": async () => {
    throw new UserError("Info text");
  },
  "addonTest.refuseError": async () => {
    throw new UserError("Error text", "error");
  },
  "addonTest.crash": async () => {
    throw new Error("boom");
  },
  "addonTest.session": async (ctx) => ctx.session,
});

let backend: Awaited<ReturnType<typeof exampleBackend>>;
beforeAll(async () => {
  backend = await exampleBackend();
});
afterAll(() => backend.close());

describe("procedure registry", () => {
  it("returns values, refusals with their kind, and fatal failures", async () => {
    expect(await backend.call("addonTest.echo", { text: "hi" })).toEqual({ ok: true, value: "hi" });
    expect(await backend.call("addonTest.refuseInfo", {})).toEqual({ ok: false, error: "Info text", kind: "info" });
    expect(await backend.call("addonTest.refuseError", {})).toEqual({ ok: false, error: "Error text", kind: "error" });
    expect(await backend.call("addonTest.crash", {})).toEqual({ ok: false, error: "boom", kind: "fatal" });
    expect(await backend.call("nope", {})).toEqual({ ok: false, error: "Unknown procedure: nope", kind: "fatal" });
    expect(await backend.call("toString", {})).toMatchObject({ ok: false, kind: "fatal" }); // no prototype lookups
    expect(await backend.call("addonTest.session", {}, { user: "7" })).toEqual({ ok: true, value: { user: "7" } });
  });

  it("refuses a name registered twice", () => {
    expect(() => register({ "addonTest.echo": async () => null })).toThrow("registered twice");
  });

  it("system.migrations lists the applied migrations", async () => {
    expect(await backend.call("system.migrations", {})).toEqual({ ok: true, value: ["0001_schema_v1.sql"] });
  });
});

describe("tables (HAdd / HReadSeek / HModify / HDelete)", () => {
  it("HAdd fills analysis defaults and returns text forms for numeric, date and timestamp", async () => {
    const row = await insert(backend.db, "Customer", { code: "C1", balance: "12.345", created: "2026-11-05" });
    expect(row).toMatchObject({ code: "C1", name: "", balance: "12.345", inactive: false, created: "2026-11-05" });
    expect(typeof row.rowid_).toBe("number");
    const line = await insert(backend.db, "order_line", { orderno: 1, line: 1, started: "2026-11-05 09:30:00.250" });
    expect(line).toMatchObject({ started: "2026-11-05T09:30:00.25", ended: null, quantity: "0" });
    const settings = await insert(backend.db, "settings", { morningstart: "08:00:00" });
    expect(settings).toMatchObject({ morningstart: "08:00:00", rate: 0 });
  });

  it("seek = HReadSeekFirst; where supports =, NULL, like (startsWith), in and ranges", async () => {
    await insert(backend.db, "customer", { code: "C2", name: "Beta_1" });
    await insert(backend.db, "customer", { code: "C3", name: "beta%" });
    expect((await seek(backend.db, "customer", { code: "C2" }))?.name).toBe("Beta_1");
    expect(await seek(backend.db, "customer", { code: "NONE" })).toBeNull();
    expect((await list(backend.db, "customer", { where: { name: startsWith("beta") }, orderBy: "code" })).map((r) => r.code)).toEqual([
      "C2",
      "C3",
    ]);
    expect((await list(backend.db, "customer", { where: { name: startsWith("beta%") } })).map((r) => r.code)).toEqual(["C3"]);
    expect(
      (await list(backend.db, "customer", { where: { code: { in: ["C1", "C3"] } }, orderBy: "code DESC" })).map((r) => r.code),
    ).toEqual(["C3", "C1"]);
    expect(await list(backend.db, "customer", { where: { code: { in: [] } } })).toEqual([]);
    expect(await count(backend.db, "customer", { code: { gte: "C2", lte: "C3" } })).toBe(2);
    expect(await count(backend.db, "customer", { created: null })).toBe(2);
  });

  it("refuses unknown tables, columns and order clauses before building SQL", async () => {
    await expect(list(backend.db, "nope")).rejects.toThrow("Unknown table: nope");
    await expect(list(backend.db, "customer", { where: { "1=1; drop": 1 } })).rejects.toThrow("Unknown column");
    await expect(list(backend.db, "customer", { orderBy: "code; drop table customer" })).rejects.toThrow();
    await expect(insert(backend.db, "customer", { code: "X", bogus: 1 })).rejects.toThrow("Unknown column: customer.bogus");
  });

  it("HModify by primary key, update/delete where, and an empty delete condition is refused", async () => {
    const c = await seek(backend.db, "customer", { code: "C1" });
    expect(await update(backend.db, "customer", c!.rowid_, { name: "Alpha" })).toMatchObject({ code: "C1", name: "Alpha" });
    expect(await update(backend.db, "customer", 999999, { name: "x" })).toBeNull();
    expect(await updateWhere(backend.db, "customer", { name: startsWith("beta") }, { inactive: true })).toBe(2);
    await expect(removeWhere(backend.db, "customer", {})).rejects.toThrow("needs a condition");
    expect(await removeWhere(backend.db, "customer", { inactive: true })).toBe(2);
    expect(await remove(backend.db, "customer", c!.rowid_)).toBe(true);
    expect(await remove(backend.db, "customer", c!.rowid_)).toBe(false);
  });

  it("numbers like the legacy MAX+1", async () => {
    expect(await nextNumber(backend.db, "order_line", "line", { orderno: 7 })).toBe(1);
    await insert(backend.db, "order_line", { orderno: 7, line: 4 });
    expect(await nextNumber(backend.db, "order_line", "line", { orderno: 7 })).toBe(5);
  });
});

describe("transactions", () => {
  it("rolls back every step when one fails; nested calls reuse the transaction", async () => {
    await expect(
      backend.db.transaction(async (tx) => {
        await insert(tx, "customer", { code: "T1" });
        await tx.transaction(async (inner) => insert(inner, "customer", { code: "T2" }));
        throw new Error("boom");
      }),
    ).rejects.toThrow("boom");
    expect(await count(backend.db, "customer", { code: { in: ["T1", "T2"] } })).toBe(0);
  });

  it("a transaction started while another one runs is still atomic (PGlite serializes them; no shared nesting flag)", async () => {
    let started!: () => void;
    const isStarted = new Promise<void>((resolve) => (started = resolve));
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const first = backend.db.transaction(async (tx) => {
      await insert(tx, "customer", { code: "R1" });
      started();
      await gate;
    });
    await isStarted;
    const second = backend.db.transaction(async (tx) => {
      await insert(tx, "customer", { code: "R2" });
      throw new Error("rollback R2");
    });
    release();
    await first;
    await expect(second).rejects.toThrow("rollback R2");
    expect((await list(backend.db, "customer", { where: { code: { in: ["R1", "R2"] } } })).map((r) => r.code)).toEqual(["R1"]);
  });
});

describe("migrations, seeds and start-up", () => {
  it("applies pending migrations once, in name order, and tells when it created the database", async () => {
    const db = await openPglite();
    try {
      const extra = { name: "0002_add_index.sql", sql: "CREATE INDEX customer_created ON customer (created);" };
      const first = await migrate(db, [extra, ...EXAMPLE_MIGRATIONS]);
      expect(first).toEqual(["0001_schema_v1.sql", "0002_add_index.sql"]);
      expect(createdNow(first, EXAMPLE_MIGRATIONS)).toBe(true);
      const again = await migrate(db, [extra, ...EXAMPLE_MIGRATIONS]);
      expect(again).toEqual([]);
      expect(createdNow(again, EXAMPLE_MIGRATIONS)).toBe(false);
      const broken = migrate(db, [...EXAMPLE_MIGRATIONS, { name: "0003_broken.sql", sql: "CREATE TABLE ok_part (x int); SELECT nope();" }]);
      await expect(broken).rejects.toThrow();
      expect(await db.query("SELECT 1 FROM information_schema.tables WHERE table_name = 'ok_part'")).toEqual([]);
      expect((await db.query("SELECT name FROM schema_migrations ORDER BY name")).map((r) => r.name)).toEqual([
        "0001_schema_v1.sql",
        "0002_add_index.sql",
      ]);
    } finally {
      await db.close();
    }
  });

  it("seeds families, merges one-record tables and skips duplicate keys", async () => {
    addSeed("addonTest.a", { settings: [{ companyname: "Demo" }], customer: [{ code: "S1", name: "One" }] });
    addSeed("addonTest.b", { settings: [{ morningstart: "09:00:00" }], customer: [{ code: "S1", name: "Dup" }, { code: "S2" }] });
    const db = await openPglite();
    try {
      await migrate(db, EXAMPLE_MIGRATIONS);
      const skipped = await applySeeds(db, { families: ["addonTest.a", "addonTest.b"], singletons: ["Settings"] });
      expect(skipped).toHaveLength(1);
      expect(await db.query("SELECT companyname, morningstart FROM settings")).toEqual([{ companyname: "Demo", morningstart: "09:00:00" }]);
      expect((await list(db, "customer", { orderBy: "code" })).map((r) => [r.code, r.name])).toEqual([
        ["S1", "One"],
        ["S2", ""],
      ]);
      const onlyA = await openPglite();
      await migrate(onlyA, EXAMPLE_MIGRATIONS);
      await applySeeds(onlyA, { families: ["addonTest.a"] });
      expect(await count(onlyA, "customer")).toBe(1);
      await onlyA.close();
    } finally {
      await db.close();
    }
  });

  it("runs the start-up procedure when registered and fails loudly when it refuses", async () => {
    const db = await openPglite();
    const ctx = { db, session: {}, now: () => new Date(), settings: { APP_FLAG: "x" } };
    const name = "addonTest.init";
    expect(await initialize(ctx, name)).toBeUndefined();
    let calls = 0;
    register({
      [name]: async (c) => {
        calls++;
        if (c.settings?.APP_FLAG === "refuse") throw new UserError("not configured");
        return { flag: c.settings?.APP_FLAG };
      },
    });
    expect(await initialize(ctx, name)).toEqual({ flag: "x" });
    await expect(initialize({ ...ctx, settings: { APP_FLAG: "refuse" } }, name)).rejects.toThrow("addonTest.init failed: not configured");
    expect(calls).toBe(2);
    expect((await dispatch(ctx, name, {})).ok).toBe(true);
    await db.close();
  });
});
