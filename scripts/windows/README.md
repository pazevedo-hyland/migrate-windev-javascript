# Windows data export

Exports every table of an HFSQL database through PC SOFT's HFSQL ODBC driver: a lossless SQLite copy, CSV files and a manifest. Static UI evidence (captions, tab order, masks, window images, query SQL) comes from WINDEV's project documentation instead — see [dossier_extract.py](../README.md#dossier_extractpy--windevs-project-documentation-as-data).

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

## Status

`export_odbc.py` is tested on GitHub's Windows runners against a real ODBC driver (SQL Server LocalDB: accents, decimals, dates, NULLs). On the real project, the HFSQL ODBC driver (32-bit, see above) read every table: 17 tables, about 180,000 rows, text in clean UTF-8 — with composite keys arriving as binary columns ([data_profile.py](../README.md#data_profilepy--what-the-legacy-data-really-is) flags them). That first export did not use this script: its composite keys were read as text (bytes damaged, rebuildable from their parts), a composite link column came out empty, and no source row counts were kept. This script reads bytes as bytes and checks every count; run it for the next export.
