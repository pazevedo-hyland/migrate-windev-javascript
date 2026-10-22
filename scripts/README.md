# Scripts

Python 3.10+, standard library only. No WINDEV runtime, network or AI credentials required. Run the tests with `python3 -m unittest discover -s tests -v`.

## `inspect_windev.py` — inventory, context and parity seed

```sh
python3 scripts/inspect_windev.py /absolute/path/to/project --out analysis-local/inspect-1 \
  [--fallback-encoding cp1252] [--extra-ext .wwh ...] [--block-key <key> ...]
```

Use a new output directory per run: existing output is rejected so stale and current evidence never mix. The output cannot equal or contain the source directory. The source is only read; legacy code is never executed.

**Recognized extensions** (case-insensitive): `.wdp` project, `.wdw` window, `.wde` report, `.wdr` query, `.wdg` procedure set, `.wdc` class, `.xdd` analysis export. Add others with `--extra-ext` after comparing with the project element list in WINDEV (for example WebDev pages). The walk skips symlinks, `.git`, `node_modules`, `target`, `dist`, `Backup`, `Exe`, `History`, `Groupware`, `Bkp_*` and `*.cpl` folders, and a nested output directory. This is a convenience inventory, not a guarantee of complete discovery.

**Text sources**: UTF-8 (with or without BOM) and BOM-marked UTF-16 are decoded; `--fallback-encoding` accepts an explicit codec for older non-Unicode sources. Other files are reported `binary-or-unsupported` and seeded as `export-needed`. Byte-identical copies (such as the XDD inside the `.ana` folder) are reported `duplicate` with `duplicate_of` and not seeded twice. The tool recognizes indented `code : |1-` style literal blocks, including list items written as a bare `-` line (the WINDEV 27 text format), and records, for each block:

- `start_line`/`end_line` and the relative path;
- `context.names`: ancestor `name :` values (e.g. `["WIN_Order", "BTN_Save"]`);
- `context.siblings`: scalar keys next to the block, such as the raw event `type` code — **not interpreted**. Window global declarations (`PROCEDURE MyWindow(…)`) usually have no `type`;
- `procedures`: `PROCEDURE`/`PROCÉDURE` declarations found in the block.

`literal_keys` in the inventory counts every literal block key found in a file, so other embedded sources are visible; extract them with `--block-key`. The tool does not parse the full WINDEV text format, resolve resource strings, decode internal properties or interpret numeric event identifiers.

**XDD** is parsed as XML with its declared encoding; DTD/entity declarations and non-ASCII-compatible XML are rejected. Each field's raw XML metadata and table attributes are retained, with other top-level metadata/relationships. Numeric type/key codes are deliberately not translated.

**Outputs**

- `inventory.json` — paths, kinds, sizes, SHA-256 hashes, status, block/table counts, literal keys, limitations.
- `code/<relative-source>.json` — extracted blocks with context and line references.
- `schema/<relative-source>.json` — raw table/field/relationship metadata.
- `parity-seed.csv` — one `unmapped` row per code block, table and unresolved source, with stable `SRC-*` IDs. Import it into `docs/parity/parity.csv`.
- `secret-hints.json` — `path`, `line` and hint type for likely hardcoded credentials and connection calls. **Values are never copied.** Treat findings as credentials to revoke.

Outputs contain business logic and possibly secrets: keep them local (`analysis-local/` is ignored) and sanitize before sharing.

## `parity_check.py` — the parity gate

```sh
python3 scripts/parity_check.py docs/parity/parity.csv [--seed analysis-local/inspect-1/parity-seed.csv] [--require-complete]
```

Validates columns, unique IDs, statuses and confidence values, and evidence rules (`verified` needs an executed test and cannot be `unresolved`; `excluded` needs a decision; `implemented` needs `implemented_in`). With `--seed`, every seed row must still exist. With `--require-complete`, every row must be `verified` or `excluded`. Prints a summary and exits non-zero on any error. See [10 — Parity](../10-parity-and-verification.md).

## `plan_capture.py` — unattended capture plan

```sh
python3 scripts/plan_capture.py analysis-local/inspect-1 --out analysis-local/capture-plan.json
```

Lists every window, every route that opens it (menu option or button, call and arguments, evidence) and classifies routes and windows: `navigation` / `review` / `writes` for clicks, and whether the window writes on open or close. Writes `capture-plan.json` and a `capture-plan.md` checklist. Used by the [Windows capture kit](windows/README.md), which also contains `capture_app.py` (screens) and `export_odbc.py` (data).

## `compare_exports.py` — golden master and reconciliation

```sh
python3 scripts/compare_exports.py --config docs/golden/compare.json \
  --legacy legacy/golden/GS-001/after --target analysis-local/golden/GS-001/after [--report report.json]
```

Compares CSV exports table by table using the configured key (target column names), legacy→target column renames, ignored columns, per-side delimiter/encoding, and **declared** normalizations per column: `trim` (default on), `decimal` with optional `decimal_places`, `date_formats`, `casefold`, `strip_accents`, `empty_as_null`. Reports missing/extra rows, mismatched cells, duplicate keys and missing columns; exits 1 on any difference. Example: [templates/compare.example.json](../templates/compare.example.json).
