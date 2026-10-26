import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import {
  cancelEdits, createAndReopen, deleteCancelThenConfirm, editAndReopen, invalidSaveUnchanged, searchAndSelect,
  type DeleteContract, type SearchContract, type StoredRow, type WorkflowContract,
} from "@windev-migration/testing";

type Draft = Record<string, string | boolean>;
interface Example {
  entity: "members" | "rooms"; key: string; initial: Draft; created: Draft; edited: Draft;
  invalid: Draft; error: string; search: string;
}
const examples: Example[] = [
  { entity: "members", key: "9007199254740993", initial: { name: "Alpha reader", email: "alpha@example.invalid", active: true },
    created: { name: "New d'Água  ", email: "new@example.invalid", active: false },
    edited: { name: "Edited reader  ", email: "edited@example.invalid", active: false },
    invalid: { name: "", email: "invalid@example.invalid", active: false }, error: "Name is required", search: "Alpha" },
  { entity: "rooms", key: "9007199254740995", initial: { code: "R-A", capacity: "12", notes: "Quiet room" },
    created: { code: "R-Z", capacity: "9007199254740993", notes: "Line one\nLine two  " },
    edited: { code: "R-C", capacity: "25", notes: "Updated notes  " },
    invalid: { code: "R-A", capacity: "0", notes: "Keep rejected draft" }, error: "Capacity must be a positive integer", search: "R-A" },
];

function configure(page: Page, request: APIRequestContext, example: Example) {
  const endpoint = `/__workflow_fixture/api/${example.entity}`;
  const editor = page.getByTestId("record-editor"), dialog = page.getByRole("dialog", { name: "Delete record", exact: true });
  const row = (key: string) => page.getByTestId("record-table").locator("tbody tr").filter({ has: page.getByRole("cell", { name: key, exact: true }) });
  const store = { async read(): Promise<StoredRow[]> {
    // Query the real test SQLite service, independently of the browser's local rows/drafts.
    const response = await request.get(endpoint);
    expect(response.status()).toBe(200);
    return (await response.json() as ({ id: string } & Draft)[]).map(({ id, ...values }) => ({ key: id, values }));
  } };
  const openList = async () => {
    await page.goto(`/ui-check/contracts.html?entity=${example.entity}`);
    await expect(page.getByTestId("new-record")).toBeEnabled();
    await expect(page.getByTestId("list-error")).toHaveCount(0);
  };
  const driver = {
    openList,
    async beginCreate() { await page.getByTestId("new-record").click(); await expect(editor).toBeVisible(); },
    async openExisting(key: string) { await row(key).click(); await page.getByTestId("edit-record").click(); await expect(editor).toBeVisible(); },
    async fill(draft: Draft) {
      for (const [name, value] of Object.entries(draft)) {
        const field = editor.getByTestId(`field-${name}`);
        if (typeof value === "boolean") await field.setChecked(value); else await field.fill(value);
      }
    },
    async save() {
      const [response] = await Promise.all([
        page.waitForResponse(response => response.url().includes(endpoint) && ["POST", "PATCH"].includes(response.request().method())),
        page.getByTestId("save-record").click(),
      ]);
      await response.finished();
      if (response.ok()) {
        await expect(editor).toBeHidden();
        await expect(page.getByTestId("new-record")).toBeEnabled();
      } else {
        await expect(page.getByTestId("form-error")).toBeVisible();
        await expect(page.getByTestId("save-record")).toBeEnabled();
      }
    },
    async cancel() { await page.getByTestId("cancel-record").click(); await expect(editor).toBeHidden(); },
    async readDraft(): Promise<Draft> {
      const result: Draft = {};
      for (const [name, sample] of Object.entries(example.initial)) {
        const field = editor.getByTestId(`field-${name}`);
        result[name] = typeof sample === "boolean" ? await field.isChecked() : await field.inputValue();
      }
      return result;
    },
  };
  const contract: WorkflowContract<Draft> = { store, driver };
  const search: SearchContract<string> = { store, driver: {
    openList, async search(value) { await page.getByTestId("search").fill(value); },
    async readResults() { return page.getByTestId("record-table").locator("tbody tr").evaluateAll(rows => rows.map(row => row.getAttribute("data-record-key")!)); },
    async select(key) { await row(key).click(); },
    async readSelection() { return page.getByTestId("record-table").locator('tbody tr[aria-selected="true"]').getAttribute("data-record-key"); },
  } };
  const deletion: DeleteContract = { store, driver: {
    openList, async requestDelete(key) { await row(key).click(); await page.getByTestId("delete-record").click(); },
    async assertConfirmation() { await expect(dialog).toBeVisible(); },
    async dismissConfirmation() { await page.keyboard.press("Escape"); },
    async acceptConfirmation() {
      await Promise.all([
        page.waitForResponse(response => response.url().includes(endpoint) && response.request().method() === "DELETE"),
        dialog.getByRole("button", { name: "Yes", exact: true }).click(),
      ]);
    },
    async assertConfirmationClosed() { await expect(dialog).toBeHidden(); await expect(page.getByTestId("new-record")).toBeEnabled(); },
  } };
  return { contract, search, deletion };
}

test.beforeEach(async ({ request }) => { expect((await request.post("/__workflow_fixture/reset")).status()).toBe(200); });

for (const example of examples) {
  test.describe(example.entity, () => {
    test("create and reopen checks independently persisted fields and generated identity", async ({ page, request }) => {
      const { contract } = configure(page, request, example);
      const key = await createAndReopen(page, contract, { draft: example.created, expectedStored: example.created, expectedDraft: example.created });
      expect(key).not.toBe(example.key);
    });
    test("edit and reopen changes only the selected persisted record", async ({ page, request }) => {
      await editAndReopen(page, configure(page, request, example).contract,
        { key: example.key, draft: example.edited, expectedStored: example.edited, expectedDraft: example.edited });
    });
    test("cancel edits retains the original persisted record and reopened draft", async ({ page, request }) => {
      await cancelEdits(page, configure(page, request, example).contract,
        { key: example.key, draft: example.edited, expectedDraft: example.initial });
    });
    test("invalid save retains the rejected draft and all persisted records", async ({ page, request }) => {
      await invalidSaveUnchanged(page, configure(page, request, example).contract, {
        key: example.key, draft: example.invalid, expectedDraft: example.invalid,
        async assertRejected() { await expect(page.getByTestId("form-error")).toHaveText(example.error); },
      });
    });
    test("search and selection preserve exact string identities and stored records", async ({ page, request }) => {
      await searchAndSelect(page, configure(page, request, example).search,
        { criteria: example.search, expectedKeys: [example.key], selectKey: example.key, expectedSelection: example.key });
    });
    test("delete cancellation preserves data and confirmation removes only its target", async ({ page, request }) => {
      await deleteCancelThenConfirm(page, configure(page, request, example).deletion, { key: example.key });
    });
  });
}

test("the shared create scenario detects a successful-looking response without persistence", async ({ page, request }) => {
  const example = examples[0], { contract } = configure(page, request, example);
  let attempted = 0;
  await page.route("**/__workflow_fixture/api/members", async route => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    attempted++;
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "pretend-save", ...example.created }) });
  });
  await expect(createAndReopen(page, { ...contract, timeoutMs: 300 },
    { draft: example.created, expectedStored: example.created, expectedDraft: example.created })).rejects.toThrow("Create must persist exactly one new row");
  expect(attempted).toBe(1);
  await expect(page.getByRole("cell", { name: "pretend-save", exact: true })).toBeVisible();
  expect((await contract.store.read()).map(row => row.key)).toEqual(["9007199254740993", "9007199254740994"]);
});

test("the shared rejection scenario detects a write hidden behind an error response", async ({ page, request }) => {
  const example = examples[1], { contract } = configure(page, request, example);
  let attempted = 0;
  await page.route(`**/__workflow_fixture/api/rooms/${example.key}`, async route => {
    if (route.request().method() !== "PATCH") { await route.continue(); return; }
    attempted++;
    // Fault injection: commit valid values, then lie to the browser with a rejection.
    const committed = await route.fetch({ postData: JSON.stringify(example.edited) });
    expect(committed.status()).toBe(200);
    await route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ error: example.error }) });
  });
  await expect(invalidSaveUnchanged(page, contract, {
    key: example.key, draft: example.invalid, expectedDraft: example.invalid,
    async assertRejected() { await expect(page.getByTestId("form-error")).toHaveText(example.error); },
  })).rejects.toThrow("Rejected/cancelled/read-only action changed persisted data");
  expect(attempted).toBe(1);
  expect((await contract.store.read()).find(row => row.key === example.key)?.values).toEqual(example.edited);
});
