# Application instructions — <App>

Mission: migrate <legacy app> to the accepted TypeScript/Tauri architecture.
Read docs/runbooks/handoff.md and ROADMAP.md before implementing a slice.

## Repository map

- src/ui: screens; src/domain: pure business rules; src/application: use cases.
- src/infrastructure: native/API adapters; src-tauri: Rust commands and migrations.
- docs: evidence, architecture, parity matrix, decisions and runbooks.
- legacy/ and analysis-local/: private, ignored source evidence.

## Rules

Cite evidence for business rules and label assumptions. Follow accepted ADRs.
Validate runtime input at native/server boundaries; parameterize SQL.
Keep multi-table writes atomic; preserve numeric/date semantics.
Do not commit legacy data or credentials. Use synthetic fixtures in tests.
Do not claim checks passed unless executed; record unavailable native checks.
Keep generated contracts reproducible. Record deliberate behavior changes.

## Project commands

<Replace with actual package scripts and native checks after scaffolding.>

## Accepted choices

<OS targets, deployment topology, persistence, permissions, reporting and releases.>
