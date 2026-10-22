# 01 — Principles and roles

Keep the upstream method: inventory first, record decisions, implement bounded steps, verify behavior, and leave a handoff. One assistant can do analysis and implementation in separate passes. A reviewer should examine evidence and changes; no particular provider or two-agent arrangement is required.

The human defines scope and accepts deliberate behavior changes. The implementation assistant reads actual sources and APIs, implements the agreed slice, and runs available checks. Review findings identify file/line, impact, and a concrete correction.

Every inferred rule must be labeled as verified, inferred, or unresolved. Cite source paths and lines. Do not mistake UI labels for requirements, a schema for actual data, or a successful build for business parity. Preserve the original behavior unless a change is explicitly recorded.

Use small commits, decision records for consequential choices, one authoritative migration history, deterministic tests, and an accurate rolling handoff. Keep private legacy artifacts and credentials outside published examples. Routine reversible work can proceed within agreed scope; data deletion and cutover need an explicit plan.
