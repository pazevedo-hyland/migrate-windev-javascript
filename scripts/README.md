# Scripts

Python 3.10+, standard library plus `pypdf` (dossier) and `pillow` (skin images, visual scores): `python3 -m pip install pypdf pillow`. No WINDEV runtime, network or AI credentials required. Run the tests with `python3 -m unittest discover -s tests -v`.

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
python3 scripts/parity_check.py docs/parity/parity.csv [--seed docs/parity/parity-seed.csv] [--element <unit>[,<unit>…]] [--require-complete] [--check-files] [--note <md>]
```

Validates columns, unique IDs, statuses and confidence values, and evidence rules (`verified` needs an executed test and cannot be `unresolved`; `excluded` needs a decision; `implemented` needs `implemented_in`). Confidence `assumed` marks rows built on a `proposed:` answer or a default ADR: they may be verified, are counted apart (`verified_on_assumptions`), and a row citing `proposed:` cannot claim `verified` confidence. With `--seed`, every seed row must still exist, and a matrix row the seed no longer has is matched to its new ID when one seed row has the same element, context and event ("rename it"). `--element` scopes every check to those units (a rule row belongs to the unit its context starts with); `--check-files` also resolves seed evidence under `legacy/`. With `--require-complete`, every row must be `verified` or `excluded`. Prints a summary and exits non-zero on any error. See [10 — Parity](../10-parity-and-verification.md).

## `data_profile.py` — what the legacy data really is

```sh
python3 scripts/data_profile.py <copy.sqlite or export_odbc folder> [--schema docs/schema/schema-draft.json] [--ref T.col=U.key] [--out docs/data/profile.md]
```

Profiles a copy of the data against the schema draft: per column nulls, empty strings, distinct values, shapes, lengths against the analysis size, values not parsing as the WINDEV type, zeros, constant columns, spaces, line breaks, binary content (composite keys); duplicates per unique key; orphans per link (named after a table or its identifier, or `--ref`), `0` counted as no link. Counts and extremes only, no records. See [08 — Data](../08-data-migration.md#profile-the-data-before-deciding-the-schema).

## `prepare_evidence.py` — the whole evidence pipeline in one command

```sh
python3 scripts/prepare_evidence.py            # defaults: legacy/, analysis-local/, docs/
```

Runs the inspector, dossier extraction, event legend, evidence report and navigation map, schema draft and layout drawings in order, into fresh dated folders, and writes their paths to `analysis-local/latest.json`. Finds the dossier PDF in `legacy/docs/` and the compile folder in `legacy/code/` itself and says when one is missing. On the real project (2,303-page dossier): about 15 seconds with `--no-images`, about 70 with images.

## `unit_evidence.py` — one unit's evidence in one JSON

```sh
python3 scripts/unit_evidence.py WIN_Table_Clientes --out analysis-local/units/WIN_Table_Clientes.json
```

Seed rows, code blocks with event meanings, encoded actions with every other slot holding the same action ID (with or without code), parsed dossier fields, callers, calls out, gaps and runtime questions for one window or report, from the paths in `analysis-local/latest.json`. The mapper starts from it; the reviewer diffs it against a newer pack to see what changed.

## `progress_dashboard.py` — migration progress for non-technical readers

```sh
python3 scripts/progress_dashboard.py --title "My App"     # writes docs/progress/index.html (+ .json)
```

One self-contained HTML page from what the process already maintains — parity matrix and seed, mapping notes and specs, answer sheet, ADRs, Git history: the share of legacy behaviors verified in the new app, screens and reports done / being built / mapped / not started, assumptions to confirm with the WINDEV expert, decisions waiting for the owner, progress over time (from the history of `docs/parity/`) and recent commits. Each stage regenerates and commits it; open it in a browser, no server needed.

## `screen_layout.py`, `skin_assets.py`, `visual_compare.py` — a screen that looks like the legacy one

```sh
python3 scripts/screen_layout.py WIN_Table_Clientes --out src/ui/legacy/WIN_Table_Clientes.layout.json
python3 scripts/skin_assets.py src/ui/legacy/*.layout.json --out public/skin   # images from legacy/images/ (00 §E); fails if one is missing
python3 scripts/visual_compare.py docs/evidence/images/WIN_Table_Clientes.jpg ui-report/WIN_Table_Clientes.png \
  --out docs/evidence/visual/WIN_Table_Clientes.compare.png --record docs/evidence/visual/WIN_Table_Clientes.json
```

Layout JSON from the evidence (positions, captions, icons and states, backgrounds, caption widths, columns); skin images as one PNG per state with magenta made transparent; a visual score (pixel similarity, edge overlap) plus a side-by-side image for the human. The last two need Pillow.

## `dossier_extract.py` — WINDEV's project documentation as data

```sh
pip install pypdf
python3 scripts/dossier_extract.py legacy/<path to>/<project>_Documentation.pdf --out <dossier dir> [--no-images]
```

WINDEV's project technical documentation states what the text sources encrypt. The extractor writes one JSON per element (`windev-window/`, `report/`, `query/`, `analysis/`, `project/`) with the raw section text plus parsed fields — window `title` and `window_type`; per control `caption`, `tab_order`, `input_mask`, `input_size`, `image`, `background_image`, `anchoring`; per query `sql`, `parameters`, `conditions`; per analysis file its description and items with `caption`, `type` as WINDEV names it ("8-byte real", "Decimal", "Automatic identifier (8 bytes)"), `size` and `default` — and each element's image under `images/`. **Checkbox properties** are read from the check marks the dossier draws (they are not text): window-level `flags` such as `Indep. HFSQL ctx.`, `Resizable`, `Title bar`, and per control `flags` from the control tables (`Visible`, `Password`, `Required input`, `Multiline`, `Blank if zero`, `NULL if empty`…), and per analysis item `keys` (`Unique Key`, `Key with Duplicates`). Tables continuing on the next page without a header and long control names cut at 31 characters are handled.

**Generic, with a check.** Positions are measured from each page's own left margin, not fixed for one project. Labels are those of an English-language WINDEV, in one place (`CONTROL_TABLE`, `KEY_TABLE`, `TEXT_COLUMNS`): a dossier printed in another UI language needs its words added there. Every run writes `coverage` to `index.json` (windows with flags, controls with captions and flags, analysis items with keys, queries with SQL) and warns on stderr when under half of a kind was recognised: then the layout or labels differ, and the missing fields are "not extracted", never false. Measured on one English WINDEV 28 dossier; other versions and languages are untested. On a real WINDEV 28 project (2,303 pages): 51 windows, 28 reports, 29 queries with SQL, 106 images, in about 15 seconds. Only images actually painted on a page are taken (every page shares a resource dictionary of ~150 images). Requires `pypdf`; the other scripts stay standard-library only.


## `schema_draft.py` — draft schema and decisions from the analysis

```sh
python3 scripts/schema_draft.py <inspect dir> --dossier <dossier dir> --out docs/schema/schema-draft.md
```

XDD structure (items, raw type codes, key type, size, default, null support) + dossier type names and captions → a type-code legend, a draft SQLite DDL that loads as is, and a list of per-column decisions for the database ADR. On the real project: 17 tables, 135 columns, 14 type codes named, 35 decisions (unsigned 8-byte codes, 8-byte reals, decimals, date/time formats); the XDD also exposed items the PDF parser missed, now fixed.

## `evidence_report.py` — is the evidence complete?

```sh
python3 scripts/evidence_report.py <inspect dir> --dossier <dossier dir> --out docs/evidence-report.md [--language pt-PT]
```

Merges the inspector output and the dossier extract into one report before mapping starts:

1. **Coverage** per window, report, query and table: code blocks, controls, dossier description, captions, image, dialogs, SQL, typed items — and a list of **gaps** (missing dossier entries, undescribed controls, queries without SQL, untyped tables). Names are matched case-insensitively and by each element's internal name.
2. **Platform usage**: every WLanguage function the code calls, grouped by what the new app must provide (data access, navigation, dialogs, tables, printing, files/INI/registry, external programs, devices), with literal arguments — INI files, external programs, command-line options, printed reports.
3. **Callers** (in the JSON): for every window and report, the code lines that open or print it — mapping agents read call sites from here instead of searching; elements with no caller are listed as gaps.
4. **Runtime questions**: what only the running app can confirm, one per pattern (a dialog's Esc button, whether a Validate button closes its window), grouped across windows. Each question and each encoded-action group carries a proposed answer with its basis (template button names, button types, the button's own code, compiled references, WINDEV conventions, or a labelled default), so work never waits for the answer sheet.

On the real WINDEV 28 project: 108 elements, 4 gaps, 50 platform functions (revealing `servidor.ini`, the `WDModFic.EXE` schema update run at startup and the `"artigos"`/`"modulo"` command-line modes), 11 runtime questions.

## `event_legend.py` — event codes verified from the compile folder

```sh
python3 scripts/event_legend.py legacy/<project folder> --compile-dir legacy/<project folder>/<project>.cpl --out docs/mapping/event-codes.md
```

The text sources store events as raw codes (18, 17, 34…). The compiled per-window files in the project's `.cpl` folder contain WINDEV's own label for each coded event ("Click BTN_Save", "Exit from EDT_Name"). Pairing them where unambiguous gives a legend backed by the compiler, with evidence counts and conflicts. On a real WINDEV 28 project: 18 Click (293 matches, no conflict), 17 Whenever modifying, 16 Exit, 15 Entry, 21 Display a row, 33 Select a row, 34 End of initialization, no code = Global declarations. The inspector itself skips `.cpl` folders (they are build output, not sources).

## `render_layouts.py` — every legacy window drawn from source

```sh
python3 scripts/render_layouts.py <inspect dir> --out <layouts dir> [--dossier <dossier dir>]
```

Draws every window to scale from the inspector's control positions (one SVG each plus `index.html`), labelled with legacy control names, or with the real captions when a dossier extract is given. No WINDEV and no running app needed: it covers every window, reachable or not.

## `compare_exports.py` — golden master and reconciliation

```sh
python3 scripts/compare_exports.py --config docs/golden/compare.json \
  --legacy legacy/golden/GS-001/after --target analysis-local/golden/GS-001/after [--report report.json]
```

Compares CSV exports table by table using the configured key (target column names), legacy→target column renames, ignored columns, per-side delimiter/encoding, and **declared** normalizations per column: `trim` (default on), `decimal` with optional `decimal_places`, `date_formats`, `casefold`, `strip_accents`, `empty_as_null`. Reports missing/extra rows, mismatched cells, duplicate keys and missing columns; exits 1 on any difference. Example: [templates/compare.example.json](../templates/compare.example.json).
