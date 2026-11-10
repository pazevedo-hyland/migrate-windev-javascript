# Windows data export

Exports every table of an HFSQL database through PC SOFT's HFSQL ODBC driver: a lossless SQLite copy, CSV files and a manifest. If `export_odbc.py` crashes while connecting (HFSQL 28), use [the ANSI exporter](#when-export_odbcpy-crashes-the-ansi-exporter-hfsql-28). No driver at hand, or not on Windows: [`hfsql_read.py`](../README.md#hfsql_readpy--the-data-without-a-driver) reads the `.fic`/`.mmo` files directly and writes the same output. Static UI evidence (captions, tab order, masks, window images, query SQL) comes from WINDEV's project documentation instead — see [dossier_extract.py](../README.md#dossier_extractpy--windevs-project-documentation-as-data).

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

## Status

`export_odbc.py` is tested on GitHub's Windows runners against a real ODBC driver (SQL Server LocalDB: accents, decimals, dates, NULLs). On the real project, the HFSQL ODBC driver (32-bit, see above) read every table: 17 tables, about 180,000 rows, text in clean UTF-8 — with composite keys arriving as binary columns ([data_profile.py](../README.md#data_profilepy--what-the-legacy-data-really-is) flags them). That first export did not use this script: its composite keys were read as text (bytes damaged, rebuildable from their parts), a composite link column came out empty, and no source row counts were kept. This script reads bytes as bytes and checks every count; run it for the next export.
