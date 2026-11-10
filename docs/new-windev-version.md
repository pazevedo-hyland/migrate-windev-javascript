# A project of another WINDEV version: how much of the decoder to trust

Everything `windev_decode.py` reads at a fixed place inside a record was measured on one project (file format 25, saved by WINDEV 25, opened in 28). The container, the cipher and the packing have held on every file tried, including WINDEV 28's own examples; the positions inside some records have not. This is the ten-minute procedure that tells a team where they stand, before any screen is built on decoded values.

## 1. Run the pipeline and read three numbers

```sh
python3 scripts/prepare_evidence.py
```

Open `docs/readiness.md`, section "How far the decoder applies here":

| Line | Good | If not |
|---|---|---|
| designer properties decoded | all of them | a different cipher or packing: stop, the sources of this version need new work; use the dossier PDF for everything |
| window controls with position and size | 95% or more | the common block of a control moved: layouts are not usable; use the inspector's layout (text sources state x, y, width, height in clear) and the dossier |
| against the printed dossier | every kind of field agrees | the kinds listed as differing are not to be used from the decoder: the dossier's value wins (it already does in the evidence folder) |

## 2. With no dossier, make a small one

Nothing was compared when there is no PDF. Printing the whole project documentation may be impossible on a very large project; printing it for **three or four windows** is not (WINDEV: project documentation, restricted to selected elements). Choose windows that together hold a table with several columns, edits with masks, buttons with images, a combo and a tab control. Put the PDF under `legacy/` and run the pipeline again: `windev_fieldmap.py` learns this project's positions from it, and the calibration now covers every kind of field those windows contain. What agrees there is trusted for the other windows; what differs is reported.

Without any PDF, compare a few layouts by eye: `render_layouts.py` draws each window from the decoded positions (`docs/evidence/images/<window>.svg`); the `.cache` thumbnails in `analysis-local/decoded-*/images/` are WINDEV's own picture of the same windows.

## 3. What is known to differ in format 28

Read on WINDEV 28's tutorial and examples: windows, controls, columns, cells, panes, code blocks with their events, reports with bands and controls, predefined actions that name an element. **Not read there**: an edit's input type and mask, a report's page and margins, a report control's linked item, menus. The analysis file of those examples is a stub (nothing is read from it; the `.xdd` gives the schema).

## 4. Data files

`hfsql_read.py` says in its manifest which files it read, which it refused and why, and which item types it did not interpret. It was measured against the ODBC driver on HFSQL Classic files written by version 28. Where a driver is available, export the same copy both ways once and compare (`compare_exports.py`): agreement on one project's data is what makes the driverless route trustworthy for that project.

## 5. Report what you find

A project that varies a property this one never varied (table options, null support, links between files) is how the remaining fields get located: `windev_fieldmap.py learn` on its dossier does it without code. Send the learned field map and the calibration counts back with the WINDEV version; no source, no data.
