# Extraction strategy: from the WINDEV files to a faithful application

A migration is faithful when every behavior and every visible property of the old application is either reproduced and tested, or listed as an open question with an owner. This page says how the toolkit gets there from the project files, what it proves, and what it cannot.

Measured on the second migration's project (file format 25, 112 windows, 27 reports) with the commands shown.

## 1. Four kinds of evidence, in order of trust

| Level | Where it comes from | How it is known to be right | Share of the project |
|---|---|---|---|
| **Read exactly** | the code (plain text), `internal_properties` decoded by layout, binary containers unpacked | compared with the dossier field by field: every compared value equal (`calibration` in `index.json`) | all code; per control position, size, plane, order among siblings, caption, Visible, state, tab stop and order, anchors and rates, linked item, group, tooltip, skin style, button type, images, image states and background stretching; an edit's input type, size, mask, returned format, alignment and caption width; a static's alignment; column width, caption, alignment, place, linked item, five options and its cell's input type and mask; tab panes; window size, title, opening mode, title bar and its buttons, own HFSQL context and background image; a combo's or list's source, typed values and browsed, displayed and stored items; query parameter names; report type, data source, page, margins, band types, control kinds and geometry; the menu tree; what each report control prints; all SQL including 19 of 20 embedded queries (the other one stores no SQL text); fonts and text colours (read, not compared: the dossier does not print them) |
| **Learned, strong** | a position found by `windev_fieldmap.py learn`: its bytes explain a dossier property for every control | predicts windows it was not learned from without one error (at least 8 predictions), is the only position that fits, and a yes/no has several of each | 12 properties here, once those now read exactly left the list: an edit's calendar button and vertical scrollbar; a table's row height, browsed and stored items and two options; a button's animation steps; a column's assisted input |
| **Learned, weak** | same, but the project never varies the property enough, or two properties always change together | not known: listed apart, never applied by default | about 80 candidates here |
| **Unexplained** | `audit.json`: bytes that differ from the usual value of the control's kind and that nothing above explains | nothing is claimed; the difference is shown | 376 of 1,148 window controls have none; the others a median of 2 |

Nothing moves up a level by being plausible. A weak entry becomes strong with more variety (another project, more windows printed), or exact when someone changes that one property in WINDEV on a copy of a window and decodes it before and after.

## 2. Why this can be trusted without reading every byte

- **The decoding itself is exact.** Re-encoding the decoded values reproduces WINDEV's own bytes for 3,890 of 3,993 values.
- **Every named field is checked against a second source** wherever one exists, per field, with counts — not sampled by eye.
- **Learned positions are tested on windows they never saw**, and an enumeration value that was never seen is reported as `unknown:<bytes>`, not guessed.
- **What is not understood is counted and listed**, per control, with the usual value beside it. An unexplained difference is usually a style choice made on that one control (a colour, a border, an alignment): exactly what makes one screen look different from its neighbours, and what a rewrite silently loses.

So the remaining risk is visible and bounded: it is the audit list, not an unknown.

## 3. The pipeline

```sh
python3 scripts/prepare_evidence.py        # everything below, in order, into analysis-local/ and docs/
```

1. `inspect_windev.py` — code blocks with their control and event, layout geometry (decoded when the source has none readable), schema, parity seed.
2. `dossier_extract.py` — only if a dossier PDF exists, of the whole project or of some windows.
3. `windev_fieldmap.py learn` — only with a dossier: this project's field map, completing the one shipped in `scripts/windev_fieldmap.json`.
4. `windev_decode.py --evidence` — decoded properties, learned properties, fonts, SQL, thumbnails, `audit.json`, and the `evidence/` folder every later tool reads as the dossier (decoded values over the PDF's, the PDF's for the rest).
5. `code_map.py` — per unit, the tables read, written, deleted and bound, queries, procedures called, windows opened, globals used; per table its readers and writers; and the sites a text search cannot resolve (`dynamic`).
6. `event_legend.py`, `evidence_report.py`, `schema_draft.py`, `render_layouts.py` — unchanged readers.

Then per unit: `unit_evidence.py <UNIT>` gives the mapper its code, events, dossier-shaped properties, **unexplained differences**, **fonts**, **embedded query SQL** and its **code map entry** in one file; `screen_layout.py <UNIT>` gives the screen generator its layout.

### What a project without a printable dossier gets

The whole pipeline was run on the measured project with its PDF taken away, and every output compared with the PDF-backed run (112 windows, 1,148 controls, 32 tables).

| Output | Without the PDF |
|---|---|
| Schema draft | WINDEV type and SQL type equal for 252 of 252 columns (type names from the built-in code table); captions from the analysis file equal for 218 of 220 and present for 27 the dossier lacked |
| Screen layouts | identical for position, size, kind, plane, anchors and rates, tab order, state, Visible, caption, style, button type, images, image states and stretching, edit input type, size, mask, alignment and caption width, date options, column width, title, alignment, place, linked item, shown or hidden and four more options |
| Evidence report | same callers, the same proposals for predefined actions and the same five runtime questions |
| Code, events, navigation, code map, queries with SQL | unchanged: they never came from the PDF |

What only the PDF gave, on that project:

- a **window's** type and its other tick marks (status bar, resizable, save position…): none of them ever varies there, so no position can be told from another;
- a **table's** own options (scrollbars, selection mode, magnifier) and a column's "assisted input" (learned for one record length only), "with input", "sorted", "fixed", "RTF": same reason for all but the first;
- the input type and alignment the dossier prints for statics, combos, check boxes and radio buttons (their defaults);
- positions of the 18 controls inside table cells;

None of these is geometry, code or data. Each stays `unresolved` for the unit that needs it, and one property changed in WINDEV on a copy of a window settles its position for every project of that format.

### The earlier, single-window measurement

Run with no PDF, the same project produced, for four windows (287 controls, among them the largest window), layouts equal to those made with the dossier on position, size, plane, kind, anchors, tab order, state, Visible, caption, button type, images, image states and background stretching, an edit's input type, size, mask, alignment and caption width, and a column's alignment, place and linked item (9 caption widths and 2 column input types differ). Missing: the alignment and input type the dossier prints for combos, radio buttons and statics, a table's own options, the tick-mark properties not read yet (a column's assisted input, a check box's three states…), the skin image of check boxes and radio buttons. Those are the audit's and the weak list's job (below).

## 4. Closing what is left, cheapest first

1. **Print a small dossier.** WINDEV prints the documentation of selected elements. Choose windows that show variety (the audit names the controls that differ from the norm), put the PDF under `legacy/`, re-run. `learn` needs about eight controls of a kind with a property set both ways. A map learned on one project applies to any project of the same file format.
2. **Change one property.** On a copy of one window in WINDEV: set the property, save in text format, decode both, compare the chunk (`--raw`). One changed position is the answer, exactly. Add it to the decoder with a test.
3. **Read the audit with the thumbnail.** `images/` holds a small picture of each window as WINDEV draws it. A control with a difference at a font or colour position that looks different in the picture needs no more proof.
4. **Ask the running application** for what no file holds: values set by code at opening, what Esc does on a dialog, data-dependent states. These were always runtime questions.

Record each answer where the next project finds it: a decoder field with its calibration, or the shipped field map (`learn --shareable` keeps strong entries only, so no word of the application leaves the project).

## 5. Rules for agents using this evidence

- Cite the level: `decoded: WIN_X/BTN_Y/caption` (exact), `learned: WIN_X/EDT_Z/input_type` (strong), never a weak entry as a fact.
- A control listed in `unexplained_differences` is not done when its named properties are reproduced. Either explain each difference (and say how), or carry it as a `U-` item on the unit.
- A value marked `unknown:` is a question, not a default.
- A control with a `style` and no `differs_from_style` looks exactly like its skin style: implement the style once, not the control. Each line of `differs_from_style` is a deliberate change on that control (a red warning, a bold total) and must show in the new screen.
- A combo's `initial_content` is the complete list of values the designer typed, in order: the position of a value is what the code compares with (`COMBO = 2`). Take the list from there, never from the screenshot.
- Prefer the decoded caption to the PDF's (accents and trailing spaces are exact) and say so when a test compares strings.
- Do not copy a weak or unexplained value into a layout to make a screenshot match; match it, then find out what it is.

## 6. Using the code map to plan

- **Slice order.** `project.json` → `folders` is how the authors grouped the application; the code map says which tables each group writes. Start with units that only read and bind (lists, search windows), then the forms that write one table, then the windows that write many (here one front-office window writes eight tables and has 62 dynamic sites: it is a slice of its own, late).
- **Shared rules.** A procedure called from many units, or a table written from several windows, is a rule to implement once on the server side and test once: the map lists both.
- **Hidden writers.** Forms whose tables show only as `bound` save through a generic procedure that takes the table name at run time. The map cannot follow that: its `dynamic` sites name the lines to read.
- **Other systems.** `unknown_tables` are tables of another database reached through SQL; each is an integration to decide on, not a table to migrate.

## 7. What this does not cover

- **Behavior** is in the code and stays the mapper's and the tests' work: the decoder adds no rule, only what the designer set.
- **The skin as a whole** is not rebuilt for you: `skin/<skin>.json` lists each style's fonts, colours, frames and images, and each control says what it changed from its style, but which font or frame draws which part of a control is by order, not named.
- **Colours other than text**: frames (border type, background and border colours) are read by their shape and listed per control; no second source confirmed them, so they are a lead for the eye, not a fact.
- **Predefined actions**: an action that names an element (a Print button and its report) is read from the source and becomes a caller in the evidence report and the proposal of its encoded action. Actions that name nothing (close, validate) leave a record with no readable meaning: those still rest on the proposals of `evidence_report.py`.
- **Controls inside table cells** have no window position.
- **Projects in binary format** get windows with their controls, columns, cells, panes and options, and code blocks with their control and event (formats 25 and 28 measured; on the measured project equal to the text sources). The inspector seeds one parity row per code block of a binary element, citing a listing it writes. Reports (page, bands, controls, linked items), menu options and predefined actions are read from binary files too, each equal to the text sources of the measured project. Not yet: dialogs, and the sub-menu an option belongs to. Switching the project to text format in WINDEV, when someone can open it, is still the shorter road; when nobody can, see [file formats §2](windev-file-formats.md).
- **Other WINDEV versions**: every offset here was measured on one file format. `coverage`, `calibration` and the audit tell at once whether they hold; a partial dossier re-learns what moved.
- **Multilingual projects** were not measured: a caption is read as one string.
