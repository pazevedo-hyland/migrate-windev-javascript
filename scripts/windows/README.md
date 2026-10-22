# Windows capture kit

Collects the runtime evidence a migration needs — data, screenshots, control trees, tab order — from a running WINDEV application **without WINDEV and without clicking through it**. One unattended session on any Windows PC. A coding agent on that PC can run all of it for you: paste [templates/windows-capture-prompt.md](../../templates/windows-capture-prompt.md).

## 0. What to bring

- A **copy** of the application's install folder from a machine where it runs today: the `.exe`, the WINDEV runtime DLLs next to it (`wd*.dll`), its `.ini` files, and its data (`.fic`/`.ndx`/`.mmo`). If the `.ini` or project code points at an HFSQL **server**, bring a backup or copy of that database instead and note the connection settings.
- The inspector output and `capture-plan.json` (step 2), generated on any machine from the text sources.
- If the app has a login: a test user's name and password.

Never run this against production data or the live install folder.

## 1. Prepare the machine (once)

1. Install Python 3.10+ (python.org, "Add to PATH"), then `py -m pip install pywinauto pillow pyodbc`.
2. Install PC SOFT's **HFSQL ODBC driver** (free, from PC SOFT's download pages for your WINDEV version).
3. Put the copy in, e.g., `C:\capture\app\` and create an empty marker file in it (and in a separate data folder, if any):

   ```bat
   type nul > C:\capture\app\.migration-capture-copy
   ```

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

## No Windows PC? A GitHub-hosted Windows VM

With **fake or sanitized data only**, the same capture can run unattended on GitHub's Windows runners from a **private** repository: copy [templates/github-capture.yml](../../templates/github-capture.yml) into `.github/workflows/`, put the install-folder copy (exe, `wd*.dll`, data — without any server configuration file, so the app uses its local files) in `app/`, the text sources in `sources/`, this playbook in `playbook/`, set the test login as the `MIGRATION_APP_USER` / `MIGRATION_APP_PASSWORD` secrets and the executable name as the `APP_EXE` variable, then start the workflow. The evidence comes back as a workflow artifact. The WINDEV runtime DLLs must come from an installed copy of the application (they are redistributed with it); never download them from unofficial sources. No ODBC export runs there: decode or export the data separately.

## Limits

- Tested end to end on GitHub's Windows runners (`.github/workflows/check.yml`, `tests/windows_e2e/`) against a WinForms stand-in: login, caption-only menus with submenus, a button found by automation id, tab order, a confirmation dialog on close (captured, never answered, app restarted), and a window that writes on open (run stopped by the data guard). `export_odbc.py` is tested against a real ODBC driver.
- Not yet run against a real WINDEV app: whether WINDEV exposes captions and automation ids through UI Automation is only known after `--probe` on the real application. Run it first; a `no-go` verdict means screenshots still work but routes need manual help.
- Captions are matched from control names (`OPT_Ordens_de_Reparação` → "Ordens de Reparação"); ambiguous matches are refused, not guessed.
- Reports are not printed; use the code-defined layouts and historical data (chapter 10).
