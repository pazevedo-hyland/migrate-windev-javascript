# HFSQL Classic files: what is plain, what is not

Observed on WINDEV 28 data files with no file password, while recovering a database without its analysis ([08](../08-data-migration.md#no-analysis-wdd-recover-the-data-anyway)). These are observations, not PC SOFT documentation: check them on your own files. All integers are little-endian.

## Memo file (`.mmo`) — decoded

Read by [`scripts/hfsql_mmo.py`](../scripts/README.md#hfsql_mmopy--memo-files-read-directly); on a real database, 233 memo files and about 533,000 memos with no error.

- Header starting with `PCS\0`; blocks start at offset `0xD2`. Walking from block to block by each block's size lands exactly on the end of the file.
- **Block header** (21 bytes), then the payload:

  | Offset | Type | Meaning |
  |---|---|---|
  | 0 | u8 | size class: the block occupies `2^class` bytes, header included |
  | 1 | u8 | role: `F4` single-block memo, `E4` first block of a chain, `C4` middle, `D4` last, `00` free |
  | 2 | u32 | payload length |
  | 6 | u32 | payload length, repeated |
  | 10 | u8 | flag |
  | 11 | u64 | offset of the next block, `FFFFFFFFFFFFFFFF` = none |
  | 19 | u16 | unknown |

- **Memo content** = the payloads concatenated along the chain (chains need not be contiguous):

  | Type byte | Layout after `u32 item, u8 type` |
  |---|---|
  | `0x0C` text | `u32 record number`, `u32 0`, `u16 flags`, `u32 length`, the text: Windows-1252, sometimes UTF-16LE |
  | `0x0D` binary | same header, then a small wrapper and the file bytes (PNG, JPEG, RIFF…, found by signature) |
  | `0x00` binary with names | `u32 Unix time`, `u16 len1`, `u16 len2`, original full path + NUL, short path + NUL, then `01 u32 size u32 crc u32 u32 u16(0x8001) u32 data_length u16 width u16 height` and the data. No record number |

  The leading `u32 item` holds small values; it is probably the memo item's position in the record (unconfirmed). The original path of an imported file is often kept, and can reveal user or machine names: treat it as personal data.

## Data file (`.fic`) — partly plain

- Header `PCS\0`, a small header, then two 32-hex-digit GUID strings: the first shared by every file of the database, the second per file.
- **The table description** (item names, types, sizes) near offset `0x5A` **is scrambled. It is not decoded here, deliberately**: decoding it would mean reverse-engineering PC SOFT's protection. WDMap reads it and exports the names with the data ([wdmap_export.ps1](../scripts/windows/README.md#wdmap-export-without-the-analysis)).
- **Records are plain** in files without a password: fixed-width rows, strings NUL-padded ANSI (Windows-1252).
  - Each row starts with a status byte (`0x10` = active), a `u16` change counter and a `u32` Unix timestamp of the last change.
  - Record 0 starts after the last run of eight `FF` bytes in the control block; the record size is the smallest stride at which every slot starts with a status byte. This heuristic found it for 675 of 688 tables; without the description, the item boundaries inside a record remain unknown.
  - A **memo item** in a record holds a `u64`: the `.mmo` offset of the memo's first block (`hfsql_mmo.py --offset`). This is the only link for binary memos, since WDMap exports neither them nor rows in physical order.
- A `.fic` holding only its header and record 0 is an empty table, even when its `.ndx` is large (index files are preallocated).

## Not covered

Files protected by a password (encrypted records), HFSQL Client/Server databases, `.ndx` index and `.ftx` full-text files, and other WINDEV versions (the layout may differ: compare with a table you can open in WDMap).
