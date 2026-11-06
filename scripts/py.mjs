#!/usr/bin/env node
// Runs a Python script with the interpreter this OS provides, so npm scripts work everywhere:
//   "parity": "node scripts/py.mjs scripts/parity_check.py docs/parity/parity.csv --seed docs/parity/parity-seed.csv"
// $PYTHON wins; otherwise python3 (macOS, Linux) or py (Windows), then python.
import { spawnSync } from "node:child_process";

// On Windows, `py -3`: plain `py script.py` follows the script's `#!/usr/bin/env python3` line and may start
// another (older) interpreter without the packages installed for Python 3.
const candidates = process.env.PYTHON ? [[process.env.PYTHON]]
  : process.platform === "win32" ? [["py", "-3"], ["python3"], ["python"]] : [["python3"], ["python"]];
for (const [command, ...prefix] of candidates) {
  const run = spawnSync(command, [...prefix, ...process.argv.slice(2)], { stdio: "inherit" });
  if (!run.error) process.exit(run.status ?? 1);
}
console.error(`no Python interpreter found (tried ${candidates.map(c => c.join(" ")).join(", ")}): install Python 3.10+ or set PYTHON`);
process.exit(1);
