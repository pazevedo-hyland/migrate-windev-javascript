# WINDEV inspection tool

Python 3.10+; standard library only. No WINDEV runtime or AI credentials required.

```sh
python3 scripts/inspect_windev.py /absolute/path/to/project --out analysis-local
python3 -m unittest discover -s tests -v
```

Use a new output directory per run. Existing output is rejected to prevent mixing stale and current evidence. Output cannot equal or contain the source directory. The source is only read.

Recognized extensions: `.wdp`, `.wdw`, `.wde`, `.wdr`, `.wdg`, `.wdc`, `.xdd` (case insensitive). Walks nested source directories, skips symlinks, common build/runtime/cache/backup directories and compilation folders ending in `.cpl`. A nested output directory is excluded. This is a convenience inventory, not a guarantee of complete source discovery; compare it with the WINDEV project element list.

UTF-8/BOM and BOM-marked UTF-16 text are supported for code sources. Other encodings and binary files are reported unresolved. The tool recognizes indented `code : |1-`-style literal blocks and preserves their source line ranges and relative paths. It does not parse the full WINDEV text format, resolve resource strings, decode internal properties, or interpret numeric event identifiers. Inline code formats may not be extracted; inspect original sources when coverage matters.

XDD is parsed as XML with its declared encoding. DTD/entity declarations and non-ASCII-compatible XML are rejected. Each field's raw XML metadata and table attributes are retained, alongside other top-level metadata/relationships. Numeric type/key codes are deliberately not translated into SQL or TypeScript guesses.

Outputs:

- `inventory.json`: recognized source paths, byte sizes, SHA-256 hashes, status and block/table counts.
- `code/<relative-source>.json`: extracted WLanguage blocks and line references.
- `schema/<relative-source>.json`: raw table/field/relationship metadata.

Binary queries are inventoried without claiming to understand them. HFSQL records, PDFs and images are not read. Encoded controls still need screenshots/designer inspection. Results may include passwords embedded in legacy code: keep them local and sanitize before publication. No secret scanner is included.
