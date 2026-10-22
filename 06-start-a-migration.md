# 06 — Start a migration

## Collect and inspect

Keep original sources read-only outside this repository, or under ignored `legacy/`. Run the inspection tool into ignored `analysis-local/`. Retain relative paths, line numbers and source hashes. Review the inventory for binary files, missing global procedures, nested subprojects and unresolved references.

The tool is deliberately shallow. Read extracted event code and its callers, follow referenced queries and procedures, inspect schema relationships and compare screenshots. Export unresolved binary query SQL and parameters from WINDEV; do not reconstruct it from its filename. Encoded designer metadata still needs screenshots or a designer export.

## Produce a specification

Create entity and screen maps, workflow descriptions, permission rules, stock/time/money semantics, reporting requirements and external dependency inventory. Every rule gets a source reference, confidence, target behavior and acceptance example. Distinguish known facts from hypotheses and questions.

## Choose a first slice

Confirm deployment topology, target stack and data migration plan in ADRs. Scaffold the actual app in its own repository. Build one complete workflow using synthetic data before importing business data. A useful workshop slice is customer → vehicle → repair order → saved order, then material and labor additions with totals and a printable report.

## Establish parity and rollout

Run known old-system examples against the replacement. Reconcile imports, test concurrent edits if applicable, check native integrations on the real target OS, and rehearse backup/restore and cutover. Agree which intentional improvements replace legacy behavior before expanding scope.

Use the initialization and stage templates to keep evidence and acceptance criteria attached to each implementation step.
