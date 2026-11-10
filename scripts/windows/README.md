# Windows data export

Exports every table of an HFSQL database through PC SOFT's HFSQL ODBC driver: a lossless SQLite copy, CSV files and a manifest. If `export_odbc.py` crashes while connecting (HFSQL 28), use [the ANSI exporter](#when-export_odbcpy-crashes-the-ansi-exporter-hfsql-28). No driver at hand, or not on Windows: [`hfsql_read.py`](../README.md#hfsql_readpy--the-data-without-a-driver) reads the `.fic`/`.mmo` files directly and writes the same output. Static UI evidence (captions, tab order, masks, window images, query SQL) comes from WINDEV's project documentation instead — see [dossier_extract.py](../README.md#dossier_extractpy--windevs-project-documentation-as-data). Without any analysis (neither `.wdd` nor `.wda`), neither the driver nor the reader can open the files: use the [WDMap export](#wdmap-export-without-the-analysis).

## Steps

1. On a Windows PC, install Python 3.10+ and `py -m pip install pyodbc`, then PC SOFT's **HFSQL ODBC driver** (free, from PC SOFT's download pages for your WINDEV version).
2. Copy the data folder (`.fic`/`.ndx`/`.mmo`) — or, if the application connects to an HFSQL **server** (a server `.ini` next to the executable, `HOpenConnection` in the project code), a backup of that database. Never export from production directly.
3. Create an ODBC data source ("ODBC Data Sources (64-bit)" → Add → HFSQL driver) pointing at the **copy**. From a script: `Add-OdbcDsn -Name MigrationCopy -DriverName HFSQL -DsnType User -Platform 64-bit`, then set the driver's own keys, which `Add-OdbcDsn -SetPropertyValue` leaves empty for HFSQL: in `HKCU\Software\ODBC\ODBC.INI\MigrationCopy` set `Analyse` (the copy's `<project>.wdd`) and `RepFic` (the copy's folder). A DSN-less connection string is refused by the driver ("insufficient connection string").
4. Export:

   ```bat
   py scripts\windows\export_odbc.py --dsn MigrationCopy --out C:\migration\data
   ```

`data.sqlite` keeps every value as the driver returns it — text (dates ISO 8601, decimals exact), bytes as BLOB, NULL apart from the empty string — and is the copy to profile ([data_profile.py](../README.md#data_profilepy--what-the-legacy-data-really-is)) and import from. Every table is also a UTF-8 CSV, where NULL and an empty string look alike. `manifest.json` records, per table, the rows read **and the table's own `COUNT(*)`** — the export fails when they differ — plus column types, null and binary counts per column, a hash of the rows, the driver and the Python architecture. Exporting the same tables before and after a scripted action in the legacy app gives a golden scenario's expected data ([compare_exports.py](../README.md#compare_exportspy--golden-master-and-reconciliation)).

## When the driver cannot read the files

- **The process exits with an access violation (exit code 139 / -1073741819) on connect**, in both 32- and 64-bit, even for a data source that worked before: the installed driver (seen with 28.0) cannot open this analysis. Use the HFSQL driver of the project's WINDEV version, or have someone with WINDEV export the tables (HFSQL Control Center → export to CSV, or a small WINDEV procedure with `HExportCSV`) into `legacy/data/` with their row counts. Record it under "Decisions needed" and continue with a synthetic seed.
- **Files start with `PCS` followed by a hex key**: they are encrypted (password-protected HFSQL files). Raw reading is impossible; the export needs the password through the driver or WINDEV.
- **`CONFIG.INI` points at an HFSQL server** (`UTILIZAR_BD_LOCAL=0`-style keys, `HOpenConnection` in the code): the `.fic` files next to the executable are a local copy that may be stale; ask for a server backup.

## ODBC architecture troubleshooting

The Python process and the HFSQL ODBC driver must have the same architecture. On 64-bit Windows, `C:\Windows\System32\odbcad32.exe` configures 64-bit drivers and `C:\Windows\SysWOW64\odbcad32.exe` 32-bit ones; data sources are architecture-specific ([Microsoft: ODBC administrator](https://learn.microsoft.com/en-us/troubleshoot/sql/database-engine/install/windows/odbc-driver-install-checking)).

If the exporter exits while opening the connection, check the Python architecture and the registered drivers:

```bat
py -c "import struct, pyodbc; print(struct.calcsize('P') * 8); print(pyodbc.drivers())"
```

On the real project, a 64-bit `pyodbc` connection ended the process while a 32-bit connection opened the data source — an observed workaround, not a documented driver limitation. If the 32-bit driver is the one that works, install 32-bit Python and `pyodbc`, create the data source with the 32-bit administrator and run the exporter with that interpreter:

```bat
py -3-32 -m pip install pyodbc
py -3-32 scripts\windows\export_odbc.py --dsn MigrationCopy --out C:\migration\data
```

Use a new output folder for each attempt: the exporter refuses to overwrite one.

## When `export_odbc.py` crashes: the ANSI exporter (HFSQL 28)

With the HFSQL 28 ODBC driver, `export_odbc.py` can end while connecting with **exit code 139** or an access violation (`0xC0000005`) and no Python traceback, even from 32-bit Python. On the tested installation the driver's Unicode entry points (`SQLDriverConnectW`…, which `pyodbc` calls) crashed or failed; its **ANSI** entry points work. `hfsql-export.ps1` calls only those, through a small C# P/Invoke adapter (`HfSqlOdbcAnsi.cs`) compiled by the 32-bit Windows PowerShell at run time — nothing to install beyond the driver:

```bat
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass ^
  -File scripts\windows\hfsql-export.ps1 -Source C:\app\Exe -Analysis C:\app\Exe\App.wdd -Work C:\migration\run1
py scripts\windows\hfsql_jsonl.py --in C:\migration\run1\jsonl --out C:\migration\data
```

- `-Source` is the folder with the `.fic`/`.ndx`/`.mmo`/`.ftx` files, `-Analysis` the application's `.wdd`. Nothing there is written: the files are copied to `<Work>\source\`, each copy is SHA-256 checked, and the originals are re-hashed after the copy and after the export (close the legacy application first).
- A temporary per-user DSN (`HKCU`) points the driver at the copy; it is deleted in a `finally` block, also on failure. No ODBC administrator step.
- One `<table>.jsonl` per `.fic`: a header line (`table`, `count`, `columns` with ODBC type/size/scale/nullable, `encoding`), then one JSON array per row — text decoded from the ANSI code page (`-CodePage`, default 1252) with conversion errors refused, floating-point columns read natively and written round-trip, binary as `{"base64": …}`, NULL as `null`. Each table's rows read must equal its `COUNT(*)` before **and** after the read, or the export fails.
- `hfsql_jsonl.py` (standard library, any OS) turns the JSONL folder into **exactly `export_odbc.py`'s output** — `data.sqlite`, one CSV per table, `manifest.json` with rows and `COUNT(*)` — by feeding it to the same `export()` function, so profiling, comparison and importers need no second code path. It refuses malformed rows and fails when rows and count differ.
- Options: `-Driver <path to wd<version>hfo.dll>` when the driver is not registered as `HFSQL`; `-CodePage` for non-Western data. Output for a calling program (an installer's import wizard, say): `STEP …` lines, one line per table, and on failure one `ERROR <message>` line with exit code 1.
- `<Work>\source\` and the JSONL hold business data: delete the work folder once `data.sqlite` is checked.

Measured on a real WINDEV 28 / HFSQL Classic application (driver 28, 32-bit, Windows 11): `export_odbc.py` crashed while connecting; the ANSI exporter read **30 tables / 24,915 rows**, every table's rows equal to its `COUNT(*)` before and after; `hfsql_jsonl.py` produced the same 30 tables, row for row, as the project's own converter. Not tested: other HFSQL versions, HFSQL Client/Server databases, non-1252 code pages. The method was first used in the gestao-oficinas migration.

On another machine, `pyodbc` ended with an **access violation** against the HFSQL driver in both 32- and 64-bit, while .NET's `System.Data.Odbc` from PowerShell opened the same data source. `export_odbc.py` needs `pyodbc`; use .NET to confirm the driver and the data source work before blaming them:

```powershell
$c = New-Object System.Data.Odbc.OdbcConnection "DSN=MigrationCopy"; $c.Open()
$q = $c.CreateCommand(); $q.CommandText = 'SELECT COUNT(*) FROM "Customers"'; $q.ExecuteScalar(); $c.Close()
```

Remember that the driver needs the analysis (`.wdd`): without it, see [the WDMap export](#wdmap-export-without-the-analysis).

## Status

`export_odbc.py` is tested on GitHub's Windows runners against a real ODBC driver (SQL Server LocalDB: accents, decimals, dates, NULLs). On the real project, the HFSQL ODBC driver (32-bit, see above) read every table: 17 tables, about 180,000 rows, text in clean UTF-8 — with composite keys arriving as binary columns ([data_profile.py](../README.md#data_profilepy--what-the-legacy-data-really-is) flags them). That first export did not use this script: its composite keys were read as text (bytes damaged, rebuildable from their parts), a composite link column came out empty, and no source row counts were kept. This script reads bytes as bytes and checks every count; run it for the next export.

## WDMap export without the analysis

When the `.wdd` is lost, ODBC cannot open the files ([08](../../08-data-migration.md#no-analysis-wdd-recover-the-data-anyway)). PC SOFT's **WDMap** (`C:\PC SOFT\<WINDEV version>\Programs\WDMAP.exe`) opens a `.fic` given on its command line, reads the description the file carries, and exports the table to XML with the real column names. `wdmap_export.ps1` automates it for a whole folder, invisibly:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\wdmap_export.ps1 -DataDir C:\data -OutDir C:\migration\xml -Workers 4
py scripts\wdmap_xml_to_sqlite.py C:\migration\xml --data-dir C:\data --out C:\migration\data
```

Work on a copy of the data folder. `-WDMap <path>` overrides the default (the newest `C:\PC SOFT\*\Programs\WDMAP.exe`); `-Tables A,B` limits the run; `-Workers N` starts N WDMap instances, each taking every N-th table.

**How it works.** WDMap is started with `CreateProcess` on a separate desktop (`CreateDesktop`, `STARTUPINFO.lpDesktop`): nothing appears on the user's screen and no real keystroke is sent — the user keeps working. The script then posts window messages: `WM_SYSKEYDOWN 'F'` (Alt+F) to the main window, `E` (Export) and `DOWN, DOWN, RETURN` ("to an XML file") to the untitled WinDev popup windows that appear. In the Save dialog (`Select .XML file`), the file-name field (`Edit`, control id **1001**) ignores `WM_SETTEXT`, so the path is typed into it with `WM_CHAR` before `BM_CLICK` on button id 1. The export is done when WDMap opens a second `WDMap - <table>.fic` window (its confirmation); then the process is ended.

**Safety and log.** It never overwrites: a table whose `<Table>.XML` exists is skipped (`SKIPPED_EXISTS`), so a stopped run resumes where it was, and a table where WDMap asks to confirm an overwrite fails. Each worker appends one line per table to `_log_worker<N>.tsv`: name, `.fic` size, status, rows found in the XML, seconds. **Export is greyed out on empty tables**: they are logged `EMPTY_OR_NO_EXPORT` with 0 rows. Other statuses (`OPEN_TIMEOUT`, `NO_MENU`, `EXPORT_TIMEOUT`…) are failures: run the same command again — tables with an XML are skipped, failed ones are retried — or retry them with `-Tables`. On the real database, the first table of each worker failed once with `NO_MENU` (startup timing on a fresh hidden desktop) and succeeded on the retry. `wdmap_xml_to_sqlite.py` lets a success in any log override an earlier failure.

**What the XML holds.** An `ISO-8859-1` header over Windows-1252 bytes; one element per row named after the table, one child per item. Values are WDMap's text: dates and times as `YYYYMMDDHHMMSSmmm` (`00000000000000000` is the empty date), booleans `0`/`1`, text memos inline with CR LF; password items can contain control characters, so strict XML parsers fail — `wdmap_xml_to_sqlite.py` reads it tolerantly and checks its row counts against the log. **Binary memos are not exported**: read them with [hfsql_mmo.py](../README.md#hfsql_mmopy--memo-files-read-directly). **WDMap's row order is not the physical record order**, so a binary memo must be linked to its row by a key or by the memo pointer in the record ([format notes](../../docs/hfsql-classic-format.md)), never by position.

**Limits.** Not unit-tested (it needs WDMap and a desktop session); validated manually on a real WINDEV 28 database of 689 tables: 257 tables with rows exported (about 910,700 rows), 431 empty tables correctly detected (confirmed empty against the `.fic` record area), 1 table exported by hand earlier; about 7 s per table with 4 workers, with one retry run. It depends on WDMap's menu layout and dialog ids (WINDEV 28); another version may need the key sequence adjusted — the status says which step failed. Files protected by a password are not covered. Licensing: the Express edition's WDMap must not be used commercially ([08](../../08-data-migration.md#no-analysis-wdd-recover-the-data-anyway)).
