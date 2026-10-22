# Mapping prompt (stage 0, for the implementer)

Run once after `scripts/inspect_windev.py`, and again for any source added later. The goal is a complete, reviewed description of the legacy application **before** any code is written.

```text
Read AGENTS.md (or this prompt if it does not exist yet), docs/wlanguage-traps.md and analysis-local/inventory.json.

Goal: map the whole legacy application into docs/mapping/ and docs/parity/parity.csv. Do not write application code.

1. Event-code legend first: create docs/mapping/event-codes.md. For the most frequent raw event codes in the inspector output, infer the meaning from evidence across many windows (control type, code content), label each inferred, and keep it shared so every mapper uses the same meanings.
2. Plan the split: one unit per window, report, query, procedure set, class and table group (≈5–10 tables). List units in docs/mapping/README.md with their parity-seed row counts.
3. Fan out: one unit per sub-agent in parallel (or per parallel session, or sequentially if your agent has no sub-agents). Each follows skills/map-element/SKILL.md and writes docs/mapping/<unit>.md, docs/screens/<unit>.md and docs/parity/<unit>.csv, validated with parity_check.py --element <unit>. Sub-agents only read legacy/ and analysis-local/.
4. Cross-review: use different sub-agents or sessions (ideally a different model) to review each note against the sources and screenshots. They report missing events, misread rules, unresolved references and wrong confidence labels. Apply the corrections.
5. Consolidate:
   - docs/legacy-inventory.md: sources, coverage, binary or missing exports to request (queries, encoded properties, reports), nested projects, external dependencies, hardcoded secrets to revoke (location only, never the value).
   - docs/mapping/entities.md, screens.md (navigation map: menus, which window opens which, modal or not, parameters, returned values), workflows.md, permissions.md, reports.md, jobs-and-integrations.md.
   - docs/parity/parity.csv: merge the per-unit CSVs, then import every remaining parity-seed.csv row unchanged (keep IDs), and add rows for menus, shortcuts, rights, reports, jobs and integrations not covered by code blocks.
6. Run python3 scripts/parity_check.py docs/parity/parity.csv --seed analysis-local/parity-seed.csv and fix every error.
7. Write the handoff: coverage numbers, unresolved items, exports needed from WINDEV, questions for the human.

Never execute legacy code. Numeric event and type codes stay raw in the notes; their meanings live only in docs/mapping/event-codes.md, labelled inferred until documentation, a screenshot or the running app confirms them.
```
