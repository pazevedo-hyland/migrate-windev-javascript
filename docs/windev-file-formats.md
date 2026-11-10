# What is inside the WINDEV project files

The project folder holds everything the project documentation PDF (the "dossier") prints, and more. This page says where each piece is, how it is stored and how far `scripts/windev_decode.py` reads it. Use it when the dossier is missing, cannot be generated (a very large project) or lost characters in the PDF.

Measured on one project (file format 25: `major_version : 25` in its sources; 112 windows, 27 reports, 5 queries) and compared with that project's dossier:

| Decoded from the sources | Result | Against the dossier |
|---|---|---|
| `internal_properties` values | 3,993 of 3,993 decoded | — |
| Window control size | 1,148 controls | 1,144 of 1,144 equal |
| Control position in the window | all but the 17 controls inside table cells | 1,126 of 1,126 equal |
| Visible | | 802 of 802 equal |
| Plane | | 1,144 of 1,144 equal |
| Tab order and tab stop | | 1,034 of 1,034 equal |
| Initial state (active, read-only, grayed) | | 1,081 of 1,081 equal |
| Button type (normal, validate, abort) | | 589 of 589 equal |
| Button image, background image and its number of states | | 588 of 589 equal each |
| Anchor rates | | 1,130 of 1,130 equal |
| Captions | 822 controls with one | 819 of 820 equal; accents correct where the PDF lost them. 292 of them are stored in UTF-8, the others in the code page, sometimes in one window: each string is read as UTF-8 when it is valid UTF-8 (before this was found, those 292 came out as `InÃ­cio`; the comparison with the PDF ignores accented letters and did not show it) |
| Combo and list boxes: content in memory or from a file, browsed file, browsed, displayed and stored items | 44 with a dossier value | source 44 of 44 equal; the four names 106 of 106 |
| Values typed in the designer for a combo or a combo column | 6 lists | the dossier prints the first value only: first values equal; the full lists (document types, order states, months) are in the source alone |
| Window size and title | 112 windows | size 111 of 112 equal (the window with a menu bar differs by its height); title 112 of 112 |
| Edit control: input type, input size, input mask, format of the returned value, alignment | 270 edit controls | 261 of 261 equal; 270 of 270 equal; 270 of 270 equal; 270 of 270 equal; 270 of 270 equal |
| Where an edit's or combo's input area starts (caption width) | 310 controls | 281 of 294 equal; the others are one pixel off in the dossier, all in two windows |
| Static text alignment (horizontal, vertical) | 74 statics | 74 of 74 equal |
| Button: number of image states, how the background image is stretched | | 588 of 588 equal; 580 of 580 equal |
| Table column: alignment, place in the table, five options (sortable, moveable, adjustable width, multiline, with search) | 310 columns | 250 of 250 equal; 270 of 270 equal; 1,375 of 1,375 equal |
| Table column cell: input type and mask | | 243 of 243 equal; 240 of 240 equal |
| Skin style of a control (`170 AquaBlue.BTN_Ok`) | 1,018 controls name one | not printed by the dossier |
| Window: opening mode, title bar, system menu, minimize and maximize icons, own HFSQL context, background image | 112 windows | opening mode 112 of 112 equal; the five options 498 of 498 (the PDF extract mixes the names of neighbouring tick marks for some windows: those are not compared) |
| Skin styles (`Templates/<skin>/<skin>.sty`) | 1,203 styles in 3 skins | not in the dossier. 1,015 controls name a style found there; 291 of them changed a font, a colour or a frame from it |
| Query parameters | 13 of 24 queries have some | names read from the SQL (`{pOrder}`); the dossier extract had none |
| Report control geometry (mm) | 497 controls | 493 of 493 equal |
| Report control kind (static, calculation, preset, image, shape) | | 493 of 493 equal |
| Report type, data source, margins | 27 reports | 26 of 26 equal each |
| Report band types | 133 bands | equal to the band names WINDEV gave them |
| Query SQL from binary `.WDR` | 5 of 5 | same text, without the PDF's line wraps |
| SQL of queries embedded in windows and reports | 19 of 20 | not in the dossier at all |
| Fonts and text colours | every control | not printed by the dossier: read, not compared |
| Window and report thumbnails | 219 images | — |

Screen layouts generated with no PDF at all (`screen_layout.py` on four windows, 287 controls, among them the largest window of the project) equal the layouts generated with the dossier on every position (but the 3 controls inside table cells), size, kind, plane, anchor, tab order, state, Visible tick, caption, button type, button images and their state counts, background stretching, edit input type, size, mask and alignment, column alignment, index and linked item, and on all but 9 caption widths and 2 column input types. What the PDF still adds there: a table's own options, the tick-mark properties not named above, the skin image of check boxes and radio buttons, and the default input type the dossier prints for statics and combos.

The offsets below come from that one format. On another WINDEV version, run the tool, read `coverage` in `index.json`, and compare with a dossier of a few windows or with the running app before trusting a field.

## 1. `internal_properties` in text-format sources

Text-format `.wdw`, `.wde`, `.wdg` and `.wdc` files keep code readable and put every designer property in `internal_properties : <base64>`. In this format there is no readable `x`, `y`, `width` or `height`: geometry is in there too.

The value is not a secret format, only a packed one:

1. **Base64** of: an 8-byte header (two 32-bit values, `5` and `5` here), then the body. If the first byte is `0` or `4`, there is no header and no cipher: the value is a packed block directly.
2. **A byte cipher over the whole body**, with a fixed 16-byte key (`51 43 3a e7 24 db 48 68 aa 41 07 db 74 b7 4c 44`). Each byte is combined with its mirror byte, its neighbour and the key, so changing one property changes every byte: that is why two near-identical controls look unrelated in the file. `decrypt()` in the script is the whole algorithm (about 15 lines); `encrypt()` is its inverse.
3. **A packed block**: byte `4`, packed size (u32), unpacked size (u32), two zero bytes, then LZW codes read low bit first, 9 to 16 bits wide. Codes 1–256 are the bytes 0–255, 0 resets the table, 257 ends. Byte `0` instead of `4` means stored data (u32 size, bytes).
4. **Property chunks**: one count byte, then per chunk an id (u16), a version (u16) and a size (u32), then the chunk data in the same order.

Re-encoding the decoded chunks with the script reproduces WINDEV's own bytes for 3,890 of the 3,993 values, so the reading is exact, not approximate.

### Chunk contents

Chunks are sequential binary records without field names. Three things make them readable:

- **Strings are in two encodings.** The project's code page, and UTF-8 for texts last edited by a recent WINDEV. Nothing marks which: a string that is valid UTF-8 and has a byte above 127 is UTF-8.
- **Strings** are framed: one zero byte when empty, else `ff ce 88 f1`, total length (u32), the text, a zero byte, `fe ed 98 e1`. The tool lists every string of every chunk in file order (`strings`), in the project's code page (`--encoding`, default Windows-1252), plus UTF-16 runs (report captions).
- **Sub-records start with a version number** (`0x25f`, `0x262`, `0x25b`…), which is how a record is recognised.
- **Layout is fixed per control type**, so an offset found on one button holds for all buttons of that format.

Which chunk holds what (id, version):

| Element | Chunks | Contents |
|---|---|---|
| Window control | `1`, then `0` (v14) | `1`: identifiers and links. `0`: type-specific style (fonts, colours, style name such as `170 AquaBlue.BTN_Simple`), the common block, type-specific tail (button caption and image, masks) |
| Table column | `1`, `0` | `0`: version, width, caption, alignment and options, linked item (`Customer.Name`), more options (below) |
| Column `content`, combo `dropdown`, `calendar` | `0` | the embedded edit/combo/calendar control. A column's `content` is its cell: a whole control with the common block, and for a text column the edit record with its input type and mask |
| Window | `1`, `6`, `0` | `6`: platform, creator, skin template. `0`: version at 16, then x, y, width, height; title; background image; file name |
| Menu option | `0` (and `1`) | caption, fonts |
| Report, band, report control | `15` (v14), `1` | `15`: name, 8 bytes, then top, bottom, left, right as doubles in millimetres, then one byte for the element's type (below); font; caption. `1`: the same captions in UTF-16. The report's own `15`: name, type, data source, messages, page and margins |
| `code_elements`, `code_parameters`, `string_res`, `rad`, `custom_note` | `5`, `2`, `3`, `9`… | small fixed records; rarely needed |

### The common block of a window control

Found in chunk `0` by its signature: a version, four integers, eight zero bytes and the maximum size (`ff ff ff 07` or `ff ff ff 7f`, twice). From the first integer:

| Field | Where | Notes |
|---|---|---|
| x, y, width, height | 4 × i32 | x and y are **relative to the parent control** |
| visible | +32, u32 | the dossier's Visible tick |
| double-click button | string after 5 bytes | a table's or list's button, e.g. `BTN_Modify` |
| popup menu | string | `<NO CONTEXT MENU>` or a menu name |
| initial state | u32 | 0 active, 1 read-only, 4 grayed |
| tooltip | string | |
| caption | string, 24 bytes later | statics, edits, combos, check boxes, tabs. A button keeps it empty and has its caption after the block |
| plane | u32 right after the caption | 0 = every plane |
| initial value | string, 4 bytes later | an edit's value, an image control's file |
| anchor | u16 | bits: 1 bottom, 2 height, 4 right, 8 width |
| linked item | string | the data binding, `Table.Item` |
| tab stop, tab order | u32, and i32 16 bytes later | order is zero-based; −1 = none. The dossier prints −1 when the stop is off |
| group | string | |
| order | u16 right after the group | 1..n among the controls of the same parent (per pane inside a tab): the designer's order. Numbering checked on 148 sibling groups; its use as drawing order is inferred |
| anchor rates | 4 × u32, 12 bytes later | right, width, bottom, height, in thousandths |
| button type | byte 50 before the end of the chunk | 0 normal, 1 validate, 3 abort (2 and 4 not observed) |
| button caption, background image, number of background states, image | a record 107 bytes after the block end (below) | string, string, u32, string. Kept only when these are exactly the first strings found there |
| tab style | u32, 58 bytes before the end of a tab's chunk | 0: panes start 26 px below the tab's top; 2: 2 px. Other values not measured |

**Where the block ends.** The record of the control's own kind starts 28 bytes after the group's order. One window of the project (its largest, 118 of 124 controls) keeps four more bytes per control before that record: the maximum-size marker (`ff ff ff 7f`, or `ff ff ff ff`) that sits 26 bytes into the record says which. Every offset "after the block" below counts from the corrected position; before this was known those controls were read four bytes off.

### Records of one kind of control

| Kind | Field | Where | Checked |
|---|---|---|---|
| any | skin style | the first string of the form `<number> <skin>.<style>` before the common block | names are the skin's own (`BTN_Ok`, `BTN_Annuler`, `BTN_Supprimer`, `SAI_Simple`…): a button's role is often readable from it. Absent = a custom style |
| any | font record | tag `0x25b`, 4 bytes, 4 bytes, horizontal alignment (u32: 0 left, 1 centre, 2 right, 3 justified), vertical alignment (u32: 0 top, 1 centre), `LOGFONT`, face, text colour | a static's only font gives the static's alignment |
| any | frame record | tag `0x262`, border type (u32), background colour (4th byte `ff` = none), border colour | read by shape, not compared with another source |
| Edit, Combo | caption width | 24 bytes after the first font's face: u32 `4`, then the width | the input area starts there, from the control's left edge |
| Edit (and a column's cell) | version tag | block end + 51: u32 `1`, u32 `0x286` | when the tag is not there the record is not read |
| | input size | + 59, u32 | |
| | input type | + 71, u32 | 0 text, 1 numeric, 2 date, 3 time, 5 duration |
| | type of the value | + 75, u16 | WINDEV's code; 13 with a numeric input is the dossier's "high-precision numeric" |
| | alignment | + 77, u8 | 0 left, 1 centre, 2 right |
| | input mask, returned format | two strings from + 121 | empty mask = the dossier's `0` |
| Button | caption, background image, its states, image, its states | a record 107 bytes after the block end: string, string, u32, string, u32 | |
| | background stretching | u32, 52 bytes after the fourth font's face | 2 width and height, 0 custom 9-slice scaling; only meaningful with a background image |
| List box, a combo's `dropdown` | version tag | block end + 51: u32 `1`, u32 `0x270` | |
| | content in memory | + 63, u32 | 1 memory, 0 a file or query. Whether a file is loaded in memory or read directly is not located |
| | typed content, browsed file, browsed item, (u32), displayed item, stored item | strings from + 71 | the typed content is one value per line; a browsed query embedded in the window is named `<window>_1$Query` |
| Table column | alignment | u32 right after the caption | 0 left, 1 centre, 2 right |
| | sortable, moveable | u32 at + 12 and + 16 after the caption | |
| | linked item | string at + 32 after the caption | a column shown through a link holds `File.Item<TAB>OtherFile.Key.Item` |
| | adjustable width, multiline, with search | u32 at + 4, + 16, + 20 after the linked item | kept only when all five options are 0 or 1 |
| Window | opening mode | one byte, 312 bytes after the face of the window's font | 2 centred in the screen, 3 centred in the parent window |
| | title, background image | two strings, 316 bytes after that face | |
| | title bar, system menu, minimize icon, maximize icon | 4 × u32, 5 bytes after the background image | maximize was never off where the dossier names it clearly: its place is the one left |
| | own HFSQL context | u32, 46 bytes after the background image | |
| Report | type, data source | u32 at + 9 and + 13 after the report's name | 2 table, 4 label, 5 free; 0 none, 1 embedded query, 6 the dossier's "text file" |
| | page | eight doubles in a row: height, width, margins top, bottom, left, right (mm) | found by shape. Reports created by the RAD keep a Letter size there while the dossier prints A4: the band widths follow the stored size |
| Report band, report control | type | one byte after the four geometry doubles | bands: 1 start of document, 2 page header, 4 body, 6 break header, 7 break footer, 11 page footer, 12 end of document. Controls: 16 calculation, 17 shape, 18 image, 20 preset, 39 static. A code outside these lists is kept as `type_code` |

**Positions.** Add the parents' x and y to get window coordinates; a **tab** parent also adds where its panes start (its style, above). A tab of an unmeasured style gives its children no window position, and a **table** places controls in cells: those keep parent-relative `x`/`y` only. Each pane of a tab is an element of its own (owner `tabs`, with its caption); a control directly inside a tab carries `pane`, the number of its pane. A pane is not a WINDEV plane: planes are not named yet.

### Mapping one more field

Everything else a control has (a table's options, the other tick-mark properties, most of a report control's style) is in the same chunks, not yet named. To name one:

1. Run with `--raw` to keep each chunk as hex.
2. Take two controls of the same type that differ in that property only (or the dossier's value for a few hundred controls) and compare their chunks from the common block signature, or from the end of the chunk.
3. Keep an offset only when it explains **every** control of that type, as the tables above do; add it to the decoder with a test and a line in `calibrate`.

The fastest search, used for the records above: for one kind of control, try every offset counted from the block end, from the chunk end and from the end of a string or font before it, and keep those where the bytes and the dossier's values map one-to-one for all controls. An offset that fits all but a few is usually right with the anchor wrong: look at what the exceptions share (here, one window).

A property changed in WINDEV on a copy of one window, saved in text format and decoded before and after, settles an offset in minutes.

### Fonts, options, embedded queries

- **Fonts**: a font is a Windows `LOGFONT` (height, width, escapement, orientation, weight, italic, underline, strike-out, character set, four precision bytes) whose face name is a framed string. A negative height is pixels at 96 dpi (−11 = 8.25 pt). The four bytes after the face are read as the text colour (red, green, blue, 0). Each element lists its `fonts` in file order: a button has four (one per state), an edit its caption font and its input font. Which font belongs to which part is by order, not named.
- **Menus**: a window's menu options, in file order with their captions and the options above them, form the tree (`menu` in the evidence folder); each option's code is a normal code block of the inspector.
- **Report controls**: besides geometry, `linked_item` is the query item a control prints (`<report>$Query.item`, from chunk `1`) and `content` its own text, mask or preset (`[PAGENUM]/[NBPAGES]`).
- **Options**: each choice of a radio button or check box and each menu option is an element of its own (owner `options`) whose first string is its caption.
- **Embedded queries**: a window's or report's own query (`<name>$Query`, owner `elements`) holds a whole PCS container in chunk `4`; its SQL is read like a `.WDR` file's and added to `queries.json`.

### Properties without a known layout: the field map and the audit

Replacing each string of a chunk by one zero byte gives the layout an all-empty element would have, so a byte position means the same in every element of a kind, counted from the chunk's start or end or, for a control, from the start or end of the common block. On that footing `scripts/windev_fieldmap.py`:

- **learns** where a dossier property sits: the position whose bytes map one-to-one to the property's values for every control of that kind (a number read directly, an enumeration, or a string slot), then scores it on windows left out of the learning. `strong` = at least 8 held-out predictions, none wrong, no other position fitting, and for a yes/no at least 3 of the rarer value. Everything else is `weak` and not applied.
- **applies** strong entries to every element (`properties` in the decoder's output, written into the evidence folder in the dossier's own form). The map shipped as `scripts/windev_fieldmap.json` was learned on the measured project; `learn` on another project completes it.
- **audits**: per element, the bytes that differ from the most common value of its kind and that no parsed field, learned property, font or string covers. Positions where most elements differ from each other are identifiers and are left out. See [extraction strategy](extraction-strategy.md) for how to use the list.

### How the other tools get these values

- `inspect_windev.py` fills its `layout` (positions and sizes of controls, column widths, report bands and controls) from `internal_properties` when the source has no readable geometry, and marks the file `layout_source: internal_properties`. `render_layouts.py` and `screen_layout.py` read that layout as before.
- `windev_decode.py --evidence` writes `<out>/evidence/`, a folder in the shape `dossier_extract.py` writes: when a dossier extract is given it is copied and the decoded captions, titles, geometry, tab order, state, Visible, button type and images, anchors and SQL are written over it (each control lists them in `decoded`; a query keeps the PDF's text as `sql_pdf`); controls, windows, reports and queries the dossier lacks get entries. Everything the decoder does not name stays as the dossier had it. Without a dossier the folder holds the decoded values alone.
- `prepare_evidence.py` makes that folder the `dossier` of `analysis-local/latest.json`, so `evidence_report.py`, `render_layouts.py`, `screen_layout.py` and `unit_evidence.py` use it unchanged; the PDF extract stays at `dossier_pdf`.

## 2. Binary files: the PCS container

Every binary project file starts with `PCS\0`: `.wdp` (project), `.WDR` (query), `.wdd`/`.wda` (analysis), `.sty`, `.WPF`, `.wdcoverage`, the `.wdw.cache`/`.wde.cache` files and, in `<project>.cpl/<user>/`, a binary copy of every window, report, class and procedure set. Inside are packed blocks of the same kind as above (byte `4`, sizes, LZW), **without the cipher**. The tool finds each block by its header and keeps it only if it unpacks to its declared size.

| File | What its blocks hold | Use |
|---|---|---|
| `QRY_*.WDR` | the SQL, one record per line with author and date; the tables, items and parameters it binds; the query editor's object graph; a thumbnail | `queries.json`: query name → SQL. No export from WINDEV needed |
| `<project>.wdp` | project code (declarations, initialisation, constants) one record per line, each followed by its author (an empty line is a record without text); the project explorer's folders with their elements; configurations (`32-bit Windows executable`…); editor resources | `project/<project>.code.wl`: the start-up code when the `.wdp` is not in text format (220 lines here: constants, connection set-up from an INI file, schema update); `project.json` → `folders`: the authors' own grouping of windows (back office, front office, monitor…), a ready-made slice list |
| `<project>.cpl/<user>/*.wdw`, `*.wde` | the same description and code as the text file, in binary | a second copy to compare with; the only copy when the project was never switched to text format |
| `*.wdw.cache`, `*.wde.cache` | description, compiled state and a **thumbnail** of the window or report as WINDEV draws it (about 150 px) | `images/`: a picture of every window without the dossier — small, but enough to see a layout is right |
| `<project>.ana/<project>.wda` | the whole analysis (files, items, keys, links, captions) | the `.xdd` beside it is the same content as XML: prefer it |
| `*.wdw.wcw`, `.wbw`, `.wrw` in `.cpl/<user>/00000000/` | compiled code with WINDEV's event labels (`Click BTN_Save`) | already used by `event_legend.py` |

Blocks that are not SQL or images are listed with their strings (`text`); `--blocks` saves each one for closer reading. `<project>.wdd` has no such block in this project (it is stored another way): use the `.xdd`.

### The skin: what a style name stands for

`Templates/WD/<skin>/<skin>.sty` is a PCS container that is **not packed**: its strings are readable in place. Each style is one record in the layout a control uses — fonts with their alignment and text colour, frames, image files — opened by the WINDEV version that wrote it (`25.0.225.3`) and closed by the style's name (`BTN_Ok`, `SAI_Simple`). The decoder writes `skin/<skin>.json` (402 styles per skin here) and compares each control with the style it names: `differs_from_style` lists what the control changed, one line per value (`fonts[0].colour: #fe0000 (style #2d2d2d)`).

That turns "match the screenshot" into two smaller jobs: reproduce each skin style once (its fonts, colours and images are listed), then apply per control only the listed changes. A control with a style and no `differs_from_style` needs nothing of its own.

## 3. Other files worth reading

| File | Format | What it gives a migration |
|---|---|---|
| `<project>.xdd` | XML | the schema (already read by `inspect_windev.py`) |
| `<project>.wdu` | text, one path per line: an element, then the files it uses | `project.json` → `used_files`: images, skin files and external files per element → the asset list |
| `<project>.REP` | text | each data file's name and physical location |
| `<project>.WPF` | PCS, plain strings | a profiler run, when one was recorded: the events, procedures and WLanguage functions the application executed during it |
| `<project>.env` | UTF-16 INI | editor settings; not needed |
| `HstDuree.log` | UTF-16 CSV | who worked on the project and when; not needed |
| `Exe/*.fic`, `.ndx`, `.mmo` | HFSQL | the data: export through the ODBC driver ([data export](../scripts/windows/README.md)), never by hand |
| `Exe/*.ini`, `CONFIG.INI` | text | deployment configuration the code reads |
| `Templates/`, `*.sty`, `*.wdy` | images, PCS | the skin: images are usable as is (`skin_assets.py`); the `.sty` holds every style's fonts, colours, frames and images (`skin/<skin>.json`, above) |

### What a full survey of one project left unread

Every key of the text sources and every file type of the project folder was listed and checked against what the tools read (243 windows and copies, 83 reports, 16 classes, 4 procedure sets).

- **Text sources: nothing left.** Besides code, names, types and `internal_properties`, the only other keys are identifiers, a `description` per window, `original_name` (the template a window was created from) and `enabled : false` on event slots. No disabled slot holds code here (1,283 code blocks checked), so no code is silently dead; check that count on another project before trusting it there.
- **`<project>.wdcoverage`** (code coverage of the last test runs) and **`<project>.wdd`** are PCS files whose body is neither packed nor under the cipher of `internal_properties`: not read. The `.wdd` is the analysis, which the `.xdd` gives in XML. Coverage would say which lines the authors' tests ran; nothing else holds that.
- **`<project>.waudit`**, `.wdap`, `.mdf`, `.ref`, `.wtp`, `.wlr`: editor state and build leftovers, a few hundred bytes each.
- **Inside the decoded chunks**: a table's own options, the tick-mark properties not named above, a report control's alignment and borders, where a file-bound list says "loaded in memory", and the records of predefined button actions. The audit lists each control they touch.

## 4. What stays outside the files

- **Runtime behavior**: what a dialog's Esc does, values set by code at opening, data-dependent states. From the code, and where the code cannot settle it, from the running application.
- **Predefined button actions** (the encoded event slots of `evidence_report.py`): each slot's `internal_properties` now decodes like any other; the records are small and not yet named. Until they are, the proposed answers stay.
- **Fields not yet named** (section 1): present in the chunks; each control's differences from the usual values of its kind are listed in `audit.json`.

## 5. How this was established, and its limits

The packing was first measured on the files alone: values with one differing property share long runs of bytes and differ by fixed patterns, which showed a keyed transform over the whole value instead of real encryption. The exact routine and its key were then read from the editor's own text-format reader (`wdfen.dll` of a WINDEV 28 Express installation), which unpacks the same values. No WINDEV code is included or run by the tool.

Decoding your own project's files to migrate it is interoperability; reading a vendor's library to do so is regulated differently by country and by licence terms. Check yours before redistributing the decoder or its key. The dossier and the running application remain the reference when a decoded value and they disagree: record the difference, do not pick silently.
