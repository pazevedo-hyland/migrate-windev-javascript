# Windows data export

Exports every table of an HFSQL database through PC SOFT's HFSQL ODBC driver: a lossless SQLite copy, CSV files and a manifest. Without the analysis (`.wdd`), ODBC cannot open the files: use the [WDMap export](#wdmap-export-without-the-analysis) instead. Static UI evidence (captions, tab order, masks, window images, query SQL) comes from WINDEV's project documentation instead — see [dossier_extract.py](../README.md#dossier_extractpy--windevs-project-documentation-as-data).

## Steps

1. On a Windows PC, install Python 3.10+ and `py -m pip install pyodbc`, then PC SOFT's **HFSQL ODBC driver** (free, from PC SOFT's download pages for your WINDEV version).
2. Copy the data folder (`.fic`/`.ndx`/`.mmo`) — or, if the application connects to an HFSQL **server** (a server `.ini` next to the executable, `HOpenConnection` in the project code), a backup of that database. Never export from production directly.
3. Create an ODBC data source ("ODBC Data Sources (64-bit)" → Add → HFSQL driver) pointing at the **copy**.
4. Export:

   ```bat
   py scripts\windows\export_odbc.py --dsn MigrationCopy --out C:\migration\data
   ```

`data.sqlite` keeps every value as the driver returns it — text (dates ISO 8601, decimals exact), bytes as BLOB, NULL apart from the empty string — and is the copy to profile ([data_profile.py](../README.md#data_profilepy--what-the-legacy-data-really-is)) and import from. Every table is also a UTF-8 CSV, where NULL and an empty string look alike. `manifest.json` records, per table, the rows read **and the table's own `COUNT(*)`** — the export fails when they differ — plus column types, null and binary counts per column, a hash of the rows, the driver and the Python architecture. Exporting the same tables before and after a scripted action in the legacy app gives a golden scenario's expected data ([compare_exports.py](../README.md#compare_exportspy--golden-master-and-reconciliation)).

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

**Safety and log.** It never overwrites: a table whose `<Table>.XML` exists is skipped (`SKIPPED_EXISTS`), so a stopped run resumes where it was, and a table where WDMap asks to confirm an overwrite fails. Each worker appends one line per table to `_log_worker<N>.tsv`: name, `.fic` size, status, rows found in the XML, seconds. **Export is greyed out on empty tables**: they are logged `EMPTY_OR_NO_EXPORT` with 0 rows. Other statuses (`OPEN_TIMEOUT`, `NO_MENU`, `EXPORT_TIMEOUT`…) are failures to retry with `-Tables`.

**What the XML holds.** An `ISO-8859-1` header over Windows-1252 bytes; one element per row named after the table, one child per item. Values are WDMap's text: dates and times as `YYYYMMDDHHMMSSmmm` (`00000000000000000` is the empty date), booleans `0`/`1`, text memos inline with CR LF; password items can contain control characters, so strict XML parsers fail — `wdmap_xml_to_sqlite.py` reads it tolerantly and checks its row counts against the log. **Binary memos are not exported**: read them with [hfsql_mmo.py](../README.md#hfsql_mmopy--memo-files-read-directly). **WDMap's row order is not the physical record order**, so a binary memo must be linked to its row by a key or by the memo pointer in the record ([format notes](../../docs/hfsql-classic-format.md)), never by position.

**Limits.** Not unit-tested (it needs WDMap and a desktop session); validated manually on a real WINDEV 28 database of 689 tables: 265 exported, 424 empty correctly detected, about 7 s per table with 4 workers. It depends on WDMap's menu layout and dialog ids (WINDEV 28); another version may need the key sequence adjusted — the status says which step failed. Files protected by a password are not covered. Licensing: the Express edition's WDMap must not be used commercially ([08](../../08-data-migration.md#no-analysis-wdd-recover-the-data-anyway)).
