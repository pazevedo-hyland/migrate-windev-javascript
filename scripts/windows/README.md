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

<<<<<<< ours
Every table becomes a UTF-8 CSV; `manifest.json` records row counts, column types and row hashes. Exporting the same tables before and after a scripted action in the legacy app gives a golden scenario's expected data ([compare_exports.py](../README.md#compare_exportspy--golden-master-and-reconciliation)).
=======
   The capture script refuses to run in a folder without this marker.

## 2. Plan the capture (any OS)

```sh
python3 scripts/inspect_windev.py legacy/code --out analysis-local/inspect-1
python3 scripts/plan_capture.py analysis-local/inspect-1 --out analysis-local/capture-plan.json
```

`capture-plan.md` lists each window as `auto` (a caller only opens windows; the window writes nothing on open/close), `auto-review` (callers run other code, no detected writes), `manual` (opening or every route writes) or `unreachable` (no caller in code, e.g. the main window).

## 3. Export the data

Create an ODBC data source ("ODBC Data Sources (64-bit)" → Add → HFSQL driver) pointing at the **copied** data folder, then:

```bat
py scripts\windows\export_odbc.py --dsn GestaoCopy --out C:\capture\data
```

Every table becomes a UTF-8 CSV with `manifest.json` (row counts, column types, row hashes). This is also the "before/after" tool for golden scenarios.

### ODBC architecture troubleshooting

The Python process and HFSQL ODBC driver must have matching architectures. On 64-bit Windows, use `C:\Windows\System32\odbcad32.exe` to configure 64-bit drivers and `C:\Windows\SysWOW64\odbcad32.exe` for 32-bit drivers. System DSNs are architecture-specific; [Microsoft documents the ODBC administrator paths and behavior](https://learn.microsoft.com/en-us/troubleshoot/sql/database-engine/install/windows/odbc-driver-install-checking).

If the exporter exits unexpectedly while opening the connection, first check the Python architecture and registered driver:

```bat
py -c "import struct, pyodbc; print(struct.calcsize('P') * 8); print(pyodbc.drivers())"
```

On one HFSQL setup, a 64-bit `pyodbc` connection terminated the process, while a 32-bit Windows PowerShell ODBC connection opened the DSN. This is an observed workaround, not a general HFSQL driver limitation. If the 32-bit driver is the working one, install 32-bit Python and `pyodbc`, create the DSN with the 32-bit ODBC administrator, and run the same exporter with the 32-bit interpreter:

```bat
py -3-32 -m pip install pyodbc
py -3-32 scripts\windows\export_odbc.py --dsn GestaoCopy --out C:\capture\data
```

Use a new output directory for each attempt because the exporter refuses to overwrite an existing one. Confirm the architecture with `struct.calcsize('P') * 8` before retrying.

## 4. Capture the screens (unattended)

```bat
py scripts\windows\capture_app.py --app-dir C:\capture\app --exe My_App.exe --plan capture-plan.json --out C:\capture\screens --dry-run
set MIGRATION_APP_USER=test
set MIGRATION_APP_PASSWORD=...
py scripts\windows\capture_app.py --app-dir C:\capture\app --exe My_App.exe --plan capture-plan.json --out C:\capture\screens --login
```

Leave the PC alone while it runs (it drives the keyboard and mouse), screen unlocked. For each routable window it opens the route, saves `screenshot.png`, `tree.json` (control types, captions, automation ids, positions, enabled/visible) and `tab-order.json`, closes the window, and checks that **no data file changed**. A confirmation dialog on close is captured, then the app restarts cleanly. Any data change stops the run: restore the copy before continuing.

Second pass, on a **fresh copy**, for windows reached through buttons such as New/Edit:

```bat
py scripts\windows\capture_app.py ... --out C:\capture\screens-review --allow-review --login
```

`--no-tab-order` skips tab-order capture if pressing Tab triggers field-exit code that changes data.

## 5. Bring back

`C:\capture\data\` → `legacy/data/`; `C:\capture\screens*\` → `legacy/screenshots/`; `capture-report.json` lists what was captured, what failed (control not found, timeout) and why. Failed and `manual` windows remain `unresolved` in the parity matrix until someone captures them by hand.
>>>>>>> theirs

## Status

`export_odbc.py` is tested on GitHub's Windows runners against a real ODBC driver (SQL Server LocalDB: accents, decimals, dates, NULLs). It has **not yet been run against the HFSQL ODBC driver**: check the first export's `manifest.json` (row counts per table) against the application before relying on it, and adjust the data-source settings if the driver needs them.
