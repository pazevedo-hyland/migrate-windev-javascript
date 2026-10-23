# Mapping prompt (stage 0, for the implementer)

Run once the legacy material is collected, and again for any source added later (step 0 regenerates the evidence; seed IDs stay stable). The goal is a complete, reviewed description of the legacy application **before** any code is written.

```text
Read AGENTS.md (or this prompt if it does not exist yet) and docs/wlanguage-traps.md.

Goal: map the whole legacy application into docs/mapping/ and docs/parity/parity.csv. Do not write application code.

0. Evidence first: run `python3 scripts/prepare_evidence.py` (inspector, dossier extract, event legend, evidence report, navigation map, schema draft, layouts; the paths it used are in analysis-local/latest.json — use those everywhere below). Resolve or record every gap in docs/evidence-report.md; add the platform-usage findings (INI files, external programs, command-line modes, printing) as parity rows; hand the runtime questions and the encoded-action groups to the human (answers go to docs/evidence/encoded-actions.md).
1. Event codes: docs/mapping/event-codes.md is generated from WINDEV's compiled event labels and counts as verified. For codes it does not cover, infer from evidence across many windows (control type, code content) into docs/mapping/event-codes-inferred.md, each labelled inferred, so every mapper uses the same meanings and regenerating the verified legend never erases them.
2. Plan the split: one unit per window, report, query, procedure set, class and table group (≈5–10 tables). List units in docs/mapping/README.md with their parity-seed row counts.
3. Fan out: one unit per sub-agent in parallel (or per parallel session, or sequentially if your agent has no sub-agents). Each follows skills/map-element/SKILL.md and writes docs/mapping/<unit>.md, docs/screens/<unit>.md and docs/parity/<unit>.csv, validated with parity_check.py --element <unit>. Sub-agents only read legacy/ and analysis-local/.
4. Cross-review: for each unit, a different sub-agent or session (ideally a different model) follows skills/review-mapping/SKILL.md and reports findings in its six categories. Apply the corrections, then re-run parity_check.py for the unit.
5. Consolidate:
   - docs/legacy-inventory.md: sources, coverage, binary or missing exports to request (queries, encoded properties, reports), nested projects, external dependencies, hardcoded secrets to revoke (location only, never the value).
   - docs/mapping/entities.md, screens.md (navigation map: start from the generated docs/navigation.md — proven call sites — and add what it cannot see: encoded actions once answered, dynamic targets, modal or not, parameters, returned values), workflows.md, permissions.md, reports.md, jobs-and-integrations.md.
   - docs/parity/parity.csv: merge the per-unit CSVs, then import every remaining parity-seed.csv row unchanged (keep IDs), and add rows for menus, shortcuts, rights, reports, jobs and integrations not covered by code blocks.
6. Run python3 scripts/parity_check.py docs/parity/parity.csv --seed analysis-local/parity-seed.csv and fix every error.
7. Write the handoff: coverage numbers, unresolved items, exports needed from WINDEV, questions for the human.

Never execute legacy code. Numeric event and type codes stay raw in the notes; their meanings live only in docs/mapping/event-codes.md (verified) and event-codes-inferred.md (inferred until documentation, a screenshot or the running app confirms them).
```
