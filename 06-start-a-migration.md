# 06 — Start a migration

The universal sequence. Beyond it, **what to build and in which order is decided at framing** ([03](03-scope-and-architecture.md)), not by this guide.

## 1. Set up once

Accounts, tools, legacy Windows environment, isolated agent machine, test machine → [00](00-prerequisites.md), [02](02-infrastructure.md).

## 2. Create the project repository

Create a private repository for the application. Copy `templates/` and `scripts/` from this playbook; add the `.gitignore` entries for `legacy/`, `analysis-local/`, HFSQL data files and `.env`. Install the skills, the shared guard with its pre-commit hook, and your agent's adapter ([04](04-project-memory.md#claude-code-codex-and-other-agents)).

## 3. Collect the sources

Fill `legacy/` with the fixed layout of [00 §E](00-prerequisites.md#e-collect-the-legacy-material). **More material, better analysis.** Name screenshots after windows. Keep originals read-only.

## 4. Inspect

```sh
python3 scripts/inspect_windev.py legacy/code --out analysis-local/inspect-$(date +%Y%m%d)
```

Add `--fallback-encoding cp1252` for older non-Unicode sources, `--extra-ext .wwh` (repeatable) for element types not in the default list (compare with the project's element list in WINDEV), and `--block-key <key>` if `literal_keys` in the inventory shows other embedded sources worth extracting. Review `inventory.json` for binary files, nested projects and missing global procedures; request the missing exports from WINDEV. Review `secret-hints.json`: credentials found are **to be revoked**, not reused. **Spot-check 3–5 `code/*.json` files** against the sources: if `context.names` does not show the right window/control, fix the inspector for your project's format before mapping on top of it.

The inspector is deliberately shallow: it extracts code blocks with their window/control path and raw event code, raw XDD metadata, a **parity seed** (one row per block, table and unresolved export), and secret locations. It never guesses meanings. See [scripts/README](scripts/README.md).

## 4a. Extract the dossier (if one exists)

```sh
python3 scripts/dossier_extract.py legacy/docs/<project>_Documentation.pdf --out analysis-local/dossier
```

Per-element JSON (window title and type; each control's caption, tab order, input mask and size, button type, images; each query's SQL, parameters and conditions) plus each window's image as WINDEV draws it. Mapping notes and screen specs cite it as evidence (`dossier: WIN_X/BTN_Y`). It does not show runtime behavior (what Esc does on a dialog, dynamic states): that comes from the code, and when the code cannot settle it, from someone observing the running app — record it as `unresolved` until then.

## 4b. Check that the evidence is complete

```sh
python3 scripts/evidence_report.py analysis-local/inspect-1 --dossier analysis-local/dossier --out docs/evidence-report.md
```

Coverage per element with the list of gaps, the platform functions the code depends on (printing, INI files, external programs, command-line modes), and the few runtime questions for someone with the running app. Fix or record every gap before mapping.

## 4c. Export the data

Export every table to CSV through the HFSQL ODBC driver ([data export](scripts/windows/README.md)), from a copy of the data or a backup of the HFSQL server database.

## 5. Map the legacy application (before coding)

The first prompt to the implementer is the **mapping** ([templates/mapping-prompt.md](templates/mapping-prompt.md)):

- **sub-agents in parallel**, one per window/report/procedure set/table group, each using the [map-element skill](templates/agent/skills/map-element/SKILL.md), produce `docs/mapping/*.md` notes: entities, screens and navigation, events, business rules, naming conventions, traps, external dependencies, **hardcoded secrets to revoke**;
- **other agents review** each note against the sources and screenshots;
- consolidated outputs: `docs/legacy-inventory.md`, navigation map, `docs/screens/<WINDOW>.md`, and `docs/parity/parity.csv` imported from the seed plus manual rows (menus, shortcuts, rights, reports, jobs, integrations).

Gate: `python3 scripts/parity_check.py docs/parity/parity.csv --seed <inspect dir>/parity-seed.csv` passes. This is the analysis brief.

## 6. Frame with the planner

Paste [templates/PromptInit.md](templates/PromptInit.md) into the planning session. From the mapping notes, it asks **the questions that change the plan**, with a recommendation each; **you decide together**: topology, persistence, OS targets, permissions, reports, UI fidelity, integrations, build order, exclusions. Then it creates `AGENTS.md`, the first ADRs, the local instruction files and `ROADMAP.md` in the order **you chose**.

UI style is one of these choices: a **WINDEV-like replica** (same layout, fields, tab order and shortcuts from the screenshots — the safest for trained users and for parity) or a **modernized layout** (each difference is an accepted behavior change). For a replica, add the dedicated instruction from [templates/prompt-stage.md](templates/prompt-stage.md) to stage prompts.

## 7. Foundations

Scaffold the Tauri app in the accepted structure, `npm run verify` in CI on every target OS, bindings generation, schema v1 migrations, an opt-in dev seed (a Cargo feature such as `dev-seed` that loads the synthetic data into an empty database, so humans can try every slice), a browser-preview mode with the fake backend for agent UI inspection ([05](05-work-loop.md#checks-to-use)), and an import **dry run** on sanitized data with a reconciliation report ([08](08-data-migration.md)). Record golden scenarios for the first workflows in the legacy app ([10](10-parity-and-verification.md)).

## 8. First vertical slice

Build **one complete workflow** with synthetic data, then with imported data: UI + domain + command + persistence + tests + golden scenario. A good workshop example: customer → vehicle → repair order → saved order, then material and labor lines with totals and a printable report.

## 9. Run the loop

Each stage ([05](05-work-loop.md)): planner writes the prompt → you paste it into the implementer → it executes, verifies, commits, pushes, writes the handoff → you `git pull` → the planner reviews (4 categories) → decisions become ADRs → parity and roadmap updated.

## 10. Parity and rollout

Expand slice by slice until `parity_check.py --require-complete --seed …` passes. Then: replay all golden scenarios, reconcile a full import, test concurrent edits if applicable, check native integrations on the real target OSes, rehearse backup/restore and cutover ([08](08-data-migration.md#cutover)). Agree which intentional improvements replace legacy behavior before expanding scope.

---

> **The method stops there.** Module order, architecture details and conventions were fixed by **your** framing. This guide gave you the tools and the method to keep them.
>
> To replace the remaining PC SOFT services (telemetry, identity, distribution, reports, jobs): [07 — Platform replacements](07-platform-replacements.md).
