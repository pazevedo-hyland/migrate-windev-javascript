#!/usr/bin/env node
// Runs a Python script with the interpreter this OS provides, so npm scripts work everywhere:
//   "parity": "node scripts/py.mjs scripts/parity_check.py docs/parity/parity.csv --seed docs/parity/parity-seed.csv"
// $PYTHON wins; otherwise python3 (macOS, Linux) or py (Windows), then python.
import { spawnSync } from "node:child_process";

const candidates = process.env.PYTHON ? [process.env.PYTHON]
  : process.platform === "win32" ? ["py", "python3", "python"] : ["python3", "python"];
for (const command of candidates) {
  const run = spawnSync(command, process.argv.slice(2), { stdio: "inherit" });
  if (!run.error) process.exit(run.status ?? 1);
}
console.error(`no Python interpreter found (tried ${candidates.join(", ")}): install Python 3.10+ or set PYTHON`);
process.exit(1);
