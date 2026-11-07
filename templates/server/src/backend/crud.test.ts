import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { installCatalogue } from "./catalogue";
import { defineCrud, type CrudMessages } from "./crud";
import { UserError } from "./rpc";
import { insert, seek } from "./tables";
import { exampleBackend } from "./testing/example-backend";
import { EXAMPLE_CATALOGUE } from "./testing/example-schema";

installCatalogue(EXAMPLE_CATALOGUE);

// Placeholder texts: a real project copies them from the legacy windows and the WINDEV runtime it ran with.
const MESSAGES: CrudMessages = {
  gone: "GONE",
  confirmDelete: "CONFIRM?",
  emptyKey: "EMPTY KEY",
  duplicate: (item, value) => `DUPLICATE ${item}=${value}`,
};

defineCrud({
  name: "addonTest.customers",
  table: "customer",
  key: "code",
  fields: ["code", "name", "balance"],
  messages: MESSAGES,
  duplicateMessage: "CODE EXISTS",
  keyRules: [{ refuses: (key) => String(key).includes("'"), message: "NO QUOTE" }],
  validate: (values) => (String(values.name ?? "").trim() === "" ? "NO NAME" : null),
  authorize: (ctx, action) => {
    if (action !== "list" && ctx.session.user !== "admin") throw new UserError("NO RIGHT");
  },
  preDeleteGuards: [(key) => (key === "GENERAL" ? "CANNOT DELETE GENERAL" : null)],
  deleteGuards: [{ table: "order_line", column: "customer", message: "HAS ORDERS" }],
  confirmMessage: "DELETE THIS CUSTOMER?",
});
defineCrud({
  name: "addonTest.customersReinsert",
  table: "customer",
  key: "code",
  fields: ["code", "name"],
  messages: MESSAGES,
  duplicateMessage: "CODE EXISTS",
  whenModifiedRecordIsGone: "reinsert",
});

const admin = { user: "admin" };
let backend: Awaited<ReturnType<typeof exampleBackend>>;
beforeAll(async () => {
  backend = await exampleBackend();
});
afterAll(() => backend.close());

describe("defineCrud save (Form window)", () => {
  it("checks rights, empty key, key rules, existing key and validation in the legacy order", async () => {
    const save = (values: Record<string, string>, session = admin) =>
      backend.call("addonTest.customers.save", { mode: "new", values }, session);
    expect(await save({ code: "A", name: "x" }, { user: "guest" })).toEqual({ ok: false, kind: "info", error: "NO RIGHT" });
    expect(await save({ code: " ", name: "x" })).toEqual({ ok: false, kind: "info", error: "EMPTY KEY" });
    expect(await save({ code: "O'K", name: "x" })).toEqual({ ok: false, kind: "info", error: "NO QUOTE" });
    expect(await save({ code: "A", name: "" })).toEqual({ ok: false, kind: "info", error: "NO NAME" });
    const created = await save({ code: "A", name: "Alpha", balance: "1.50" });
    expect(created).toMatchObject({ ok: true, value: { code: "A", name: "Alpha", balance: "1.50", inactive: false } });
    expect(await save({ code: "A", name: "Again" })).toEqual({ ok: false, kind: "info", error: "CODE EXISTS" });
  });

  it("saves only the form's fields; modify keeps the other columns; a unique clash gives WINDEV's duplicate error", async () => {
    const a = await seek(backend.db, "customer", { code: "A" });
    await backend.db.query("UPDATE customer SET inactive = true WHERE code = 'A'");
    const modified = await backend.call(
      "addonTest.customers.save",
      { mode: "modify", id: a!.rowid_, values: { code: "A", name: "Alpha 2", inactive: false, rowid_: 999 } },
      admin,
    );
    expect(modified).toMatchObject({ ok: true, value: { rowid_: a!.rowid_, name: "Alpha 2", inactive: true } });
    await insert(backend.db, "customer", { code: "B", name: "Beta" });
    const clash = await backend.call(
      "addonTest.customers.save",
      { mode: "modify", id: a!.rowid_, values: { code: "B", name: "Alpha" } },
      admin,
    );
    expect(clash).toEqual({ ok: false, kind: "error", error: "DUPLICATE code=B" });
    expect((await seek(backend.db, "customer", { rowid_: a!.rowid_ }))?.code).toBe("A");
  });

  it("modify of a record deleted meanwhile: refused by default, re-added when the window re-adds it", async () => {
    const gone = await backend.call("addonTest.customers.save", { mode: "modify", id: 424242, values: { code: "Z", name: "Zed" } }, admin);
    expect(gone).toEqual({ ok: false, kind: "info", error: "GONE" });
    expect(await seek(backend.db, "customer", { code: "Z" })).toBeNull();
    const again = await backend.call("addonTest.customersReinsert.save", {
      mode: "modify",
      id: 424242,
      values: { code: "Z", name: "Zed" },
    });
    expect(again).toMatchObject({ ok: true, value: { code: "Z", name: "Zed" } });
  });
});

describe("defineCrud list/get/delete (Table window)", () => {
  it("lists in key order and gets by key", async () => {
    const listed = await backend.call("addonTest.customers.list", {});
    expect(listed.ok && (listed.value as { code: string }[]).map((r) => r.code)).toEqual(["A", "B", "Z"]);
    expect(await backend.call("addonTest.customers.get", { key: "B" }, admin)).toMatchObject({ ok: true, value: { name: "Beta" } });
    expect(await backend.call("addonTest.customers.get", { key: "B" })).toEqual({ ok: false, kind: "info", error: "NO RIGHT" });
  });

  it("delete: pre-guards before the read, gone, dependent records, confirmation, then deletes", async () => {
    const del = (key: string, confirmed?: boolean) => backend.call("addonTest.customers.delete", { key, confirmed }, admin);
    expect(await del("GENERAL")).toEqual({ ok: false, kind: "info", error: "CANNOT DELETE GENERAL" });
    expect(await del("NOPE")).toEqual({ ok: false, kind: "info", error: "GONE" });
    await insert(backend.db, "order_line", { orderno: 1, line: 1, customer: "B" });
    expect(await del("B")).toEqual({ ok: false, kind: "info", error: "HAS ORDERS" });
    expect(await del("A")).toEqual({ ok: true, value: { needsConfirmation: "DELETE THIS CUSTOMER?" } });
    expect(await seek(backend.db, "customer", { code: "A" })).not.toBeNull();
    expect(await backend.call("addonTest.customersReinsert.delete", { key: "A" })).toEqual({
      ok: true,
      value: { needsConfirmation: "CONFIRM?" },
    });
    expect(await del("A", true)).toEqual({ ok: true, value: { deleted: true } });
    expect(await seek(backend.db, "customer", { code: "A" })).toBeNull();
  });

  it("refuses a definition on an unknown table at registration", () => {
    expect(() =>
      defineCrud({ name: "addonTest.x", table: "nope", key: "code", fields: [], messages: MESSAGES, duplicateMessage: "" }),
    ).toThrow("Unknown table");
  });
});
