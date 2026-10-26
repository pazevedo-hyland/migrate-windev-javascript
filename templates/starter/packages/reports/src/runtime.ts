import { createHash } from "node:crypto";
import { createReadStream, constants } from "node:fs";
import { access, stat } from "node:fs/promises";
import { posix, win32 } from "node:path";
import { chromium, type Browser } from "playwright-core";
import type { ReportRenderer } from "./contracts";
import { createReportRenderer, loadReportAssets } from "./renderer";

export type ReportRuntimeConfiguration = { executablePath: string; sha256: string; version: string };
export type ReportRuntimeErrorCode = "configuration" | "executable" | "fingerprint" | "assets" | "launch" | "version";

/** Diagnostics expose fixed codes, never configured paths, environment values or browser logs. */
export class ReportRuntimeConfigurationError extends Error {
  constructor(readonly code: ReportRuntimeErrorCode) {
    super(`Report runtime configuration failed (${code})`);
    this.name = "ReportRuntimeConfigurationError";
  }
}

export function validateReportRuntimeConfiguration(input: unknown, platform: NodeJS.Platform = process.platform): ReportRuntimeConfiguration {
  if (input === null || typeof input !== "object" || Array.isArray(input)) throw new ReportRuntimeConfigurationError("configuration");
  const record = input as Record<string, unknown>, { executablePath, sha256, version } = record;
  if (Object.keys(record).sort().join(",") !== "executablePath,sha256,version"
    || typeof executablePath !== "string" || executablePath.includes("\0") || !(platform === "win32" ? win32 : posix).isAbsolute(executablePath)
    || platform === "win32" && !/^[a-z]:[\\/]/i.test(executablePath)
    || typeof sha256 !== "string" || !/^[a-f\d]{64}$/i.test(sha256)
    || typeof version !== "string" || !/^\d+\.\d+\.\d+\.\d+$/.test(version)) throw new ReportRuntimeConfigurationError("configuration");
  return { executablePath, sha256: sha256.toLowerCase(), version };
}

async function executableFingerprint(configuration: ReportRuntimeConfiguration): Promise<void> {
  try {
    if (!(await stat(configuration.executablePath)).isFile()) throw new Error();
    await access(configuration.executablePath, constants.R_OK | (process.platform === "win32" ? 0 : constants.X_OK));
  } catch { throw new ReportRuntimeConfigurationError("executable"); }
  let fingerprint: string;
  try {
    const hash = createHash("sha256");
    for await (const chunk of createReadStream(configuration.executablePath)) hash.update(chunk);
    fingerprint = hash.digest("hex");
  } catch { throw new ReportRuntimeConfigurationError("executable"); }
  if (fingerprint !== configuration.sha256) throw new ReportRuntimeConfigurationError("fingerprint");
}

/** Explicit service-host provisioning. No download, channel, cache or environment fallback.
 * Undefined configuration lets a caller keep its report feature unavailable. */
export async function createConfiguredReportRenderer(input?: ReportRuntimeConfiguration): Promise<ReportRenderer | undefined> {
  if (input === undefined) return undefined;
  const configuration = validateReportRuntimeConfiguration(input);
  await executableFingerprint(configuration);
  const assets = await loadReportAssets().catch(() => { throw new ReportRuntimeConfigurationError("assets"); });
  let browser: Browser | undefined;
  try {
    browser = await chromium.launch({ executablePath: configuration.executablePath, headless: true, timeout: 30_000 });
    if (browser.version() !== configuration.version) throw new ReportRuntimeConfigurationError("version");
  } catch (error) {
    if (error instanceof ReportRuntimeConfigurationError) throw error;
    throw new ReportRuntimeConfigurationError("launch");
  } finally { try { await browser?.close(); } catch { /* Close only the process owned by this probe. */ } }
  return createReportRenderer({ executablePath: configuration.executablePath, expectedVersion: configuration.version, assets: Promise.resolve(assets) });
}
