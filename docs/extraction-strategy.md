# Extraction strategy: from the WINDEV files to a faithful application

A migration is faithful when every behavior and every visible property of the old application is either reproduced and tested, or listed as an open question with an owner. This page says how the toolkit gets there from the project files, what it proves, and what it cannot.

Measured on the second migration's project (file format 25, 112 windows, 27 reports) with the commands shown.

## 1. Four kinds of evidence, in order of trust

| Level | Where it comes from | How it is known to be right | Share of the project |
|---|---|---|---|
| **Read exactly** | the code (plain text), `internal_properties` decoded by layout, binary containers unpacked | compared with the dossier field by field: every compared value equal (`calibration` in `index.json`) | all code; per control position, size, plane, order among siblings, caption, Visible, state, tab stop and order, anchors and rates, linked item, group, tooltip, button type and images; column width and caption; tab panes; window size and title; report geometry; the menu tree; what each report control prints; all SQL including 19 of 20 embedded queries (the other one stores no SQL text); fonts and text colours (read, not compared: the dossier does not print them) |
| **Learned, strong** | a position found by `windev_fieldmap.py learn`: its bytes explain a dossier property for every control | predicts windows it was not learned from without one error (at least 8 predictions), is the only position that fits, and a yes/no has several of each | 15 properties here: an edit's input type, calendar button, return format; a table's row height and three options; column options… |
| **Learned, weak** | same, but the project never varies the property enough, or two properties always change together | not known: listed apart, never applied by default | about 80 candidates here |
| **Unexplained** | `audit.json`: bytes that differ from the usual value of the control's kind and that nothing above explains | nothing is claimed; the difference is shown | 332 of 1,148 window controls have none; the others a median of 2 |

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
5. `event_legend.py`, `evidence_report.py`, `schema_draft.py`, `render_layouts.py` — unchanged readers.

Then per unit: `unit_evidence.py <UNIT>` gives the mapper its code, events, dossier-shaped properties, **unexplained differences**, **fonts** and **embedded query SQL** in one file; `screen_layout.py <UNIT>` gives the screen generator its layout.

### What a project without a printable dossier gets

Run with no PDF, the same project produced, for a 77-control window with tabs, tables and a supercontrol, a layout equal to the dossier-validated one on position, size, plane, kind, anchors, tab order, state, Visible, input type, button type and images. Missing: alignment, input mask and size, caption width, image state counts, table options, check-box images. Those are the audit's and the weak list's job (below).

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
- Prefer the decoded caption to the PDF's (accents and trailing spaces are exact) and say so when a test compares strings.
- Do not copy a weak or unexplained value into a layout to make a screenshot match; match it, then find out what it is.

## 6. What this does not cover

- **Behavior** is in the code and stays the mapper's and the tests' work: the decoder adds no rule, only what the designer set.
- **Predefined actions** of code-less event slots decode to small identical records; their meaning still comes from the proposals of `evidence_report.py`.
- **Controls inside table cells** have no window position.
- **Other WINDEV versions**: every offset here was measured on one file format. `coverage`, `calibration` and the audit tell at once whether they hold; a partial dossier re-learns what moved.
- **Multilingual projects** were not measured: a caption is read as one string.
