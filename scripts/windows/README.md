# Windows data export

Exports every table of an HFSQL database to CSV with a manifest, through PC SOFT's HFSQL ODBC driver. Static UI evidence (captions, tab order, masks, window images, query SQL) comes from WINDEV's project documentation instead — see [dossier_extract.py](../README.md#dossier_extractpy--windevs-project-documentation-as-data).

## Steps

1. On a Windows PC, install Python 3.10+ and `py -m pip install pyodbc`, then PC SOFT's **HFSQL ODBC driver** (free, from PC SOFT's download pages for your WINDEV version).
2. Copy the data folder (`.fic`/`.ndx`/`.mmo`) — or, if the application connects to an HFSQL **server** (a server `.ini` next to the executable, `HOpenConnection` in the project code), a backup of that database. Never export from production directly.
3. Create an ODBC data source ("ODBC Data Sources (64-bit)" → Add → HFSQL driver) pointing at the **copy**.
4. Export:

   ```bat
   py scripts\windows\export_odbc.py --dsn MigrationCopy --out C:\migration\data
   ```

Every table becomes a UTF-8 CSV; `manifest.json` records row counts, column types and row hashes. Exporting the same tables before and after a scripted action in the legacy app gives a golden scenario's expected data ([compare_exports.py](../README.md#compare_exportspy--golden-master-and-reconciliation)).

## Status

`export_odbc.py` is tested on GitHub's Windows runners against a real ODBC driver (SQL Server LocalDB: accents, decimals, dates, NULLs). It has **not yet been run against the HFSQL ODBC driver**: check the first export's `manifest.json` (row counts per table) against the application before relying on it, and adjust the data-source settings if the driver needs them.
