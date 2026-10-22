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
- `dialogs` in each `code/<file>.json` — dialog boxes declared in the window resources: message and button labels per language, button values, `cancel_button` (readable, unlike control captions).
- `controls` in each `code/<file>.json` — every control and table column declared in the window or report, in source order (used by the UI control-coverage check).
- `parity-seed.csv` — one `unmapped` row per code block, table and unresolved source, with stable `SRC-*` IDs. Import it into `docs/parity/parity.csv`.
- `secret-hints.json` — `path`, `line` and hint type for likely hardcoded credentials and connection calls. **Values are never copied.** Treat findings as credentials to revoke.

Outputs contain business logic and possibly secrets: keep them local (`analysis-local/` is ignored) and sanitize before sharing.

## `parity_check.py` — the parity gate

```sh
python3 scripts/parity_check.py docs/parity/parity.csv [--seed analysis-local/inspect-1/parity-seed.csv] [--require-complete]
```

Validates columns, unique IDs, statuses and confidence values, and evidence rules (`verified` needs an executed test and cannot be `unresolved`; `excluded` needs a decision; `implemented` needs `implemented_in`). With `--seed`, every seed row must still exist. With `--require-complete`, every row must be `verified` or `excluded`. Prints a summary and exits non-zero on any error. See [10 — Parity](../10-parity-and-verification.md).

## `dossier_extract.py` — WINDEV's project documentation as data

```sh
pip install pypdf
python3 scripts/dossier_extract.py legacy/docs/<project>_Documentation.pdf --out analysis-local/dossier [--no-images]
```

WINDEV's project technical documentation states what the text sources encrypt. The extractor writes one JSON per element (`windev-window/`, `report/`, `query/`, `analysis/`, `project/`) with the raw section text plus parsed fields — window `title` and `window_type`; per control `caption`, `tab_order`, `input_mask`, `input_size`, `image`, `background_image`, `anchoring`; per query `sql`, `parameters`, `conditions`; per analysis file its description and items with `caption`, `type` as WINDEV names it ("8-byte real", "Decimal", "Automatic identifier (8 bytes)"), `size` and `default` — and each element's image under `images/`. **Checkbox properties** are read from the check marks the dossier draws (they are not text): window-level `flags` such as `Indep. HFSQL ctx.`, `Resizable`, `Title bar`, and per control `flags` from the control tables (`Visible`, `Password`, `Required input`, `Multiline`, `Blank if zero`, `NULL if empty`…). On a real WINDEV 28 project (2,303 pages): 51 windows, 28 reports, 29 queries with SQL, 106 images, in about 15 seconds. Only images actually painted on a page are taken (every page shares a resource dictionary of ~150 images). Requires `pypdf`; the other scripts stay standard-library only.

## `evidence_report.py` — is the evidence complete?

```sh
python3 scripts/evidence_report.py analysis-local/inspect-1 --dossier analysis-local/dossier --out docs/evidence-report.md [--language pt-PT]
```

Merges the inspector output and the dossier extract into one report before mapping starts:

1. **Coverage** per window, report, query and table: code blocks, controls, dossier description, captions, image, dialogs, SQL, typed items — and a list of **gaps** (missing dossier entries, undescribed controls, queries without SQL, untyped tables). Names are matched case-insensitively and by each element's internal name.
2. **Platform usage**: every WLanguage function the code calls, grouped by what the new app must provide (data access, navigation, dialogs, tables, printing, files/INI/registry, external programs, devices), with literal arguments — INI files, external programs, command-line options, printed reports.
3. **Callers** (in the JSON): for every window and report, the code lines that open or print it — mapping agents read call sites from here instead of searching; elements with no caller are listed as gaps.
4. **Runtime questions**: what only the running app can answer, one per pattern (a dialog's Esc button, whether a Validate button closes its window), grouped across windows.

On the real WINDEV 28 project: 108 elements, 4 gaps, 50 platform functions (revealing `servidor.ini`, the `WDModFic.EXE` schema update run at startup and the `"artigos"`/`"modulo"` command-line modes), 11 runtime questions.

## `event_legend.py` — event codes verified from the compile folder

```sh
python3 scripts/event_legend.py legacy/code --compile-dir legacy/code/<project>.cpl --out docs/mapping/event-codes.md
```

The text sources store events as raw codes (18, 17, 34…). The compiled per-window files in the project's `.cpl` folder contain WINDEV's own label for each coded event ("Click BTN_Save", "Exit from EDT_Name"). Pairing them where unambiguous gives a legend backed by the compiler, with evidence counts and conflicts. On a real WINDEV 28 project: 18 Click (293 matches, no conflict), 17 Whenever modifying, 16 Exit, 15 Entry, 21 Display a row, 33 Select a row, 34 End of initialization, no code = Global declarations. The inspector itself skips `.cpl` folders (they are build output, not sources).

## `render_layouts.py` — every legacy window drawn from source

```sh
python3 scripts/render_layouts.py analysis-local/inspect-1 --out analysis-local/layouts [--dossier analysis-local/dossier]
```

Draws every window to scale from the inspector's control positions (one SVG each plus `index.html`), labelled with legacy control names, or with the real captions when a dossier extract is given. No WINDEV and no running app needed: it covers every window, reachable or not.

## `compare_exports.py` — golden master and reconciliation

```sh
python3 scripts/compare_exports.py --config docs/golden/compare.json \
  --legacy legacy/golden/GS-001/after --target analysis-local/golden/GS-001/after [--report report.json]
```

Compares CSV exports table by table using the configured key (target column names), legacy→target column renames, ignored columns, per-side delimiter/encoding, and **declared** normalizations per column: `trim` (default on), `decimal` with optional `decimal_places`, `date_formats`, `casefold`, `strip_accents`, `empty_as_null`. Reports missing/extra rows, mismatched cells, duplicate keys and missing columns; exits 1 on any difference. Example: [templates/compare.example.json](../templates/compare.example.json).
