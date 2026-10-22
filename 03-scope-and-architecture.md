# 03 — Scope and architecture

## Decisions to make from evidence

Record supported OSes, single-machine versus shared use, offline requirements, roles, concurrency, external integrations, reports, hardware, data volume, rollout and excluded features. A folder of HFSQL files does not establish that the deployment is single-user.

## Recommended local desktop structure

```text
src/ui/                 React screens and components
src/domain/             pure TypeScript entities, value objects and rules
src/application/        use cases and repository interfaces
src/infrastructure/     typed Tauri IPC adapters
src-tauri/src/          native commands, filesystem and database adapters
src-tauri/migrations/   authoritative ordered SQL migrations
```

UI calls application services; domain rules do not import React or Tauri. Persistence is accessed through repository interfaces, allowing in-memory domain tests. Native commands accept structured values, validate them, parameterize SQL, and own transactions. TypeScript types do not validate IPC input at runtime; validate both boundaries as appropriate. Regenerate or test shared DTO contracts to prevent Rust/TypeScript drift.

Do not expose an arbitrary SQL or shell command from the renderer. Define narrow business commands. A transaction spans the entire save operation, not a sequence of independent UI invokes. For example: validate a stock consumption command, re-check current stock and record consumption atomically, then return committed results. Renderer checks improve feedback; authoritative integrity belongs at the persistence boundary.

For shared business data, use a server API that owns authorization and transactions, with PostgreSQL behind it. Do not put shared database credentials in desktop clients or place a SQLite file on a network share. Offline synchronization is a separate feature requiring conflict rules.

[Capabilities](https://v2.tauri.app/security/capabilities/) constrain native access; grant only necessary commands/plugins, restrict filesystem paths, and use a deliberate content security policy. A hidden button is not authorization. Keep platform-specific printing and device integrations behind adapters.
