import { test as base, expect, type Page } from "@playwright/test";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

/**
 * Real-server flows for the optional server add-on (templates/server: Node procedure server + PostgreSQL/PGlite).
 * Each Playwright worker starts the built server (`dist-server/main.js`, `npm run server:build`: the same code an
 * installer embeds) with its own fresh database and the demo seed, and the app talks to it over HTTP (`?server=`), as
 * installed. Database: a real PostgreSQL when APP_TEST_DATABASE_URL is set (an admin connection string from the CI
 * environment, never Git; one database per worker, dropped afterwards), else an embedded PGlite folder in a temporary
 * directory (local runs). Tests of one worker share its database: they create their own records (unique codes) and
 * never assume counts another test could change.
 */
export interface Backend {
  url: string;
  /** Read or write the server's database directly (independent of the UI), with TEST_SESSION. */
  rpc<T = unknown>(name: string, input?: unknown): Promise<T>;
}

const root = fileURLToPath(new URL("../..", import.meta.url));
/** The session the independent reader calls procedures with: replace with your app's Session fields (an administrator). */
const TEST_SESSION = { user: "1" };

async function freshDatabase(adminUrl: string, name: string): Promise<{ url: string; drop: () => Promise<void> }> {
  const admin = new pg.Client({ connectionString: adminUrl });
  await admin.connect();
  await admin.query(`DROP DATABASE IF EXISTS ${name}`);
  await admin.query(`CREATE DATABASE ${name}`);
  await admin.end();
  const url = new URL(adminUrl);
  url.pathname = `/${name}`;
  return {
    url: url.toString(),
    drop: async () => {
      const client = new pg.Client({ connectionString: adminUrl });
      await client.connect();
      await client.query(`DROP DATABASE IF EXISTS ${name} WITH (FORCE)`);
      await client.end();
    },
  };
}

function waitForReady(child: ChildProcessWithoutNullStreams): Promise<void> {
  return new Promise((resolveReady, reject) => {
    let output = "";
    const timer = setTimeout(() => reject(new Error(`server not ready after 90 s:\n${output}`)), 90_000);
    child.stdout.on("data", (chunk: Buffer) => {
      output += chunk.toString();
      if (/^READY$/m.test(output)) {
        clearTimeout(timer);
        resolveReady();
      }
      const failed = /^FAILED (.*)$/m.exec(output);
      if (failed) {
        clearTimeout(timer);
        reject(new Error(`server failed: ${failed[1]}`));
      }
    });
    child.stderr.on("data", (chunk: Buffer) => {
      output += chunk.toString();
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`server exited (${code}):\n${output}`));
    });
  });
}

export const test = base.extend<object, { backend: Backend }>({
  backend: [
    // eslint-disable-next-line no-empty-pattern -- Playwright fixtures take their dependencies as a destructured object
    async ({}, use, workerInfo) => {
      const port = 4950 + workerInfo.parallelIndex;
      const env: NodeJS.ProcessEnv = {
        ...process.env,
        PORT: String(port),
        APP_HOST: "127.0.0.1",
        APP_STDIO_CONTROL: "1",
        APP_DEV_SEED: "1",
      };
      let cleanup = async () => {};
      if (process.env.APP_TEST_DATABASE_URL) {
        const db = await freshDatabase(process.env.APP_TEST_DATABASE_URL, `app_test_w${workerInfo.parallelIndex}`);
        env.DATABASE_URL = db.url;
        delete env.APP_DATA_DIR;
        cleanup = db.drop;
      } else {
        const dir = mkdtempSync(join(tmpdir(), "app-server-test-"));
        env.APP_DATA_DIR = join(dir, "data");
        delete env.DATABASE_URL;
        cleanup = async () => rmSync(dir, { recursive: true, force: true });
      }
      const child = spawn(process.execPath, [join(root, "dist-server", "main.js")], { cwd: root, env, stdio: "pipe" });
      await waitForReady(child);
      const url = `http://127.0.0.1:${port}`;
      const rpc = async <T>(name: string, input: unknown = {}) => {
        const response = await fetch(`${url}/rpc`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ name, input, session: TEST_SESSION }),
        });
        const result = (await response.json()) as { ok: boolean; value?: T; error?: string };
        if (!result.ok) throw new Error(`${name}: ${result.error}`);
        return result.value as T;
      };
      await use({ url, rpc });
      const exited = new Promise((done) => child.once("exit", done));
      child.stdin.end(); // APP_STDIO_CONTROL: end of stdin closes the database and exits
      await Promise.race([exited, new Promise((done) => setTimeout(done, 10_000))]);
      if (child.exitCode === null) child.kill();
      await cleanup();
    },
    { scope: "worker" },
  ],
});

export { expect };

/**
 * Open the app against this worker's server: `?server=` is how an installed station is pointed at its server.
 * `janela` (window) and `posto` (workstation) are one migration's start-up options: use your app's.
 */
export async function open(page: Page, backend: Backend, janela: string, posto = "1") {
  await page.goto(`/?server=${encodeURIComponent(backend.url)}&janela=${janela}&posto=${posto}`);
  await expect(page.getByTestId("preview-banner")).toHaveCount(0); // not the in-browser demo
}

/** Example login of one migration (its login window and demo-seed password): replace with your app's. */
export async function login(page: Page, backend: Backend) {
  await open(page, backend, "WIN_Login");
  await page.getByTestId("edt_senha").fill("admin");
  await page.getByTestId("edt_senha").press("Enter");
  await expect(page.locator('section[data-layout="WIN_MENU"]')).toBeVisible();
}
