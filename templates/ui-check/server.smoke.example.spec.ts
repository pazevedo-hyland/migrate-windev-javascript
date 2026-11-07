// Example from the Gestão de Produção migration: replace the windows, codes and procedure names with your app's.
import { expect, login, open, test } from "./server-fixtures.example";

/**
 * The product path the preview flows skip: Chrome → HTTP /rpc → the built server → its database (PostgreSQL on CI).
 * Few tests on purpose: the behaviour is covered by ui-check/app; these prove the layers between work and persist.
 */
const rows = (page: import("@playwright/test").Page, table: string) =>
  page.getByTestId(table).locator("tbody tr, [role=row]:not(:has([role=columnheader]))");

test("login through the server opens the menu and its dashboard", async ({ page, backend }) => {
  await login(page, backend);
  await expect(page.getByTestId("IW_mensagens")).toBeVisible();
});

test("a brand saved in the UI is in the server's database and in a new session", async ({ page, backend, browser }) => {
  const codigo = `T${String(Date.now()).slice(-6)}`;
  await login(page, backend);
  const menu = page.locator('section[data-layout="WIN_MENU"]');
  for (const name of ["OPT_Tabelas", "Marcas"]) await menu.getByTestId(name).click();
  await page.getByTestId("Btn_novo").click();
  await page.getByTestId("EDT_codigo").fill(codigo);
  await page.getByTestId("EDT_descricao").fill("Marca do servidor");
  await page.getByTestId("BTN_gravar").click();
  await expect(page.getByTestId("EDT_codigo")).toHaveCount(0);
  await expect(rows(page, "TABLE_marcas").filter({ hasText: codigo })).toHaveCount(1);
  // Independent reader: the server's database, not the screen.
  const stored = await backend.rpc<{ codigo: string; descricao: string }[]>("marcas.list");
  expect(stored.find((row) => row.codigo === codigo)?.descricao).toBe("Marca do servidor");
  // Another station (new browser context) sees it.
  const other = await (await browser.newContext({ locale: "pt-PT" })).newPage();
  await login(other, backend);
  for (const name of ["OPT_Tabelas", "Marcas"]) await other.locator('section[data-layout="WIN_MENU"]').getByTestId(name).click();
  await expect(rows(other, "TABLE_marcas").filter({ hasText: codigo })).toHaveCount(1);
  await other.context().close();
});

test("front office over HTTP: post header, collaborators and orders of the post", async ({ page, backend }) => {
  await open(page, backend, "WIN_main_frontOffice", "71");
  const fo = page.locator('section[data-layout="WIN_main_frontOffice"]');
  await expect(fo.getByTestId("stc_mensagem")).toHaveText("POSTO FRONT OFFICE");
  await expect(rows(page, "TABLE_colaboradores").filter({ hasText: "Rui FO" })).toHaveCount(1);
  await expect(rows(page, "Table_ordens_decorrer").filter({ hasText: "FO-A1" })).toHaveCount(1);
});
