# What the evidence tools hand to agents, and in what order to read it

The extraction tools exist to be consumed: by the next tool, by a template, or by an agent with a limited context. This page is the map of that hand-over — every output, who writes it, who reads it, and how much of it an agent needs for which job. Keep it current when a tool changes what it writes; `scripts/field_use.py` checks the toolkit against it.

## Reading order for one unit

An agent taking a window, report, class or set of procedures reads in this order and stops as soon as it has enough:

1. **`docs/briefs/<unit>.md`** — one page: what the unit is, who opens it, the data files it touches, its events with their line ranges, and its **open points** (what the evidence does not settle, and what would). On the measured project the 149 briefs together are 210 KB; the full evidence pack of one large window alone is 360 KB.
2. **`docs/screens/<unit>.md` or `docs/reports/<unit>.md`, `docs/mapping/<unit>.md`** — once the unit is mapped: what to build and the rules, each with its evidence.
3. **The layout as data** — `python3 scripts/screen_layout.py <unit>`: positions, captions, images, fonts, anchors, tab order, columns. The screen generator consumes it; an agent reads it only to check a control.
4. **The source file, at the lines of the event being ported** — never the whole file "to be sure": the brief gives the line ranges.
5. **`python3 scripts/unit_evidence.py <unit>`** — everything at once, for the mapper and the reviewer, who need all of it. An implementer opens it only where the brief points.

Before a stage starts, the planner reads **`docs/readiness.md`**: units ranked by open points and sized by parity rows and code lines. First slices come from the units with none; a unit's open points are settled (answer sheet, a question to the owner, a look at the running application) before its slice starts, not discovered inside it.

## The outputs

| Output | Written by | Read by | Committed |
|---|---|---|---|
| `analysis-local/latest.json` | `prepare_evidence.py` | every tool below (`--latest`), prompts | no |
| `docs/parity/parity-seed.csv` | `inspect_windev.py` | `parity_check.py`, `merge_parity.py`, the mapper | yes |
| `docs/readiness.md`, `.json` | `readiness_report.py` | the planner; `docs/briefs/` come from the same run | yes |
| `docs/briefs/<unit>.md` | `readiness_report.py --briefs` | the agent taking the unit | yes |
| `docs/evidence-report.md`, `.json` | `evidence_report.py` | `unit_evidence.py`, `readiness_report.py`, the mapper | yes |
| `docs/evidence/encoded-actions.md` | `evidence_report.py` (never overwritten) | everyone: answers, or the proposal used until answered | yes |
| `docs/navigation.md` | `evidence_report.py` | the planner (slice order), the shell | yes |
| `docs/code-map.md`, `.json` | `code_map.py` | `unit_evidence.py`, `readiness_report.py`, the data-layer slices | yes |
| `docs/mapping/event-codes.md`, `.json` | `event_legend.py` | `unit_evidence.py`, `readiness_report.py`, the mapper | yes |
| `docs/schema/schema-draft.md`, `.sql`, `.json` | `schema_draft.py` | the database ADR; `data_profile.py`; the server template's `tools/pg_schema.py` | yes |
| `docs/data/profile.md` | `data_profile.py` | the database ADR, the importer's quarantine rules | after review |
| `docs/evidence/images/` | `prepare_evidence.py` | specs, `visual_compare.py`, agents that can see images | yes |
| layout JSON (`format_version` 1) | `screen_layout.py` | `generate_screens.py`, the UI kit (`LegacyControl`), `render_layouts.py`, `skin_assets.py` | generated |
| `analysis-local/decoded-*/analysis.json` | `windev_decode.py` | `schema_draft.py --decoded`, `hfsql_read.py --analysis` | no |
| `analysis-local/decoded-*/evidence/` | `windev_decode.py --evidence` | every tool that takes `--dossier` | no |
| `data.sqlite`, CSV, `manifest.json` | `hfsql_read.py`, `windows/export_odbc.py` | `data_profile.py`, `compare_exports.py`, the importer | never |

## Read from the files, applied by no tool yet

`field_use.py` lists the fields nothing reads. On the measured project these are in the layout JSON and declared in the UI kit's types, but no generator or control renders them: they are the adapter's job, and a screen spec should say which matter for its window.

| Field | What it is | Where it matters |
|---|---|---|
| `control.differs_from_style` | what the control changed from the skin style it names | the per-control overrides: everything else comes from the style, reproduced once |
| `control.frames` | border type, background and border colours (read by shape, not compared with a dossier) | coloured panels and bordered statics; check against the image before using |
| `control.background_stretch` | how a button's background image is stretched | 9-slice or stretched button skins |
| `window.opening_mode`, `window.window_type` | centred in the parent, in the screen, free or modal | how the shell opens the window |
| `control.displayed_item`, `stored_item` | what a file-bound combo shows and stores | the combo's adapter |
| schema draft `key_compares` | a text key ignores case and accents | unique indexes and lookups: carried to the server catalogue as `compares`, enforced by nothing |
| schema draft `scale`, `integer_digits` | digits of a decimal | carried to the server catalogue; rounding and formatting are the data layer's |

## Checks that cost no agent time

| Question | Command |
|---|---|
| What would an implementer have to guess, and where? | `python3 scripts/readiness_report.py --out docs/readiness.md --briefs docs/briefs` (run by `prepare_evidence.py`) |
| Does the decoder's reading hold on this project and WINDEV version? | the first section of `docs/readiness.md`; then [new-windev-version.md](new-windev-version.md) |
| Does every window's layout pass the screen generator? | the same run: a refused layout is an open point |
| Which extracted fields does nothing use? | `python3 scripts/field_use.py --out docs/field-use.md --consumers src packages` |
| Is the data readable without a driver, and what is it really? | `python3 scripts/prepare_evidence.py --data <copy of the data folder>` |
