# Mapping prompt (stage 0, for the implementer)

Run once after `scripts/inspect_windev.py`, and again for any source added later. The goal is a complete, reviewed description of the legacy application **before** any code is written.

```text
Read AGENTS.md (or this prompt if it does not exist yet), docs/wlanguage-traps.md and analysis-local/inventory.json.

Goal: map the whole legacy application into docs/mapping/ and docs/parity/parity.csv. Do not write application code.

1. Plan the split: one unit per window, report, query, procedure set, class and table group (≈5–10 tables). List units in docs/mapping/README.md with their parity-seed row counts.
2. Fan out: launch sub-agents in parallel, one unit each (batch if needed). Each sub-agent uses the /map-element skill (or the instructions in templates/claude/skills/map-element/SKILL.md) and writes docs/mapping/<unit>.md plus proposed parity rows. Sub-agents only read legacy/ and analysis-local/.
3. Cross-review: launch different sub-agents to review each note against the sources and screenshots. They report missing events, misread rules, unresolved references and wrong confidence labels. Apply the corrections.
4. Consolidate:
   - docs/legacy-inventory.md: sources, coverage, binary or missing exports to request (queries, encoded properties, reports), nested projects, external dependencies, hardcoded secrets to revoke (location only, never the value).
   - docs/mapping/entities.md, screens.md (navigation map: menus, which window opens which, modal or not, parameters, returned values), workflows.md, permissions.md, reports.md, jobs-and-integrations.md.
   - docs/parity/parity.csv: import every parity-seed.csv row (keep IDs), fill legacy_behavior and confidence, and add rows for menus, shortcuts, rights, reports, jobs and integrations not covered by code blocks.
   - docs/screens/<WINDOW>.md from templates/window-spec.md for each window.
5. Run python3 scripts/parity_check.py docs/parity/parity.csv --seed analysis-local/parity-seed.csv and fix every error.
6. Write the handoff: coverage numbers, unresolved items, exports needed from WINDEV, questions for the human.

Never execute legacy code. Never guess the meaning of a numeric event or type code: write it raw and mark it unresolved until a screenshot, export or documentation confirms it.
```
