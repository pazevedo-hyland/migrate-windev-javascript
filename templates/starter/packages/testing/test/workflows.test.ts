import { describe, expect, it, vi } from "vitest";
import type { Page } from "@playwright/test";
import { cancelEdits, createAndReopen, deleteCancelThenConfirm, editAndReopen, invalidSaveUnchanged,
  searchAndSelect, type StoredRow, type WorkflowContract } from "../src/index";

type Draft = { label: string | null };
const first = "9007199254740993", second = "9007199254740994";
function fixture() {
  const rows: StoredRow[] = [{ key: first, values: { label: "Original  " } }, { key: second, values: { label: null } }];
  let active: string | undefined, draft: Draft = { label: "" };
  const page = { reload: vi.fn(async () => { draft = { label: "reload clears view" }; }) };
  const store = { read: vi.fn(async (): Promise<readonly StoredRow[]> => rows) };
  const driver = {
    openList: vi.fn(async () => {}),
    beginCreate: vi.fn(async () => { active = undefined; draft = { label: "" }; }),
    openExisting: vi.fn(async (key: string) => { active = key; draft = structuredClone(rows.find(row => row.key === key)!.values as Draft); }),
    fill: vi.fn(async (value: Draft) => { draft = structuredClone(value); }),
    save: vi.fn(async () => {
      if (active) rows.find(row => row.key === active)!.values = structuredClone(draft);
      else rows.push({ key: "database-generated-uuid", values: structuredClone(draft) });
    }),
    cancel: vi.fn(async () => {}),
    readDraft: vi.fn(async () => draft),
  };
  const contract: WorkflowContract<Draft> = { store, driver, timeoutMs: 45, stableForMs: 20 };
  return { rows, page: page as unknown as Page, reload: page.reload, store, driver, contract };
}

describe("portable workflow persistence assertions", () => {
  it("discovers one new identity, preserves existing values and reloads before reopening", async () => {
    const f = fixture(), expected = { label: "  Literal text  " };
    const key = await createAndReopen(f.page, f.contract, { draft: expected, expectedStored: expected, expectedDraft: expected });
    expect(key).toBe("database-generated-uuid");
    expect(f.reload).toHaveBeenCalledOnce();
    expect(f.driver.openExisting).toHaveBeenLastCalledWith(key);
    expect(f.driver.openExisting.mock.invocationCallOrder[0]).toBeGreaterThan(f.reload.mock.invocationCallOrder[0]);
    expect(f.rows[0]).toEqual({ key: first, values: { label: "Original  " } });
    expect(f.rows[1]).toEqual({ key: second, values: { label: null } });
  });

  it("checks a supplied new key and rejects an already existing identity", async () => {
    const f = fixture(), expected = { label: "Created" };
    await expect(createAndReopen(f.page, f.contract, { key: "wrong-identity", draft: expected,
      expectedStored: expected, expectedDraft: expected })).rejects.toThrow();
    const another = fixture();
    await expect(createAndReopen(another.page, another.contract, { key: first, draft: expected,
      expectedStored: expected, expectedDraft: expected })).rejects.toThrow(/Create key/);
    expect(another.driver.save).not.toHaveBeenCalled();
  });

  it("edits one row and requires an explicitly expected fresh reopened draft", async () => {
    const f = fixture(), expected = { label: "Edited  " };
    await editAndReopen(f.page, f.contract, { key: first, draft: expected, expectedStored: expected, expectedDraft: expected });
    expect(f.reload).toHaveBeenCalledOnce();
    expect(f.rows[1]).toEqual({ key: second, values: { label: null } });
  });

  it("cancels a draft, samples unchanged storage and reloads the original value", async () => {
    const f = fixture();
    await cancelEdits(f.page, f.contract, { key: first, draft: { label: "Discard" }, expectedDraft: { label: "Original  " } });
    expect(f.reload).toHaveBeenCalledOnce();
    expect(f.driver.save).not.toHaveBeenCalled();
  });

  it("requires the rejected path and preserves both draft and independent stored rows", async () => {
    const f = fixture(), rejected = vi.fn(async () => {}), invalid = { label: "" };
    f.driver.save.mockImplementation(async () => {});
    await invalidSaveUnchanged(f.page, f.contract, { draft: invalid, expectedDraft: invalid, assertRejected: rejected });
    expect(rejected).toHaveBeenCalledOnce();
    expect(f.rows).toHaveLength(2);
  });

  it("compares search matches as key sets and asserts actual selection without writing", async () => {
    const f = fixture(); let selection: string | null = null;
    const driver = { openList: f.driver.openList, search: vi.fn(async (_criteria: { literal: string }) => {}),
      readResults: async () => [second, first], select: async (key: string) => { selection = key; }, readSelection: async () => selection };
    await searchAndSelect(f.page, { ...f.contract, driver }, { criteria: { literal: "100%" },
      expectedKeys: [first, second], selectKey: second, expectedSelection: second });
    expect(driver.search).toHaveBeenCalledWith({ literal: "100%" });
  });

  it("cancels deletion first, then confirms exactly one deletion and reloads", async () => {
    const f = fixture(); let confirmation = false;
    const driver = { openList: f.driver.openList, requestDelete: vi.fn(async (_key: string) => { confirmation = true; }),
      assertConfirmation: async () => { expect(confirmation).toBe(true); },
      dismissConfirmation: async () => { confirmation = false; },
      acceptConfirmation: async () => { f.rows.splice(f.rows.findIndex(row => row.key === first), 1); confirmation = false; },
      assertConfirmationClosed: async () => { expect(confirmation).toBe(false); } };
    await deleteCancelThenConfirm(f.page, { ...f.contract, driver }, { key: first });
    expect(driver.requestDelete).toHaveBeenCalledTimes(2);
    expect(f.reload).toHaveBeenCalledOnce();
    expect(f.rows).toEqual([{ key: second, values: { label: null } }]);
  });

  it("fails a no-op create instead of trusting a save click", async () => {
    const f = fixture(), value = { label: "New" };
    f.driver.save.mockImplementation(async () => {});
    await expect(createAndReopen(f.page, f.contract, { draft: value, expectedStored: value, expectedDraft: value }))
      .rejects.toThrow(/exactly one new row/);
    expect(f.reload).not.toHaveBeenCalled();
  });

  it("fails a no-op edit even when the browser draft looks correct", async () => {
    const f = fixture(), value = { label: "Unsaved" };
    f.driver.save.mockImplementation(async () => {});
    await expect(editAndReopen(f.page, f.contract, { key: first, draft: value, expectedStored: value, expectedDraft: value }))
      .rejects.toThrow(/persisted rows differ/);
  });

  it("deep-clones the baseline and catches an extra mutated row", async () => {
    const f = fixture(), value = { label: "New" };
    f.driver.save.mockImplementation(async () => {
      (f.rows[1].values as Draft).label = "Unrelated mutation";
      f.rows.push({ key: "database-generated-uuid", values: value });
    });
    await expect(createAndReopen(f.page, f.contract, { draft: value, expectedStored: value, expectedDraft: value }))
      .rejects.toThrow(/exactly one new row/);
  });

  it("fails an invalid save that wrote despite showing rejection", async () => {
    const f = fixture(), value = { label: "" };
    await expect(invalidSaveUnchanged(f.page, f.contract, { draft: value, expectedDraft: value, assertRejected: async () => {} }))
      .rejects.toThrow(/changed persisted data/);
  });

  it("samples delayed writes after the rejected path has completed", async () => {
    const f = fixture(), value = { label: "" };
    f.contract.stableForMs = 70;
    f.driver.save.mockImplementation(async () => { setTimeout(() => { f.rows[0].values = { label: "Late invalid write" }; }, 15); });
    await expect(invalidSaveUnchanged(f.page, f.contract, { draft: value, expectedDraft: value, assertRejected: async () => {} }))
      .rejects.toThrow(/changed persisted data/);
  });

  it("latches an observed mismatch even when later reads restore the original data", async () => {
    const f = fixture(), value = { label: "" }; let reads = 0;
    f.driver.save.mockImplementation(async () => {});
    f.store.read.mockImplementation(async () => {
      reads++;
      return reads === 2 ? [{ key: first, values: { label: "Transient write" } }, f.rows[1]] : f.rows;
    });
    await expect(invalidSaveUnchanged(f.page, f.contract, { draft: value, expectedDraft: value, assertRejected: async () => {} }))
      .rejects.toThrow(/changed persisted data/);
    expect(reads).toBeGreaterThan(2);
  });

  it("rejects duplicate and numeric precision-lost identities before actions", async () => {
    for (const badKey of [first, Number("9007199254740993")]) {
      const f = fixture(), value = { label: "New" };
      f.rows[1].key = badKey as string;
      await expect(createAndReopen(f.page, f.contract, { draft: value, expectedStored: value, expectedDraft: value }))
        .rejects.toThrow(/identity|identities/);
      expect(f.driver.save).not.toHaveBeenCalled();
    }
  });

  it("rejects a stale reopened model even after the store persisted correctly", async () => {
    const f = fixture(), value = { label: "Saved" };
    f.driver.readDraft.mockImplementation(async () => ({ label: "Stale browser model" }));
    await expect(editAndReopen(f.page, f.contract, { key: first, draft: value, expectedStored: value, expectedDraft: value }))
      .rejects.toThrow(/Reopened draft/);
    expect(f.reload).toHaveBeenCalledOnce();
  });
});
