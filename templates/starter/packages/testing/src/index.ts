import { expect, type Page } from "@playwright/test";

/** Project values explicitly: no trimming, numeric coercion, sorting rules or NULL conversion. */
export interface StoredRow { key: string; values: unknown }
export interface Store { read(): Promise<readonly StoredRow[]> }
export interface WorkflowDriver<Draft> {
  openList(): Promise<void>;
  beginCreate(): Promise<void>;
  openExisting(key: string): Promise<void>;
  fill(draft: Draft): Promise<void>;
  save(): Promise<void>;
  cancel(): Promise<void>;
  readDraft(): Promise<Draft>;
}
/** Stability is a bounded sampling window after the driver's settled action, not an unlimited guarantee. */
interface Timing { timeoutMs?: number; stableForMs?: number }
export interface WorkflowContract<Draft> extends Timing { store: Store; driver: WorkflowDriver<Draft> }
export interface SaveCase<Draft> { key: string; draft: Draft; expectedStored: unknown; expectedDraft: Draft }
export type CreateCase<Draft> = Omit<SaveCase<Draft>, "key"> & { key?: string };
export interface CancelCase<Draft> { key: string; draft: Draft; expectedDraft: Draft }
export interface InvalidCase<Draft> {
  key?: string; draft: Draft; expectedDraft: Draft;
  /** Await the actual rejection/error path, including its response or dialog, before returning. */
  assertRejected(): Promise<void>;
}
export interface SearchDriver<Criteria> {
  openList(): Promise<void>;
  search(criteria: Criteria): Promise<void>;
  readResults(): Promise<readonly string[]>;
  select(key: string): Promise<void>;
  readSelection(): Promise<string | null>;
}
export interface SearchContract<Criteria> extends Timing { store: Store; driver: SearchDriver<Criteria> }
export interface SearchCase<Criteria> {
  criteria: Criteria; expectedKeys: readonly string[]; selectKey: string; expectedSelection: string;
}
export interface DeleteDriver {
  openList(): Promise<void>;
  requestDelete(key: string): Promise<void>;
  assertConfirmation(): Promise<void>;
  dismissConfirmation(): Promise<void>;
  acceptConfirmation(): Promise<void>;
  assertConfirmationClosed(): Promise<void>;
}
export interface DeleteContract extends Timing { store: Store; driver: DeleteDriver }

function keys(values: readonly string[]): string[] {
  if (!Array.isArray(values) || values.some(key => typeof key !== "string" || key.length === 0))
    throw new Error("Store/result identities must be nonempty strings; numeric IDs can lose precision");
  if (new Set(values).size !== values.length) throw new Error("Duplicate store/result identity");
  return [...values].sort();
}
function ordered(rows: readonly StoredRow[]): StoredRow[] {
  const order = keys(rows.map(row => row.key));
  const byKey = new Map(rows.map(row => [row.key, row]));
  return order.map(key => byKey.get(key)!);
}
async function snapshot(store: Store): Promise<StoredRow[]> {
  const rows: unknown = structuredClone(await store.read());
  if (!Array.isArray(rows) || rows.some(row => !row || typeof row !== "object" || !Object.hasOwn(row, "values")))
    throw new Error("Independent store.read() must return rows with key and values");
  return ordered(rows);
}
function timing(contract: Timing) {
  const timeout = contract.timeoutMs ?? 5000, stable = contract.stableForMs ?? 100;
  if (!Number.isFinite(timeout) || timeout <= 0 || !Number.isFinite(stable) || stable <= 0)
    throw new Error("Workflow timeouts and stability duration must be positive");
  return { timeout, stable, intervals: [10, 25, 50, 100] };
}
async function persisted(store: Store, expected: readonly StoredRow[], contract: Timing) {
  const { timeout, intervals } = timing(contract);
  await expect.poll(() => snapshot(store), { timeout, intervals, message: "Independent persisted rows differ" })
    .toStrictEqual(ordered(expected));
}
async function stable(store: Store, before: readonly StoredRow[], contract: Timing) {
  const { timeout, stable: duration, intervals } = timing(contract), until = Date.now() + duration;
  let failure: { error: unknown } | undefined;
  // Latch every observed mismatch/read failure so retries or restoration cannot hide a write.
  await expect.poll(async () => {
    try { expect(await snapshot(store), "Rejected/cancelled/read-only action changed persisted data").toStrictEqual(before); }
    catch (error) { failure ??= { error }; }
    return Date.now() >= until;
  }, { timeout: Math.max(timeout, duration + 100), intervals, message: "Store must remain unchanged after the settled action" }).toBe(true);
  if (failure) throw failure.error;
}
function existing(before: readonly StoredRow[], key: string) {
  keys([key]);
  expect(before.some(row => row.key === key), `Existing key ${key}`).toBe(true);
}
async function reopen<Draft>(page: Page, driver: WorkflowDriver<Draft>, key: string, expected: Draft) {
  await page.reload();
  await driver.openList();
  await driver.openExisting(key);
  expect(await driver.readDraft() as unknown, "Reopened draft must come from the saved model").toStrictEqual(expected);
}

/** Returns the database-generated identity, or checks the explicit supplied identity. */
export async function createAndReopen<Draft>(page: Page, contract: WorkflowContract<Draft>, testCase: CreateCase<Draft>): Promise<string> {
  const before = await snapshot(contract.store), test = structuredClone(testCase), { driver, store } = contract;
  if (test.key !== undefined) {
    keys([test.key]);
    expect(before.some(row => row.key === test.key), "Create key must be new").toBe(false);
  }
  await driver.openList(); await driver.beginCreate(); await driver.fill(test.draft); await driver.save();
  let created: StoredRow | undefined;
  const originalKeys = new Set(before.map(row => row.key)), { timeout, intervals } = timing(contract);
  await expect.poll(async () => {
    const after = await snapshot(store), added = after.filter(row => !originalKeys.has(row.key));
    created = added.length === 1 ? added[0] : undefined;
    return { added: added.length, keyMatches: test.key === undefined || created?.key === test.key,
      values: created?.values, unchanged: after.filter(row => originalKeys.has(row.key)) };
  }, { timeout, intervals, message: "Create must persist exactly one new row without changing existing rows" })
    .toStrictEqual({ added: 1, keyMatches: true, values: test.expectedStored, unchanged: before });
  if (!created) throw new Error("Create did not establish an identity");
  await reopen(page, driver, created.key, test.expectedDraft);
  await persisted(store, [...before, { key: created.key, values: test.expectedStored }], contract);
  return created.key;
}

export async function editAndReopen<Draft>(page: Page, contract: WorkflowContract<Draft>, testCase: SaveCase<Draft>): Promise<void> {
  const before = await snapshot(contract.store), test = structuredClone(testCase), { driver, store } = contract;
  existing(before, test.key);
  await driver.openList(); await driver.openExisting(test.key); await driver.fill(test.draft); await driver.save();
  const expected = before.map(row => row.key === test.key ? { key: row.key, values: test.expectedStored } : row);
  await persisted(store, expected, contract);
  await reopen(page, driver, test.key, test.expectedDraft);
  await persisted(store, expected, contract);
}

export async function cancelEdits<Draft>(page: Page, contract: WorkflowContract<Draft>, testCase: CancelCase<Draft>): Promise<void> {
  const before = await snapshot(contract.store), test = structuredClone(testCase), { driver, store } = contract;
  existing(before, test.key);
  await driver.openList(); await driver.openExisting(test.key); await driver.fill(test.draft); await driver.cancel();
  await stable(store, before, contract);
  await reopen(page, driver, test.key, test.expectedDraft);
  await persisted(store, before, contract);
}

export async function invalidSaveUnchanged<Draft>(_page: Page, contract: WorkflowContract<Draft>, testCase: InvalidCase<Draft>): Promise<void> {
  const before = await snapshot(contract.store), draft = structuredClone(testCase.draft), expected = structuredClone(testCase.expectedDraft);
  const { driver, store } = contract;
  if (testCase.key !== undefined) existing(before, testCase.key);
  await driver.openList();
  if (testCase.key === undefined) await driver.beginCreate(); else await driver.openExisting(testCase.key);
  await driver.fill(draft); await driver.save(); await testCase.assertRejected();
  expect(await driver.readDraft() as unknown, "Rejected form draft").toStrictEqual(expected);
  await stable(store, before, contract);
}

export async function searchAndSelect<Criteria>(_page: Page, contract: SearchContract<Criteria>, testCase: SearchCase<Criteria>): Promise<void> {
  const before = await snapshot(contract.store), test = structuredClone(testCase), { driver, store } = contract;
  const expected = keys(test.expectedKeys);
  for (const key of expected) existing(before, key);
  expect(expected.includes(test.selectKey), "Selected key must match the explicit search result").toBe(true);
  await driver.openList(); await driver.search(test.criteria);
  const { timeout, intervals } = timing(contract);
  await expect.poll(async () => keys(await driver.readResults()), { timeout, intervals }).toStrictEqual(expected);
  await driver.select(test.selectKey);
  await expect.poll(() => driver.readSelection(), { timeout, intervals }).toBe(test.expectedSelection);
  await stable(store, before, contract);
}

export async function deleteCancelThenConfirm(page: Page, contract: DeleteContract, testCase: { key: string }): Promise<void> {
  const before = await snapshot(contract.store), { driver, store } = contract;
  existing(before, testCase.key);
  await driver.openList(); await driver.requestDelete(testCase.key); await driver.assertConfirmation();
  await driver.dismissConfirmation(); await driver.assertConfirmationClosed();
  await stable(store, before, contract);
  await driver.requestDelete(testCase.key); await driver.assertConfirmation();
  await driver.acceptConfirmation(); await driver.assertConfirmationClosed();
  const expected = before.filter(row => row.key !== testCase.key);
  await persisted(store, expected, contract);
  await page.reload(); await driver.openList();
  await persisted(store, expected, contract);
}
