# Windows capture prompt (for a coding agent on the Windows machine)

Paste into Claude Code, Codex or another agent running in a terminal on the Windows PC. The human stays nearby for approvals and must not touch keyboard or mouse during step 6.

```text
Goal: collect runtime evidence from the installed WINDEV application <APP NAME> for a migration, following scripts/windows/README.md in this repository (clone it if needed: <playbook repo URL>). Work only under C:\capture\. Nothing leaves this machine: no uploads, no git push of data or screenshots.

Inputs from the human: <path to capture-plan.json, or to the legacy text sources>, test login <user> with the password in the MIGRATION_APP_PASSWORD environment variable (never print it).

1. Find the installed app: the folder containing <EXE NAME> and its wd*.dll runtime files (search Program Files, Program Files (x86), C:\, the desktop shortcut target). Read its .ini files and report where the data lives: local .fic files or an HFSQL server (host, database). Do not modify anything there.
2. Copy the whole install folder to C:\capture\app\ (and the data folder to C:\capture\data-copy\ if it is elsewhere). If data is on an HFSQL server, stop and ask the human for a copy or backup. Create the empty marker file .migration-capture-copy in each copy.
3. Check Python 3.10+ (`py --version`). If missing, ask the human before installing it (e.g. winget install Python.Python.3.12). Then: py -m pip install pywinauto pillow pyodbc.
4. Check the HFSQL ODBC driver: Get-OdbcDriver | Where-Object Name -match 'HFSQL'. If missing, stop and ask the human to install PC SOFT's HFSQL ODBC driver. Then create a user DSN named MigrationCopy pointing at the COPIED data folder (inspect the driver's registry keys or ODBC dialog fields to find the right property names; ask the human if unsure).
5. Export: py scripts\windows\export_odbc.py --dsn MigrationCopy --out C:\capture\export-1. Check manifest.json: every table of the plan/schema present, row counts plausible. Report problems; do not "fix" data.
6. If no capture-plan.json was provided, generate it: inspect_windev.py on the text sources, then plan_capture.py. Run capture_app.py with --dry-run, show the routes, then ask the human to step away and run it with --login on C:\capture\app.
7. Read capture-report.json. If many controls were "not found", open a few tree.json files to see how the app exposes captions and automation ids, improve the matching in a working copy of capture_app.py, re-copy a FRESH app folder (step 2), and re-run. Stop after three attempts and report. If the run stopped because data files changed, re-copy before any further run.
8. Optional second pass on a fresh copy with --allow-review.
9. Run the export again on the copy and compare with export-1 (python scripts\compare_exports.py with a config keyed on each table's ID column): any difference means a capture step wrote data — report it.
10. Package C:\capture\export-1, C:\capture\screens*, capture-report.json and a short summary (captured / failed / manual windows, problems, matching changes made) into C:\capture\evidence.zip for the human to transfer manually.

Never run against the original install folder or production data, never bypass the marker or the data guard, never answer an application dialog by guessing — capture it and restart instead.
```
