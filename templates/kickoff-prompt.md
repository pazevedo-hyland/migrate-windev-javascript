# Kickoff prompt (autonomous migration)

For one coding agent (Claude Code, Codex…) that runs the whole migration with as little human help as possible. Open the agent in the **empty application folder** whose `legacy/` is filled as in [00 §E](../00-prerequisites.md#e-collect-the-legacy-material), fill in the first two lines, paste the block. The same prompt resumes a stopped session: the agent picks up from `ROADMAP.md` and the handoff.

```text
Playbook: <path to the migrate-windev-javascript checkout> (read-only for you).
Data in legacy/data/: <demo or test data — may be used anywhere | personal data — counts and patterns only outside legacy/>

You are migrating the WINDEV application in legacy/ to TypeScript + Tauri with full feature parity, following the
playbook. Work autonomously: never stop to ask. Where a human is needed, use the playbook's proposals and defaults
(AGENTS.md "No guessing"), record the choice (ADR "Decided by: default", or `assumed` parity rows) and continue;
list open decisions in docs/runbooks/handoff.md under "Decisions needed".

If ROADMAP.md exists, you are resuming: read AGENTS.md, ROADMAP.md, docs/runbooks/handoff.md and `git log`, then
continue with the first slice not Done. Otherwise start at step 1.

1. Read the playbook's README, chapters 06, 05 and 10, and templates/PromptInit.md (method and decision rules).
2. Set up this folder as the application repository as chapter 06 §2 says (templates/, scripts/, skills/,
   AGENTS.md from the template, chapter 09 as docs/wlanguage-traps.md, anchored .gitignore). The guard is optional:
   skip it unless the playbook's agent adapter for you is ready to install.
3. Evidence (06 §4): scripts/prepare_evidence.py, then scripts/data_profile.py on the data copy. Read
   docs/evidence-report.md, docs/evidence/encoded-actions.md (Proposed answers), docs/navigation.md,
   docs/schema/schema-draft.md and docs/data/profile.md.
4. Stage 0, mapping of the whole application: templates/mapping-prompt.md (every window, report, query set and
   table group; sub-agents in parallel if you have them, else sequentially; a cross-review by a separate agent or
   session, else a second pass of your own, said so in the handoff).
5. Framing: PromptInit part A as ADRs decided by evidence or default; part B questions answered by their
   recommended defaults ("Decided by: default"), listed in the handoff for the owner; part C stays in the answer
   sheet. Then ROADMAP.md from templates/ROADMAP.template.md: foundation rows first (scaffold and npm run verify,
   schema v1 and the data import with dry run, quarantine and reconciliation, skin kit), then slices from the
   leaves of docs/navigation.md towards the workflows that use them.
6. Slices, in ROADMAP order, one at a time, each as templates/prompt-stage.md says: write the stage brief into
   docs/runbooks/stage-<n>.md, build, verify (npm run verify, UI check and click-through flows, parity check), update
   docs/parity/parity.csv, ROADMAP.md and the handoff, regenerate the progress page
   (scripts/progress_dashboard.py), commit. Then the next slice. After every few slices, review your own last
   slices with skills/review (a fresh session if you can).
7. Stop only when every parity row is verified or excluded, or when every remaining slice waits on a decision
   no default covers; the handoff then lists exactly what is needed from whom.

Rules: legacy/ is read-only. Never push unless told to; commit in small steps. Never delete folders recursively.
On Windows run Python as `py` where the playbook writes `python3`.

Keep docs/runbooks/trial-report.md up to date as you go: what is done, check results, parity rows by status,
visual scores, import reconciliation, every place you would have asked a human, and every playbook instruction,
skill, template or script that was wrong, unclear, missing or failed (file, what happened, suggested fix).
```
