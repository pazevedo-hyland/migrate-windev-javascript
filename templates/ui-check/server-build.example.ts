import type { FullConfig } from "@playwright/test";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import warmup from "./warmup";

/** Build the server once per run, so the workers start the same bundle the installer embeds; then warm Vite up
 *  (its cold first load exceeds a test's navigation timeout). */
export default async function buildServer(config: FullConfig) {
  execSync("npm run server:build", { cwd: fileURLToPath(new URL("../..", import.meta.url)), stdio: "inherit" });
  await warmup(config);
}
