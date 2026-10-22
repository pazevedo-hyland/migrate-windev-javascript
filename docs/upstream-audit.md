# Upstream adaptation audit

Source: https://github.com/migration-windev/windev-vers-dotnet

Inspected base commit: `2f3e04c808070bb5631299a10f287d47dffd2874`. All nine chapters, README, contribution guide, changelog, six templates and MIT license were inspected. The base repository contains documentation/templates, with no converter implementation or application scaffold.

| Upstream material | Adaptation |
|---|---|
| Prerequisites and infrastructure | Node/Rust/platform tooling, optional legacy Windows environment, GitHub and native CI instead of mandatory Windows development VMs/Gitea |
| Principles and roles | Keep evidence, ADRs, handoffs and small reviewed steps; permit a single assistant |
| Scope | Propose a concrete TypeScript/Tauri default and require deployment-based persistence decisions |
| Claude project memory | Assistant-neutral AGENTS template and durable docs; optional CLAUDE pointer |
| Work loop and startup | Keep bounded stages; add behavior parity and native smoke tests |
| Platform services | Replace .NET-specific products with explicit Tauri/TypeScript integration strategies and documented gaps |
| Data chapter | Replace EF Core/Dapper guidance with native repositories or API boundary; emphasize exact numeric semantics, import reconciliation and shared-data topology |
| Templates | English initialization, stage, ADR, handoff and review templates; add parity matrix |
| New toolkit | Read text event blocks and raw XDD metadata, explicitly leave binary/encoded formats unresolved |

The original files are available in Git history. The rewritten documentation is an adaptation rather than a word-for-word translation. No claim is made that WINDEV windows, reports, authentication or database semantics translate automatically. The source license is retained unchanged in LICENSE.

## Remaining deliverables for a real application migration

An actual Tauri scaffold, dependency locks, full legacy analysis, query exports, schema mapping, data import, implementation of workflows, report/hardware adapters, native CI, installers and acceptance testing belong to the individual application project. This playbook is the framework for that work.
