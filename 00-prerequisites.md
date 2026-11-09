# 00 — Prerequisites and setup

Do this once; every migration project reuses it.

## A. Accounts

- An AI coding assistant subscription that includes an agentic coding tool (for example Claude with Claude Code). The same account usually serves the planning/review role and the implementation role.
- A Git host: GitHub, or a self-hosted Gitea/GitLab if code must stay on your infrastructure. **Git replaces the WINDEV source manager (GDS).**

## B. Tools on the development machine

- Git, a supported Node.js LTS with npm, the Rust toolchain (`rustup`), and the [Tauri 2 platform prerequisites](https://v2.tauri.app/start/prerequisites/) (Windows: Microsoft C++ Build Tools and WebView2; macOS: Xcode command-line tools; Linux: webkit2gtk and build libraries).
- Python 3.10+ for this playbook's scripts (standard library plus `python3 -m pip install pypdf pillow`; `pyodbc` too on the Windows PC that exports the data).
- An editor (VS Code or similar). Pin the real Node/Rust/dependency versions in the application repository and commit `package-lock.json` and `Cargo.lock`.

## C. The legacy Windows environment

Keep a Windows machine or VM with the **original WINDEV version** and an HFSQL engine/driver. It is needed to:

- run the old application to record [golden scenarios](10-parity-and-verification.md) and screenshots;
- switch the project to the **text backup format** (required for Git, and for the inspector) — see PC SOFT's guide on [sharing projects via Git](https://doc.pcsoft.fr/fr-FR/?9500230&name=partagez_vos_projets_via_git);
- [generate the SQL script from the analysis](https://doc.pcsoft.fr/fr-FR/?2011027), export binary queries as SQL with their parameters, and export HFSQL data to CSV through supported tooling (WINDEV, HFSQL Control Center, or ODBC/OLE DB drivers);
- optionally run the WINDEV 2026 AI Companion `/init_projet` command, which writes a project-context file: put it anywhere under `legacy/`.

Reading a text-format window file does not require WINDEV; reproducing runtime behavior does.

**Decode the sources first.** `scripts/windev_decode.py` reads what the text sources keep in `internal_properties` (geometry, captions, tab order, states, anchors, linked items, button types, report geometry) and the blocks of the binary files (query SQL, project code, window thumbnails), with no WINDEV and no PDF → [what is inside the project files](docs/windev-file-formats.md). A project too large to print its documentation is no longer blocked.

**Then look for a dossier.** If `<project>_Documentation.pdf` is in the project folder (or anyone with WINDEV can generate it, even for a few windows), `scripts/dossier_extract.py` turns it into per-element JSON and images: it names the properties the decoder does not name yet, gives full-size window images, and is the check for the decoded values (`--dossier`).

**No WINDEV machine?** Much of the migration still works from the project folder alone:

- **Readable without WINDEV:** text-format sources (`.wdw`, `.wde`, `.wdp`), the XDD schema, and the compile folder's event labels.
- **Decoded from the same files** (`windev_decode.py`, used by the whole pipeline): control geometry, captions, window titles, tab order, initial state, Visible, anchors, linked items, button types and images, tab panes, report geometry, every query's SQL, project code from a binary `.wdp`, a thumbnail of each window and report.
- **From the dossier PDF, if present:** full-size window images, masks, alignment, planes and the tick-mark properties other than Visible, which the decoder does not name yet; a second source for everything above. The pipeline writes decoded values over the PDF's and keeps the PDF's for the rest.
- **Data:** export it through PC SOFT's HFSQL ODBC driver on any Windows PC ([data export](scripts/windows/README.md)). Do not decode `.fic` files from the schema by hand: record layouts vary by field type and table and a homemade decoder is unreliable.
- **Without a dossier:** properties the decoder does not name yet stay `unresolved` until they are mapped ([how](docs/windev-file-formats.md#mapping-one-more-field)), someone with WINDEV prints the dossier of the windows concerned, or the users decide them. On a WINDEV version the decoder was not measured on, check its `coverage` before trusting a field.

## D. An isolated machine for the coding agent

A coding agent acts like a person at a terminal: it opens shells, installs tools, runs programs. Give it **its own environment** (VM, dev container or cloud sandbox) rather than your workstation:

1. **It does not interrupt you** — no stolen focus, terminals or windows.
2. **It can run while your computer is off** — long tasks continue on a server or cloud VM.
3. **You control its access** — on your workstation it inherits everything *you* can reach (files, shares, saved credentials). A sandbox only sees what you grant it.

Install there a **complete, self-sufficient development environment**, without access to production:

- Node, Rust, Tauri prerequisites, Git;
- the local database engines the target needs (SQLite is embedded; PostgreSQL if a server is planned);
- if the agent must read legacy data directly: an HFSQL server or ODBC driver on a **copy** of the data;
- a local copy of the data — **never production**.

Use a native Windows VM when you must test Windows-specific behavior (printing, COM/DLL, installers). A second **test machine** that replays everything nightly is recommended — see [02 — Infrastructure](02-infrastructure.md).

## E. Collect the legacy material

Create `legacy/` (ignored by Git, but copied privately to every machine where agents work: parity evidence cites `legacy/<path>:<line>`). **Put the WINDEV project folder in it as is**: the tools search `legacy/` for everything below.

**Needed to start:**

| What | Why | How to obtain |
|---|---|---|
| The project in **text format** (`.wdp`, `.wdw`, `.wde`, `.wdr`, `.wdg`, `.wdc`…) **with its `<project>.cpl/` compile folder** and its images | the code, every control, WINDEV's event labels, the skin | Switch the project to text backup format; the project folder holds the rest |
| **The dossier PDF** (WINDEV's project documentation) — optional since `windev_decode.py`, still worth having | full-size window images, masks, tick-mark properties, analysis item type names; the check for decoded captions, geometry, tab order, button types and SQL. If the whole project cannot be printed, print a few windows of each kind | Project documentation print option, to PDF, with windows, reports, queries, code and analysis. Often already in the project folder (`<project>_Documentation.pdf`) |
| The analysis export (`.xdd`) | the schema: tables, keys, types, sizes | Export the analysis (often already in the project folder) |
| The data: the HFSQL files (`.fic`, `.ndx`, `.mmo`), a backup of the HFSQL server, or a copy already exported | the data profile, the import, realistic tests | The agent exports it on Windows with `scripts/windows/export_odbc.py` into `legacy/data/data.sqlite` |

Demo or test data is used as is. Only **personal data** (real customers) is anonymised before any of it is committed — golden data, fixtures — or shared; the kickoff prompt asks which one you have.

**Later, when a slice needs it (optional):** sample PDFs of reports with their input data (report slices); golden scenarios recorded in the running app (before/after exports, [10](10-parity-and-verification.md)); screenshots of runtime states the dossier image cannot show (a filled table, an open dropdown), named after the window. Not needed: the generated SQL script (the schema draft replaces it) and query exports (the dossier has their SQL), unless the dossier is missing.

Also record: WINDEV version, project language (WLanguage code may be written with **French or English keywords**), HFSQL mode (Classic or Client/Server), hardware (printers, scanners, label printers), INI/registry settings, scheduled tasks, and integrations.

More material means better analysis. Configure Git authentication through a credential manager; never put tokens in URLs or files.

Once A → E are in place, follow [06 — Start a migration](06-start-a-migration.md).
