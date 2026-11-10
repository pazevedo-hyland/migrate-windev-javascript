# Scripts

## Reusable project and RAD screens

`python3 scripts/create_project.py ../my-app --name my-app` creates the [runnable starter](../templates/starter/README.md) in a new directory. Optional `--layouts <directory> --language <code>` consumes extracted layout JSON. `python3 scripts/generate_screens.py --input <layout-file-or-directory> --output <app>/src/generated --language <code>` regenerates declared outputs only; edited or unexpected files cause refusal. Inputs remain untouched. Unknown metadata stays diagnostic, strings stay data, handwritten adapters remain outside generated files. This automates screen structure, not SQL, business events or acceptance. See `--help` for both commands.

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

**Binary-format elements.** A window, report, class or procedure set saved in WINDEV's binary format is read through `windev_decode.py` (status `binary-decoded`): code blocks with their control and event in `code/<file>.json`, a listing in `listing/<file>.wl` that the blocks' line numbers and the seed rows' evidence refer to, controls and layout for a window. Its `export-needed` seed row stays (same ID); the code rows are added. Skin templates (`Templates/`) are not read this way.

`literal_keys` in the inventory counts every literal block key found in a file, so other embedded sources are visible; extract them with `--block-key`. The tool does not parse the full WINDEV text format, resolve resource strings or interpret numeric event identifiers; `windev_decode.py` decodes the internal properties.

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

## `windev_decode.py` — designer properties and binary files, without WINDEV

```sh
python3 scripts/windev_decode.py legacy/<project folder> --out analysis-local/decoded-1 [--dossier <dossier dir>] [--evidence] [--encoding cp1252] [--raw] [--blocks]
```

Decodes every `internal_properties` value of the text sources (base64 → fixed-key byte cipher → LZW → property chunks) and every packed block of the binary `PCS` files (`.WDR`, `.wdp`, `.wda`, `.cpl` copies, `.cache`). Standard library only; a new output directory per run; the source is only read.

- `properties/<source>.json` — per element: `owner` (`window`, `controls`, `columns`, `blocks`, `options`…), `name`, `type`, `parents`, each chunk's id, version, size and `strings`, and `fields` where the layout is known: window controls (`x`, `y`, `width`, `height`, `window_x`/`window_y` except inside table cells, `visible`, `state`, `caption`, `tooltip`, `initial_value`, `anchor`, `anchor_rates`, `linked_item`, `tab_stop`, `tab_order`, `group`, `popup_menu`, `double_click_button`, `button_type`, `plane`, a button's `image`, `background_image` and `background_states`, a tab's `pane_top`; `kind`, `pane`, `fonts` (face, height, weight, colour) and learned `properties` beside them), tab panes and options (`caption`), embedded queries (`sql`), windows (size, `title`), table columns (`width`, `caption`), report bands and controls (`x_mm`, `y_mm`, `width_mm`, `height_mm`). A field list cut short by an unknown layout carries `partial`; a value that does not decode carries `error` and no fields.
- `containers/<file>.json` — each unpacked block: offset, sizes, hash, its strings, `kind` (`sql`, `image`) when recognised. `queries.json` — query name → SQL. `images/` — thumbnails as BMP. `--blocks` saves every block; `--raw` keeps chunks as hex for mapping more fields.
- `evidence/` (with `--evidence`) — the decoded values in the dossier extract's shape, written over a copy of `--dossier` when given: decoded captions, titles, geometry, tab order, state, Visible, button type and images, anchors and SQL replace the PDF's (listed per control in `decoded`; a query keeps the PDF's text as `sql_pdf`), the rest of the dossier stays as the fallback, and elements the dossier lacks get entries. `prepare_evidence.py` records this folder as `dossier` in `latest.json` (the PDF extract as `dossier_pdf`), so the report, layout and unit tools read decoded values without change. `inspect_windev.py` also fills its `layout` geometry from the same decoding when the source has none readable (`layout_source: internal_properties`).
- `project/` — from a binary `.wdp`: the project's own code as text (`<project>.code.wl`: global declarations and initialisation, empty lines restored), and `project.json` with the project explorer's folders (`folders`: how the authors grouped windows, reports and classes) and, from the `.wdu` file, the files each element uses (`used_files`).
- Per kind of control, read exactly and checked against the dossier: an edit's `input_type`, `input_size`, `input_mask`, `return_format`, `h_align`, `caption_width`; a static's `h_align`/`v_align`; a button's `image_states` and `background_stretch`; every control's skin `style`; a column's `h_align`, `index`, `linked_item` and five options, and its cell (owner `content`) with the input type and mask; a report's type, data source, page and margins; a band's `band`; a report control's `kind`. `frames` (border type, background and border colours) are read by shape and not checked.
- `skin/<skin>.json` — the styles of each skin template found in the project (`.sty`): per style its fonts (face, size, weight, colour, alignment), frames and image files. A control's `style` names one (`170 AquaBlue.BTN_Ok`); `differs_from_style` on the control lists what it changed from it.
- A window's `opening_mode`, `title_bar`, `system_menu`, `minimize_icon`, `maximize_icon`, `independent_hfsql_context`, `background_image`; a list's or combo's `source`, `initial_content`, `browsed_file`, `browsed_item`, `displayed_item`, `stored_item`; a query's `parameter_names` in the evidence folder.
- `predefined_actions` of a window in the evidence folder: control, the element its action names, the action's kind. `evidence_report.py` counts them as callers and proposes them for the encoded action (`Print RPT_X`).
- A window in binary format with no text source of its name is read too (`"format": "binary"` in its properties file): its controls, columns, cells, combo lists, panes and options with type, parents and the same fields, and `code/<file>.wl` / `.json` with its code blocks, each with its control and event number (also for binary reports, classes and procedure sets). A binary report gives its page, bands, controls and linked items; a binary window its menu options and the predefined actions that name an element.
- `analysis.json` — the analysis file (`.wda`): `tables` lists every data file with its items (name, caption, type code, size, key, parts of a composite key, default, digits of a decimal, how a text key compares, position in the record, who created it and when, deleted or not). `schema_draft.py --decoded` takes captions and decimal digits from it, and the whole structure when there is no `.xdd`; `hfsql_read.py` takes the record layout from it.
- `index.json` — `coverage` (values decoded and failed, controls with fields and captions, report controls with geometry, containers, blocks, queries, images) and, with `--dossier`, `calibration`: per field, how many decoded values equal the dossier's.

On the real project: 3,993 of 3,993 values decoded; against its dossier, size 1,144/1,144, window position 1,126/1,126, Visible 802/802, tab order 1,034/1,034, state 1,081/1,081, button type 589/589, button images 588/589, anchor rates 1,130/1,130, captions 819/820 (with the accents the PDF lost), window titles 112/112, report geometry 493/493; 5 of 5 query SQL texts. With no PDF at all, the pipeline's layout of a 77-control window equals the dossier-validated one on geometry, kinds, anchors, tab order, state, Visible and button images. Offsets were measured on file format 25: on another version check `coverage` and `calibration` first. Format, limits and how the key was obtained: [docs/windev-file-formats.md](../docs/windev-file-formats.md).

## `windev_fieldmap.py` — more properties from a dossier sample, and what is still unexplained

```sh
python3 scripts/windev_fieldmap.py learn legacy/<project folder> --dossier <dossier dir> --out fieldmap.json [--base <map>] [--shareable]
python3 scripts/windev_fieldmap.py audit legacy/<project folder> [--map fieldmap.json] --out audit.json
```

`learn` finds, for each property the dossier prints, the byte position that explains it in every control of a kind, and tests it on windows left out of the learning: `strong` entries predicted them all (at least 8) and are the only position that fits; `weak` ones are kept apart and not applied. A dossier of some windows is enough; the result completes `--base` (default `scripts/windev_fieldmap.json`, learned on the real project: an edit's input type, calendar button and return format, a table's row height and options, column options). `--shareable` keeps strong entries only, so the file holds no word of the application. `windev_decode.py` applies a map (`--fieldmap`) as `properties` on each element and writes the same audit as `audit.json`: per element, the bytes that differ from the usual value of its kind and that nothing explains. `prepare_evidence.py` learns when a dossier exists and passes the map on. On the real project: 14 strong and 79 weak properties; 262 of 1,148 window controls without any unexplained difference, a median of 3 for the others. Method and limits: [docs/extraction-strategy.md](../docs/extraction-strategy.md).

## `code_map.py` — what the code touches

```sh
python3 scripts/code_map.py <inspect dir> [--decoded <decoded dir>] --out docs/code-map.md      # run by prepare_evidence.py
```

Per unit, from the code blocks (a text search, with `path:line` sites): tables **read**, **written** (`HAdd`, `HModify`, SQL `INSERT`/`UPDATE`), **deleted**, **assigned** (`File.Item = …`) and **bound** to controls without code (decoded linked items); named queries used and the tables they bring; procedures of other units called; windows opened and reports printed; classes used; project globals and constants used. Per table: its readers, writers and deleters. Per procedure: where it is defined and which units call it. With `--decoded`, the project's own code is a unit too when the `.wdp` is binary (`<project> (project code)`), and SQL of queries comes from `queries.json`.

Three lists say what a text search cannot see: `dynamic` (a name built at run time: `{sTable}` indirection, SQL assembled elsewhere, `HDeclareExternal`), `unknown_tables` (names in SQL that are no table of the analysis: another database), and procedures no other unit calls (called by an event, by name, or dead). Read those before deciding a slice's order or leaving anything out. On the real project: 149 units, all 32 tables referenced, 34 units changing data, 152 procedures, 46 project globals, 296 dynamic sites (62 in one front-office window, 50 in the class talking to another database).

## `audit_decisions.py` — every unexplained difference gets an answer

```sh
python3 scripts/audit_decisions.py --init                                  # one row per control with differences
python3 scripts/audit_decisions.py --unit WIN_Order                       # what is undecided for a unit
python3 scripts/audit_decisions.py --require-complete [--unit WIN_Order]  # exit 1 while a row has no decision
```

Keeps `docs/evidence/audit-decisions.csv` (`unit, control, differences, decision`) against the decoder's `audit.json` (path from `analysis-local/latest.json`, or `--audit`). Rows are only added, never rewritten; a decided row whose differences changed since (sources or field map changed) is reported `stale` and counts as undecided. Use it as the gate before a screen is called done.

## `parity_check.py` — the parity gate

```sh
python3 scripts/parity_check.py docs/parity/parity.csv [--seed docs/parity/parity-seed.csv] [--element <unit>[,<unit>…]] [--require-complete] [--check-files] [--note <md>]
```

Validates columns, unique IDs, statuses and confidence values, and evidence rules (`verified` needs an executed test and cannot be `unresolved`; `excluded` needs a decision; `implemented` needs `implemented_in`). Confidence `assumed` marks rows built on a `proposed:` answer or a default ADR: they may be verified, are counted apart (`verified_on_assumptions`), and a row citing `proposed:` cannot claim `verified` confidence. With `--seed`, every seed row must still exist, and a matrix row the seed no longer has is matched to its new ID when one seed row has the same element, context and event ("rename it"). `--element` scopes every check to those units (a rule row belongs to the unit its context starts with); `--check-files` also resolves seed evidence under `legacy/`. With `--require-complete`, every row must be `verified` or `excluded`. Prints a summary and exits non-zero on any error. See [10 — Parity](../10-parity-and-verification.md).

## `hfsql_read.py` — the data, without a driver

```sh
python3 scripts/hfsql_read.py <copy of the data folder> --analysis legacy/<project>/<project>.ana/<project>.wda --out legacy/data
```

Reads HFSQL Classic `.fic` and `.mmo` files directly and writes what `windows/export_odbc.py` writes: `data.sqlite`, one CSV per data file and `manifest.json` (rows, columns, deleted records skipped, files not read and why). No WINDEV, no HFSQL ODBC driver, any operating system. The record layout comes from the analysis file, so use the analysis the data was written with (the `.wda` next to the data when there is one).

It refuses rather than guesses: a file whose records are not the length the analysis gives (not rebuilt after the analysis changed, compressed, or encrypted) is listed under `not_read`, and the command ends with an error naming it. Item types it was not measured on are written as `base64:` of the stored bytes. On the measured project every value of 29 files equals what the HFSQL ODBC driver returns (224,567 values); details in [windev-file-formats.md](../docs/windev-file-formats.md). Use the ODBC route for what it refuses, and to cross-check once when both are available.

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

Seed rows, code blocks with event meanings, encoded actions with every other slot holding the same action ID (with or without code), parsed dossier fields, the unit's unexplained differences, fonts and embedded query SQL from the decoder, its entry of the code map (tables read and written with sites, queries, calls, globals, dynamic sites), callers, calls out, gaps and runtime questions for one window or report, from the paths in `analysis-local/latest.json`. The mapper starts from it; the reviewer diffs it against a newer pack to see what changed.

## `progress_dashboard.py` — migration progress for non-technical readers

```sh
python3 scripts/progress_dashboard.py --title "My App"     # writes docs/progress/index.html (+ .json)
```

One self-contained HTML page: functional acceptance first, then implementation coverage, proven behaviors, strict completion, source questions, platform evidence and recent commits. The matrix, seed, mapping notes, answer sheet and ADRs retain their roles. History remains strict completion (verified + approved exclusions); Windows and macOS visual measurements stay separate. Without an acceptance inventory the functional headline is unassessed, never inferred from built links. Each stage regenerates and commits the page; open it in a browser, no server needed.

## `functional_acceptance.py` — optional target acceptance gate

```sh
python3 scripts/functional_acceptance.py --check
python3 scripts/functional_acceptance.py --require-complete
```

Start from [the pending example](../templates/functional-acceptance.template.json), remap its units and declare the complete required workflow scope in `docs/functional-acceptance.json`. Version 1 contains `cases`, `runs` and separate `platform` capabilities. Cases use exact check file/title pairs; runs attest successful `file::title` checks, commands, OS and tested commit. Pending cases require a concrete `gap`. Record real executions before adding evidence or marking a case `verified`; the tool validates attestations, not whether tests assert the whole requirement.

Missing screens/reports create pending unassessed gaps. Stale run evidence becomes pending without changing the ledger or strict parity CSV. Cited tests and `CODE_PATHS` are compared against the tested ancestor commit, including untracked inputs. Adapt those paths to the actual project's application, assets, configuration, golden/runtime fixtures and native probes; ordinary report/status documentation can change without invalidating proof. `--require-complete` fails until every required functional case passes; platform capabilities retain their own OS-specific status and never change this denominator.

## `functional_cases.py` — acceptance cases from one executed run

```sh
npx vitest run --reporter=json --outputFile=vitest.json
npx playwright test --reporter=json > playwright.json
python3 scripts/functional_cases.py --vitest vitest.json --playwright playwright.json --commit "$(git rev-parse HEAD)" \
  --os "Windows 11 x64" --command "npx vitest run ..." --command "npx playwright test ..."
python3 scripts/functional_acceptance.py --check
```

Writes `docs/functional-acceptance.json` with one case per screen/report (`FC-<unit>`) whose witnesses are the `file::title` tests cited by the unit's `verified` parity rows, and one run (OS, commit, commands, the checks that passed). A case is `verified` only when every cited test is in the reports and passed (last retry counts); a failing or absent cited test, or a unit with no cited test, stays `pending` with the reason. Other cases (IDs not starting `FC-`), `platform` entries and the runs they cite are kept. Produce the reports from one clean commit. It derives cases from parity citations; it does not decide the approved scope — review the generated requirements, and keep strict parity, source questions and platform evidence separate.

## `merge_parity.py` — one parity file per unit, one aggregate

```sh
python3 scripts/merge_parity.py docs/parity [--exclude WIN_Old=docs/decisions/002-scope.md ...] [--check]
```

Rebuilds `docs/parity/parity.csv` from the per-unit CSVs beside it (`<UNIT>.csv`, same columns), so parallel workers each write their own unit's file and nobody overwrites the aggregate. Unit rows replace aggregate rows with the same id; rows that only live in `parity.csv` are kept; an id in two unit files or an unknown column is an error and nothing is written. `--exclude` re-applies accepted exclusions after the merge. Order: seed first, then the other ids sorted. `--check` writes nothing and exits 1 when the aggregate is stale. Run `parity_check.py` after it.

## `screen_layout.py`, `skin_assets.py`, `visual_compare.py` — a screen that looks like the legacy one

```sh
python3 scripts/screen_layout.py WIN_Table_Clientes --out src/ui/legacy/WIN_Table_Clientes.layout.json
python3 scripts/skin_assets.py src/ui/legacy/*.layout.json --out public/skin   # images from legacy/images/ (00 §E); fails if one is missing
python3 scripts/visual_compare.py docs/evidence/images/WIN_Table_Clientes.jpg ui-report/WIN_Table_Clientes.png \
  --out docs/evidence/visual/WIN_Table_Clientes.compare.png --record docs/evidence/visual/WIN_Table_Clientes.json
```

Layout JSON from the evidence (positions, captions, icons and states, backgrounds, caption widths, columns); skin images as one PNG per state with magenta made transparent; a visual score (pixel similarity, edge overlap) plus a side-by-side image for the human. The last two need Pillow. It also reads the dossier's raw control tables: geometry of controls whose names the tables cut, table column widths and the kind of generically named controls (`geometry_source`, `width_source`, `source_kind`). It joins words the PDF wrapped when the dossier or source code attests the joined word (listed in `diagnostics`), and renames kinds to the RAD kit's spelling. What the tables do not state stays missing and is listed in `unknown`, never invented.

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

With `--decoded <windev_decode.py output>` the draft also takes from the analysis file (`.wda`) each item's caption, the digits of each decimal (`Decimal (10+6 digits)`: the scale question is answered) and how each text key compares (ignoring case and accents, or also spaces and punctuation — a decision for the target's unique indexes and lookups). When the project has no `.xdd`, the whole structure comes from the analysis file: on the second project that draft equals the one made from the `.xdd` on every field (32 tables, 252 columns, 2,268 fields). Null support is not read there: the draft says so and leaves the columns nullable.

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
