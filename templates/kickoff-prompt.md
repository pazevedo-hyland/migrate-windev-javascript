# Kickoff prompt (autonomous migration)

For one coding agent (Claude Code, Codex…) that runs the whole migration with as little human help as possible. Open the agent in the **empty application folder** whose `legacy/` is filled as in [00 §E](../00-prerequisites.md#e-collect-the-legacy-material), fill in the first three lines, paste the block. To check the analysis before any code is written, start with "Stop after: framing", review the roadmap and mapping, then paste the prompt again with "Stop after: everything". The same prompt resumes a stopped session: the agent picks up from `ROADMAP.md` and the handoff.

```text
Playbook: <path to the migrate-windev-javascript checkout> (read-only for you).
Data in legacy/data/: <demo or test data — may be used anywhere | personal data — counts and patterns only outside legacy/>
Stop after: <framing (no application code) | foundation | everything>

You are migrating the WINDEV application in legacy/ to TypeScript + Tauri with full feature parity, following the
playbook. Work autonomously: never stop to ask. Where a human is needed, use the playbook's proposals and defaults
(AGENTS.md "No guessing"), record the choice (ADR "Decided by: default", or `assumed` parity rows) and continue;
list open decisions in docs/runbooks/handoff.md under "Decisions needed".

If ROADMAP.md exists, you are resuming: read AGENTS.md, ROADMAP.md, docs/runbooks/handoff.md and `git log`, then
continue with the first slice not Done. Otherwise start at step 1.

1. Read the playbook's README, chapters 06, 05 and 10, and templates/PromptInit.md (method and decision rules).
2. Set up this folder as the application repository as chapter 06 §2 says (templates/, scripts/, skills/,
   AGENTS.md from the template, chapter 09 as docs/wlanguage-traps.md, anchored .gitignore). Do not install the guard
   (humans own it); if scripts/guard.py is installed, run it with --staged before each commit.
3. Data copy: if legacy/data/ holds no data.sqlite but legacy/ holds HFSQL files (.fic/.ndx/.mmo), make one on
   Windows: copy those files to a scratch folder outside legacy/, create an ODBC data source on the copy with the
   HFSQL driver (PowerShell Add-OdbcDsn, or the ODBC administrator; 32- or 64-bit as scripts/windows/README.md
   explains), and run scripts/windows/export_odbc.py --out on a new folder, then move its data.sqlite and
   manifest.json to legacy/data/. A count mismatch stops the export: report it. For an HFSQL server, ask for a
   backup copy instead. Without Windows or the driver, record it under "Decisions needed" and go on.
   Evidence (06 §4): scripts/prepare_evidence.py, then scripts/data_profile.py on legacy/data/data.sqlite. Read
   docs/evidence-report.md, docs/evidence/encoded-actions.md (Proposed answers), docs/navigation.md,
   docs/schema/schema-draft.md and docs/data/profile.md. Port faithfully first; make it idiomatic in the
   roadmap's cleanup slices.
4. Stage 0, mapping of the whole application: templates/mapping-prompt.md (every window, report, query set and
   table group; sub-agents in parallel if you have them, else sequentially; a cross-review by a separate agent or
   session, else a second pass of your own, said so in the handoff).
5. Framing: PromptInit part A as ADRs decided by evidence or default; part B questions answered by their
   recommended defaults ("Decided by: default"), listed in the handoff for the owner; part C stays in the answer
   sheet. Then ROADMAP.md from templates/ROADMAP.template.md: foundation rows first (scaffold and npm run verify,
   schema v1 and the data import with dry run, quarantine and reconciliation, skin kit), then slices from the
   leaves of docs/navigation.md towards the workflows that use them.
   With "Stop after: framing", stop here: commit, and leave the handoff with what was found, the decisions taken by
   default and what the owner should check before the foundation starts.
6. Slices, in ROADMAP order, one at a time, each as templates/prompt-stage.md says: write the stage brief into
   docs/runbooks/stage-<n>.md, build, verify (npm run verify, UI check and click-through flows, parity check), update
   docs/parity/parity.csv, ROADMAP.md and the handoff, regenerate the progress page
   (scripts/progress_dashboard.py), commit. Each slice gets an independent review (two when it is risky) and one fixer, as
   the stage prompt says. Then the next slice.
   With "Stop after: foundation", stop once the foundation rows are Done.
7. Stop only when every parity row is verified or excluded, or when every remaining slice waits on a decision
   no default covers; the handoff then lists exactly what is needed from whom.

Rules: legacy/ is read-only. Never push unless told to; commit in small steps. Never delete folders recursively.
On Windows run Python as `py` where the playbook writes `python3`.
Progress lives where the playbook keeps it: ROADMAP.md, docs/parity/parity.csv, the handoff and the progress
page. Add a "Playbook issues" section to the handoff for any playbook instruction, skill, template or script that
was wrong, unclear or failed (file, what happened, suggested fix).
```
