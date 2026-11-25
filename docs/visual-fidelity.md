# Visual fidelity: making every window look like the WINDEV one

A screen that renders is not a screen that looks right. On a 2,335-window WINDEV 28 project the first migrated UI was
recognisable but wrong everywhere: neutral starter theme, panes overlapping their tab strips, check boxes without text,
windows stuck at their designer size, hidden controls drawn in tabs. None of it was a per-screen bug; each came from
evidence the pipeline did not extract or from one engine rule. Fix them in the pipeline and the engine, then measure
every window, not a sample.

## 1. Find the skin the application really uses

- A control's `style` (`140 iStyle.BTN_Simple`) names the template it was designed with. Search the code for
  `ChangeSkinTemplate`: applications often switch template at start-up for **all** components, from a folder
  delivered beside the executable (`<exe dir>/Estilos/<template>/<template>.wdy`), chosen per user in the data. Then
  every control takes the style of the same name in that template, whatever template its designer used.
- The project folder usually lacks the template (it keeps only the images a window names directly). Ask for the
  delivered program folder (`Exe/`) and read the template from there.
- `scripts/skin_template.py <template folder> --css … --images …` decodes the style sheet (`.sty`, else the `.wdy`
  blocks) into one CSS rule per style (font, size, weight, colour) keyed by `data-wd-style`, and exports the images
  (magenta → transparent; `--strips` cuts state strips once their state width is measured on the image).
- Measure on screenshots of the running application what the sheet does not say. Fonts can differ (one project drew
  its static captions in Segoe UI 12 px where the sheet said Trebuchet MS 11 px: `--substitute`); 9-slice margins and
  which state is hover / pressed / focused (the focused button is a later animation row of the strip) come from the
  images and the screenshots.

## 2. Extract what the layouts need beyond the dossier

`scripts/layout_frames.py` (called by `screen_layout.py` when `latest.json` names a `decoded` folder):

- **Tab frames.** Pane controls are positioned relative to the Tab's box; WINDEV draws them `pane_top` px lower (26 for
  top-tab styles, 2 for styles without a strip). Without it every pane sits under its strip and hand-made strips get
  drawn above the Tab, over other controls. Pane membership is plain text in the `.wdw` (`tabs :` → `- controls :`),
  single-pane Tabs included; the captions are the decoded unnamed `tabs` records.
- **Option captions.** A check box's text is its option record ("Corta papel"), not the control caption ("Corta
  papel?" or none). Radio buttons have one record per option. Records holding a template path are not captions.

**Each control's own look.** In the format-28 control record the font is a fixed record whose face is a plain string
(windev_decode.py looked for framed face strings and found "0 records" for every control), followed by frame and
alignment records: `scripts/control_look.py` reads face, size, weight, text colour, background, border and alignment.
On one project 16,905 controls had a font of their own (captions at 12-13 px where the style says 11), 8,043 a fill
colour and 27,954 a non-left alignment. Read them before guessing a font from screenshots: a measured caption that did
not match the style sheet looked like a font substitution and was the control's own 12 px font.

## 3. Engine rules that apply to every window

- Every control carries its style (`data-wd-skin` / `data-wd-style`); the generated sheet styles it.
- A window hosted in an MDI tab fills the tab and follows its anchors (measure the fixed content area, not the tab:
  measuring the tab feeds the window's own growth back).
- Runtime `..X` / `..Width` assignments (a window that widens a Tab when a side panel is hidden) are geometry the
  adapter declares; children of a resized container follow it by their own anchors.
- A control hidden at run time is not drawn in a tab either (a `[hidden]` rule scoped to dialogs missed tabs).
- A window opens centred on its parent: the topmost window, else the active tab's visible area. No dim overlay.
- Pictures of template buttons (`add_24.png` on `CTPL_Ribbon.BTN_Novo`) and their decoded captions are drawn: an
  adapter that draws its own button must still use the control's picture.

## 4. Find the screens that bypass the layout

A hand-built screen (flow layout, native `<input type="date">`, its own button bar) ignores all of the above. List
them before claiming coverage: files with many raw inputs and no use of the control boxes; in the browser, visible
controls without `data-control-path`. Rebuild them on the layout engine, keeping their logic.

## 5. Measure every window

- The designer thumbnail of each window (`<window>.wdw.cache` → `images/<window>.wdw.cache.3.bmp`, decoded by
  `windev_decode.py`) is the window's look as compiled, title bar included. Screenshots of the running application are
  the final word where they disagree (runtime template, runtime captions and visibility).
- Render every window at its designer size, screenshot its frame and score it against its thumbnail
  (`scripts/visual_compare.py`: pixel similarity, edge overlap, block structure). Rank, look at the worst, fix the
  cause in the pipeline or the engine, re-run. Scores rank; a person approves the look.
- REA (`rea inspect-pe-resources <exe> --json`) inventories the executable's resources and hashes; the WDL overlay of
  a WINDEV executable carries the embedded images (PNG signatures): hash them against the project folder to find
  skin images the project folder lacks.
