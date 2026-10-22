# 03 — Scope and architecture

## What this guide decides, and what it leaves to you

The upstream guide deliberately left architecture open. Coding agents perform better with **one clear default**, so this guide proposes a concrete architecture. Treat it as the recommendation the planner brings to framing: you accept it or replace parts of it, and either way every choice is recorded as an ADR and a rule in `AGENTS.md`.

**This guide fixes:** the working method (chapters 01, 04, 05), the evidence and parity discipline (chapter 10), and the hard boundaries below (validation, transactions, no arbitrary SQL from the UI, no secrets).

**You decide, from evidence, at framing:** deployment topology, persistence, supported OSes, permissions model, report engine, UI fidelity level, build order, excluded features. Two projects can legitimately end with different answers.

**The one code requirement in every case:** verify reality before coding. Inspect the real schema and the real library APIs; never invent a column, table, control or API member.

## Decisions to make from evidence

Record each one as an ADR before the first slice:

| Decision | Evidence to collect | Typical trap |
|---|---|---|
| Topology: one machine or shared data | How the HFSQL files are deployed today; number of concurrent users | A folder of `.fic` files can be shared over the network: it does not prove single-user use |
| Persistence | Volume, concurrency, encryption, HFSQL features used ([08](08-data-migration.md)) | SQLite on a network share; database credentials in desktop clients |
| OS targets | Where users run it today, printers and devices | WebView differences: WebView2 (Windows), WKWebView (macOS), WebKitGTK (Linux) |
| Permissions | Groupware usage, rights administered by users, login | Hidden button treated as authorization |
| Reports | Count, fixed vs user-designed, labels, silent printing | Browser print preview treated as proof of packaged printing |
| UI fidelity | Screenshots, keyboard habits, dense grids | Redesign that slows trained users; lost shortcuts |
| Concurrency | `HLockRecord`/`HLockFile` use, simultaneous edits | Last write silently wins |
| Integrations | Third-party systems and access mode, files exchanged, web services | Integration discovered at cutover |
| Excluded features | Usage data, user interviews | Silent omissions: every exclusion is an ADR and an `excluded` parity row |

## Recommended structure

```text
src/ui/                React screens and components (data-testid = legacy control name)
src/domain/            pure TypeScript entities, value objects and business rules
src/application/       use cases, command builders, repository/command interfaces
src/infrastructure/    typed Tauri IPC adapters (or HTTP adapters for the shared topology)
src/bindings/          generated TypeScript types for Rust commands (do not edit)
src-tauri/src/commands/  one Rust command per business operation
src-tauri/src/db/        connection setup, transactions, repositories
src-tauri/migrations/    authoritative ordered SQL migrations
docs/                  evidence, mapping, parity matrix, screens, golden scenarios, ADRs, runbooks
```

If a server is accepted (shared topology), move `src/domain/` into a workspace package (e.g. `packages/domain/`) shared by the desktop app and a TypeScript API (`apps/server/`), so the same rules run where the transaction runs.

## Where business rules live: one home per rule

The biggest parity risk in a TypeScript + Rust app is the **same rule written twice** and drifting. Apply this rule and record it in `docs/architecture.md`:

- **Business calculations and decisions** (totals, discounts, VAT, status transitions, validation messages) live **once**, in `src/domain/`, as pure tested functions.
- **Invariants that need the current database state** (stock not negative, unique codes, optimistic version) are enforced **in the same transaction that writes**: as SQL constraints or conditional statements in the Rust command (e.g. `UPDATE stock SET qty = qty - ?1 WHERE id = ?2 AND qty >= ?1` and check the affected row count). The domain may also pre-check for feedback; the database check is the authority.
- The parity row's `implemented_in` column lists every place a rule is implemented, so the review can see duplicates.

Rust stays thin: validation of input shape, transactions, persistence, OS integration.

## Command pattern: one save = one invoke = one transaction

1. The UI collects input and calls a use case.
2. The use case applies domain rules and builds **one command DTO** describing the whole business operation (e.g. `SaveRepairOrder` with header, lines and computed totals).
3. One Tauri command validates the DTO, opens a transaction, re-checks invariants, writes everything, commits and returns the committed state.
4. Errors come back as typed results (`{ kind: 'StockInsufficient', item, available }`), mapped to the legacy message text.

Never compose a business transaction from several independent `invoke` calls: a failure halfway leaves partial data. A transaction spread over several JavaScript calls through a pooled SQL plugin connection is not a reliable boundary either.

## IPC contracts and validation

- Generate TypeScript types from Rust command signatures with [tauri-specta](https://github.com/specta-rs/tauri-specta) or [ts-rs](https://github.com/Aleph-Alpha/ts-rs); CI regenerates and fails on diff.
- TypeScript types do not validate anything at runtime. Validate at both boundaries: zod (or similar) for forms and API input in TypeScript; `serde` deserialization with explicit checks (ranges, lengths, enums) in Rust.
- IDs that may exceed 2^53 cross IPC as **strings**; money as integer minor units or decimal strings (see [09](09-wlanguage-traps.md)).

## Security boundaries

- Do not expose arbitrary SQL, shell or filesystem access to the webview. Define narrow business commands.
- [Capabilities](https://v2.tauri.app/security/capabilities/) restrict which commands and plugins each window can use: grant only what is needed, restrict filesystem scopes, set a deliberate content security policy.
- A hidden or disabled button is not authorization: commands check permissions (see Groupware in [07](07-platform-replacements.md)).
- For shared business data, a **server API** owns authorization and transactions with PostgreSQL behind it. Never put shared database credentials in desktop clients, and never place SQLite on a network share. Offline synchronization is a separate feature with explicit conflict rules.

## UI architecture choices (decide once, by ADR)

- **Grid library** for dense, editable, keyboard-driven tables (e.g. AG Grid, TanStack Table + virtualization) and **form library** (e.g. React Hook Form + zod). Agents otherwise improvise a different solution per screen.
- **Windows**: WINDEV apps often keep several non-modal windows open at once. Choose between Tauri multi-window (separate webviews, state shared via the Rust side or events) and in-app tabs/MDI. Map modal windows to awaited dialogs.
- **Global state**: WLanguage project globals and HFSQL "current record" contexts become an explicit store (one per window or per workflow), never implicit module-level variables.
- **Keyboard conventions**: Enter-as-Tab, default/cancel buttons, function keys and shortcuts per `docs/screens/`.
- **Languages**: if the WINDEV project is multilingual, extract captions and messages per language into i18n resources.
- Keep platform-specific printing and devices behind adapters (`src/infrastructure/printing.ts` → Rust command per OS).
