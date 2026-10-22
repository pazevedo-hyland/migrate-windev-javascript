# Stage review

Read changed files, accepted decisions and the legacy behavior referenced by the stage. Report actionable findings with file/line and impact.

1. Blocking behavior: build failures, lost data, wrong totals, violated permissions, broken transactions or missing acceptance criteria.
2. Conventions and architecture: domain/native boundaries, schema ownership, DTO consistency and error handling.
3. Business and usability: unproven assumptions, keyboard/focus behavior, report layout and deliberate differences.

Check runtime input validation, SQL parameters, large IDs, money/date semantics, concurrent saves, migration/recovery and evidence of actual checks. Do not equate browser mocks with a packaged native test. Keep approved choices unless new evidence requires revisiting them; explain that evidence.
