// Example from the pilot (vehicle slice): each slice adds ui-check/<slice>.flows.spec.ts that clicks through its
// golden scenarios (docs/golden/) in browser-preview mode — the real UI on a fake backend loaded with the golden
// data. It proves the screens' behavior end to end, not the Rust commands (those have their own tests). Use the
// legacy control names as data-testid, the dialogs' alertdialog role, and the legacy texts as expectations.
import { expect, test, type Page } from "@playwright/test";

const plates = (page: Page) => page.locator('[data-testid="TABLE_Viaturas"] tbody tr').evaluateAll(
  (rows) => rows.map((r) => r.getAttribute("data-matricula")));
const dialog = (page: Page) => page.getByRole("alertdialog");

async function openVehicles(page: Page) {
  await page.goto("/");
  await page.getByTestId("NAV_Viaturas").click();
  await expect(page.getByTestId("WIN_Table_Viaturas")).toBeVisible();
}

test("list opens in order, inner join hides the orphan", async ({ page }) => {
  await openVehicles(page);
  expect(await plates(page)).toEqual(["AA-00-01", "BB-11-22", "CC-22-33", "DD-33-44", "EE-44-55"]);
});

test("search by client, apostrophe, literal %", async ({ page }) => {
  await openVehicles(page);
  await page.getByTestId("BTN_cliente").click();
  await page.getByTestId("EDT_termo_pesquisa").fill("silva");
  await expect.poll(() => plates(page)).toEqual(["AA-00-01", "BB-11-22"]);
  await page.getByTestId("EDT_termo_pesquisa").fill("D'Al");
  await expect.poll(() => plates(page)).toEqual(["CC-22-33"]);
  await expect(dialog(page)).toHaveCount(0);
  await page.getByTestId("BTN_marca_modelo").click();
  await page.getByTestId("EDT_termo_pesquisa").fill("100%");
  await expect.poll(() => plates(page)).toEqual(["EE-44-55"]);
});

test("delete is refused for a vehicle with repair orders, allowed otherwise", async ({ page }) => {
  await openVehicles(page);
  await page.locator('tr[data-matricula="AA-00-01"]').click();
  await page.getByTestId("BTN_Delete").click();
  await expect(dialog(page)).toContainText("Viatura usada em ordens de reparação, não pode ser eliminada");
  await dialog(page).getByRole("button").first().click();
  await page.locator('tr[data-matricula="DD-33-44"]').click();
  await page.getByTestId("BTN_Delete").click();
  await page.keyboard.press("Escape"); // Esc = the safe answer: nothing deleted
  await expect.poll(() => plates(page)).toContain("DD-33-44");
  await page.getByTestId("BTN_Delete").click();
  await dialog(page).getByRole("button", { name: /Sim|Delete|Apagar/i }).click();
  await expect.poll(() => plates(page)).not.toContain("DD-33-44");
});

test("new vehicle: empty check, duplicate, saved upper-case, form closes", async ({ page }) => {
  await openVehicles(page);
  await page.getByTestId("Btn_New").click();
  const form = page.getByTestId("WIN_Form_Viaturas");
  await expect(form).toBeVisible();
  await page.getByTestId("BTN_Validar").click();
  await expect(dialog(page)).toContainText("Falta indicar a matrícula");
  await dialog(page).getByRole("button").first().click();
  await expect(form).toBeVisible(); // stays open after a failed check
  await page.getByTestId("EDT_Matricula").fill("aa-00-01");
  await page.getByTestId("COMBO_Codigo").selectOption({ index: 1 });
  await page.getByTestId("EDT_Marca").fill("Fiat"); // legacy checks matrícula, cliente, marca, modelo in turn
  await page.getByTestId("EDT_Modelo").fill("Panda");
  await page.getByTestId("BTN_Validar").click();
  await expect(dialog(page)).toContainText("AA-00-01");
  await dialog(page).getByRole("button").first().click();
  await page.getByTestId("EDT_Matricula").fill("ff-55-66");
  await page.getByTestId("BTN_Validar").click();
  await expect(form).toBeHidden(); // closes after a successful save
  await expect.poll(() => plates(page)).toContain("FF-55-66");
});

test("form cancel and close box return to the list without closing the app", async ({ page }) => {
  await openVehicles(page);
  await page.locator('tr[data-matricula="BB-11-22"]').click();
  await page.getByTestId("BTN_Modificar").click();
  await expect(page.getByTestId("EDT_Matricula")).toHaveValue("BB-11-22");
  await page.getByTestId("BTN_Cancelar").click();
  await expect(page.getByTestId("WIN_Form_Viaturas")).toBeHidden();
  await page.getByTestId("BTN_Modificar").click();
  await page.getByTestId("WIN_Form_Viaturas").getByTestId("BTN_SYST_FERMER").click();
  await expect(page.getByTestId("WIN_Form_Viaturas")).toBeHidden();
  await expect(page.getByTestId("WIN_Table_Viaturas")).toBeVisible();
});
