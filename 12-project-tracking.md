# 12 — Running the migration as a project (Jira, progress, reporting)

A full WINDEV application is weeks to months of work, many tickets and several people. This chapter connects the playbook's files to a tracker such as Jira without keeping the same information in two places.

## Who holds what

| Information | Source of truth | Why |
|---|---|---|
| What the legacy app does, and whether each behavior is migrated | `docs/parity/parity.csv` (repository) | Machine-checked by `parity_check.py`, versioned with the code that implements it |
| Decisions | `docs/decisions/` ADRs | Reviewed with the code; linked from tickets |
| Order and dependencies of slices | `ROADMAP.md` | Read by agents at each session |
| Who does what, when; discussion; approvals | Jira (or your tracker) | People plan and talk there |
| Latest delivered stage | `docs/runbooks/handoff.md` | Agent entry point; summarized into the ticket |

Rule: **Jira holds keys and conversations; the repository holds behavior and status.** Each parity row and roadmap slice carries its ticket key (`ticket` column, roadmap `Prompt`/`Slice` cell); tickets link back to rows by ID. Never mark a ticket Done by hand while its rows are not verified.

## Ticket structure

| Jira level | Content | Source |
|---|---|---|
| **Epic: Framing and mapping** | Inventory, exports, mapping per element, framing decisions | [06 §4–6](06-start-a-migration.md) |
| **Epic: Foundations** | Scaffold, CI `npm run verify`, guards, bindings, schema v1, import dry run | Roadmap foundations |
| **Epic per business module** | Orders, Invoicing, Stock… (group legacy windows by menu or workflow) | Mapping navigation map |
| **Epic: Reports and printing** | One story per report or report family | `docs/mapping/reports.md` |
| **Epic: Platform services** | Rights/Groupware, updater, telemetry, devices, jobs, integrations | [07](07-platform-replacements.md) |
| **Epic: Data migration and cutover** | Mapping, reconciliation, rehearsals, cutover | [08](08-data-migration.md) |
| **Story** | One roadmap slice = one complete workflow (UI + domain + command + tests), or one legacy element | `ROADMAP.md`, or `status.py --work-items` |
| **Task (human)** | Record golden scenario GS-n, export query X from WINDEV, approve screen visuals, answer decision | Handoff "Decisions needed", mapping "unresolved" |

### Generating stories from the parity matrix

After mapping, create one story per legacy element that still has open, untracked rows:

```sh
python3 scripts/status.py --parity docs/parity/parity.csv --work-items analysis-local/work-items.csv
```

The CSV has `Summary`, `Issue Type`, `Description` (the parity IDs with evidence and status), two `Labels` columns (`windev-migration` and the element kind) and `Parity IDs`. Import it with Jira's CSV importer, mapping columns in the import wizard (it may require Jira admin rights; `Parity IDs` can go to a custom field or the description). Then write the created keys back into the `ticket` column of the matching rows; re-running the export only proposes rows that still have no ticket.

Group small elements into one story per workflow when that matches the roadmap better — the roadmap decides the order; tickets follow it.

### A story is a stage prompt

Write the story description with the fields of [templates/prompt-stage.md](templates/prompt-stage.md): parity rows, evidence, expected behavior (normal, boundary, failure), intentional changes, deliverables, out of scope. The implementer receives the story as the core of its prompt; nothing is lost between the ticket and the agent.

**Definition of done (in the Jira workflow)**: every parity row of the story is `verified` or `excluded`, `npm run verify` and the story's golden scenarios pass in CI, the review is closed, the handoff is updated.

## Workflow and conventions

- Branch per story: `MIG-123-order-save`; commit messages start with the key: `MIG-123: Save repair order atomically`; one pull request per story with the handoff summary in the description.
- Suggested statuses: **To do** → **In progress** (agent working) → **In review** (PR open; reviewer runs the review skill) → **Waiting for human** (decision, export, visual approval) → **Done** (human, after CI is green).
- The agent may read the ticket and post its handoff summary as a comment, through an Atlassian connector or CLI if your organization provides one; **the human moves tickets to Done**.
- Human tasks are first-class tickets: golden scenarios, exports and approvals are on the critical path, and they are where migrations usually stall.

## Checking progress

```sh
python3 scripts/status.py --parity docs/parity/parity.csv --roadmap ROADMAP.md          # Markdown report
python3 scripts/status.py --parity docs/parity/parity.csv --roadmap ROADMAP.md --json   # for dashboards
python3 scripts/parity_check.py docs/parity/parity.csv --seed <inspect dir>/parity-seed.csv   # validity
```

The report shows overall parity %, rows per status, the count of rows whose legacy behavior is still `unresolved`, slices in progress or blocked, and a table per legacy element (least complete first) with its tickets. Post it to the weekly status page, the epic, or the PR.

**Trend over time** (burn-up of verified rows), from Git history alone:

```sh
for sha in $(git rev-list --first-parent --since="12 weeks ago" main -- docs/parity/parity.csv); do
  git show "$sha:docs/parity/parity.csv" > /tmp/parity.csv
  printf '%s %s ' "$(git show -s --format=%cs "$sha")" "$sha"
  python3 scripts/status.py --parity /tmp/parity.csv --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['complete_percent'], d['statuses']['verified'])"
done
```

Read the numbers carefully:

- **Unmapped rows** are analysis debt: keep them near zero before estimating.
- **Unresolved legacy behavior** is risk: each one needs an export, a golden scenario or an expert answer.
- **Specified vs verified** is the real delivery measure; `implemented` without `verified` is not progress you can ship.
- Percent complete is per row, not per effort: a report row can cost more than ten field rows. Weight by element kind if needed.

## Estimating

1. After mapping, count open rows per element and flag the expensive kinds: reports, rights/Groupware, integrations, devices, replication.
2. Run the first two or three slices end to end and measure verified rows per week, separately for UI-heavy and rule-heavy elements.
3. Project the remainder from that velocity plus the human tasks (golden scenarios, exports, approvals), which often dominate the calendar.
4. Re-estimate at each epic boundary from the trend, not from the plan.
