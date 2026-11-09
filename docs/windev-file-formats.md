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
| Captions | 822 controls with one | 819 of 820 equal; accents correct where the PDF lost them |
| Window size and title | 112 windows | size 111 of 112 equal (the window with a menu bar differs by its height); title 112 of 112 |
| Report control geometry (mm) | 497 controls | 493 of 493 equal |
| Query SQL from binary `.WDR` | 5 of 5 | same text, without the PDF's line wraps |
| SQL of queries embedded in windows and reports | 19 of 20 | not in the dossier at all |
| Fonts and text colours | every control | not printed by the dossier: read, not compared |
| Window and report thumbnails | 219 images | — |

A screen layout generated with no PDF at all (`screen_layout.py` on one 77-control window with tabs, tables and a supercontrol) equals the layout validated earlier from the dossier on every position, size, kind, anchor, tab order, state, Visible tick, button type and button image. What the PDF still adds there: planes, the other tick-mark properties, alignment, masks, input types, caption widths and table options.

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

- **Strings** are framed: one zero byte when empty, else `ff ce 88 f1`, total length (u32), the text, a zero byte, `fe ed 98 e1`. The tool lists every string of every chunk in file order (`strings`), in the project's code page (`--encoding`, default Windows-1252), plus UTF-16 runs (report captions).
- **Sub-records start with a version number** (`0x25f`, `0x262`, `0x25b`…), which is how a record is recognised.
- **Layout is fixed per control type**, so an offset found on one button holds for all buttons of that format.

Which chunk holds what (id, version):

| Element | Chunks | Contents |
|---|---|---|
| Window control | `1`, then `0` (v14) | `1`: identifiers and links. `0`: type-specific style (fonts, colours, style name such as `170 AquaBlue.BTN_Simple`), the common block, type-specific tail (button caption and image, masks) |
| Table column | `1`, `0` | `0`: version, width, caption, linked item (`Customer.Name`) |
| Column `content`, combo `dropdown`, `calendar` | `0` | the embedded edit/combo/calendar control |
| Window | `1`, `6`, `0` | `6`: platform, creator, skin template. `0`: version at 16, then x, y, width, height; title; background image; file name |
| Menu option | `0` (and `1`) | caption, fonts |
| Report, band, report control | `15` (v14), `1` | `15`: name, then top, bottom, left, right as doubles in millimetres; font; caption. `1`: the same captions in UTF-16 |
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
| anchor rates | 4 × u32, 12 bytes later | right, width, bottom, height, in thousandths |
| button type | byte 50 before the end of the chunk | 0 normal, 1 validate, 3 abort (2 and 4 not observed) |
| button caption, background image, number of background states, image | a record 107 or 111 bytes after the anchor rates | string, string, u32, string. Kept only when these are exactly the first strings found there |
| tab style | u32, 58 bytes before the end of a tab's chunk | 0: panes start 26 px below the tab's top; 2: 2 px. Other values not measured |

**Positions.** Add the parents' x and y to get window coordinates; a **tab** parent also adds where its panes start (its style, above). A tab of an unmeasured style gives its children no window position, and a **table** places controls in cells: those keep parent-relative `x`/`y` only. Each pane of a tab is an element of its own (owner `tabs`, with its caption); a control directly inside a tab carries `pane`, the number of its pane. A pane is not a WINDEV plane: planes are not named yet.

### Mapping one more field

Everything else a control has (colours, fonts, masks, planes, input type, column options) is in the same chunks, not yet named. To name one:

1. Run with `--raw` to keep each chunk as hex.
2. Take two controls of the same type that differ in that property only (or the dossier's value for a few hundred controls) and compare their chunks from the common block signature, or from the end of the chunk.
3. Keep an offset only when it explains **every** control of that type, as the table above does; add it to `control_fields` with a test.

A property changed in WINDEV on a copy of one window, saved in text format and decoded before and after, settles an offset in minutes.

### Fonts, options, embedded queries

- **Fonts**: a font is a Windows `LOGFONT` (height, width, escapement, orientation, weight, italic, underline, strike-out, character set, four precision bytes) whose face name is a framed string. A negative height is pixels at 96 dpi (−11 = 8.25 pt). The four bytes after the face are read as the text colour (red, green, blue, 0). Each element lists its `fonts` in file order: a button has four (one per state), an edit its caption font and its input font. Which font belongs to which part is by order, not named.
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
| `<project>.wdp` | project code (declarations, initialisation, constants) one record per line; the element list; configurations (`32-bit Windows executable`…); editor resources | project-level code when the `.wdp` is not in text format |
| `<project>.cpl/<user>/*.wdw`, `*.wde` | the same description and code as the text file, in binary | a second copy to compare with; the only copy when the project was never switched to text format |
| `*.wdw.cache`, `*.wde.cache` | description, compiled state and a **thumbnail** of the window or report as WINDEV draws it (about 150 px) | `images/`: a picture of every window without the dossier — small, but enough to see a layout is right |
| `<project>.ana/<project>.wda` | the whole analysis (files, items, keys, links, captions) | the `.xdd` beside it is the same content as XML: prefer it |
| `*.wdw.wcw`, `.wbw`, `.wrw` in `.cpl/<user>/00000000/` | compiled code with WINDEV's event labels (`Click BTN_Save`) | already used by `event_legend.py` |

Blocks that are not SQL or images are listed with their strings (`text`); `--blocks` saves each one for closer reading. `<project>.wdd` has no such block in this project (it is stored another way): use the `.xdd`.

## 3. Other files worth reading

| File | Format | What it gives a migration |
|---|---|---|
| `<project>.xdd` | XML | the schema (already read by `inspect_windev.py`) |
| `<project>.wdu` | text, one path per line | every file each element uses: images, skin files, external files → the asset list |
| `<project>.REP` | text | each data file's name and physical location |
| `<project>.WPF` | PCS, plain strings | a profiler run, when one was recorded: the events, procedures and WLanguage functions the application executed during it |
| `<project>.env` | UTF-16 INI | editor settings; not needed |
| `HstDuree.log` | UTF-16 CSV | who worked on the project and when; not needed |
| `Exe/*.fic`, `.ndx`, `.mmo` | HFSQL | the data: export through the ODBC driver ([data export](../scripts/windows/README.md)), never by hand |
| `Exe/*.ini`, `CONFIG.INI` | text | deployment configuration the code reads |
| `Templates/`, `*.sty`, `*.wdy` | images, PCS | the skin: images are usable as is (`skin_assets.py`) |

## 4. What stays outside the files

- **Runtime behavior**: what a dialog's Esc does, values set by code at opening, data-dependent states. From the code, and where the code cannot settle it, from the running application.
- **Predefined button actions** (the encoded event slots of `evidence_report.py`): each slot's `internal_properties` now decodes like any other; the records are small and not yet named. Until they are, the proposed answers stay.
- **Fields not yet named** (section 1): present in the chunks; each control's differences from the usual values of its kind are listed in `audit.json`.

## 5. How this was established, and its limits

The packing was first measured on the files alone: values with one differing property share long runs of bytes and differ by fixed patterns, which showed a keyed transform over the whole value instead of real encryption. The exact routine and its key were then read from the editor's own text-format reader (`wdfen.dll` of a WINDEV 28 Express installation), which unpacks the same values. No WINDEV code is included or run by the tool.

Decoding your own project's files to migrate it is interoperability; reading a vendor's library to do so is regulated differently by country and by licence terms. Check yours before redistributing the decoder or its key. The dossier and the running application remain the reference when a decoded value and they disagree: record the difference, do not pick silently.
