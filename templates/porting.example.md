# Porting patterns (WLanguage → this project) — worked example

An example of `docs/porting.md` (mapping prompt, step 1b), taken from a finished migration: WINDEV 28 / HFSQL to React + a TypeScript procedure server on PostgreSQL, about 110 windows and 30 reports. Copy the shape, not the content: every "where" is a file of **that** code base and yours will differ (a Rust command instead of a server procedure, another kit component). Lines your application does not use are deleted; constructs it uses and this list lacks are added before the first slice that needs them.

What made this file work there: one line per construct, the place in the code that shows it, and a reference slice named at the top. Implementers stopped inventing a second way of doing the same thing, and reviewers had something to check against.

---

Every slice follows these. Missing pattern? Add it here first (AGENTS.md rule 12). Reference implementation: slice 1 (`src/ui/shell/login.ts`, `src/ui/common/crud.tsx`, `src/backend/crud.ts`, `src/backend/procedures/shell.ts`, `ui-check/app/slice1.flows.spec.ts`).

## Where code goes

| Legacy | Target |
|---|---|
| Window `WIN_X` (layout) | generated `src/generated/layouts/` — never edited; adapter `src/ui/<family>/<x>.tsx` registered in `src/ui/<family>/index.ts` |
| Code that reads or writes data files, SQL queries, class or global procedure with data access | server procedure in `src/backend/procedures/<family>.ts`, pure rules in `src/backend/domain/<topic>.ts` |
| Pure calculation (durations, dates, totals) | `src/shared/*.ts` or `src/backend/domain/*.ts`, unit-tested with the mapping's worked examples |
| Report `RPT_X` | `src/ui/reports/<family>/RPT_X.tsx` with `Page/Band/Field`, data from a `report.*` procedure |
| Demo data | `src/backend/seed/<family>.ts`, registered in one list |

## Constructs

**Data**

- **HReadSeek / HReadSeekFirst / HFound** → `seek(tx, table, {item: value})`: exact, returns the row or null. **HReadFirst / HReadNext loop** → `list(tx, table, {where, orderBy})`. **HFilter** → a `where`; a filter the legacy leaves active is reproduced only where a mapping row says its effect is visible (cite the row).
- **HAdd** → `insert` (defaults fill unspecified items). **HModify** → `update(tx, table, row.rowid_, values)`. **HDelete** → `remove` / `removeWhere`.
- **HExecuteSQLQuery with concatenated SQL** → the same SQL with `$n` parameters. Quote the legacy SQL in a comment above it.
- **"Next number" procedures (MAX + 1)** → `nextNumber(tx, table, item, where)` inside the save transaction.
- **HOnError and duplicates** → unique index violation → `duplicateError(item, value)`. **Modification conflict window** → last writer wins, as the legacy's own handler did.
- **One user action = one procedure = one transaction**, even where the legacy wrote several files without one.
- **Text keys**: the analysis says how each compares (case, accents, spaces — [schema draft](../06-start-a-migration.md)); record the target's choice in an ADR before the first search or unique index is written.
- **FileToScreen / ScreenToFile** → adapter state ↔ procedure DTO; the legacy item names are the DTO keys.

**Windows and dialogs**

- **Info / Error / YesNo** → client: `useLegacyDialogs()` (`info`, `error`, `yesNo(text, destructive)`); server refusals: `throw new UserError(text)`. Exact legacy texts from the mapping; the default button of a delete confirmation is the safe one until the legacy's is known.
- **Open(WIN_X, p…)** → `await window.open("WIN_X", p…)`, which resolves with `..ReturnedValue`. **OpenChild** → opened non-blocking, closed with its caller. **OpenSister** → opened non-blocking, then the caller closes if the legacy closes it. **Close() / ..ReturnedValue = v** → `window.close(v)`.
- **Closing event** → `ScreenModel.onClosing: async () => boolean` (false keeps the window). It runs for the frame's close box, and for Esc when the window has no Abort-type button; otherwise Esc clicks that button. Share one function between the two paths.
- **..Title = text** → `ScreenModel.title`. **..WindowState / WinSize** → `window.minimize()` / `window.maximize()`.
- **ExecuteProcess(BTN_X, trtClick)** → call the handler function the button uses.
- **TableDisplay(taCurrentRecord / taCurrentFirst)** → reload the list and reselect the same key / the first row.
- **Timer / TimerSys** → `useEffect` + `setInterval` with the legacy interval (hundredths of a second × 10 ms), stopped on unmount.
- **Rights check on open** → `const allowed = usePermissionGate(window, n)`; data is loaded only when allowed. Server writes call `requirePermission(ctx, n)` where the legacy checks inside the action.
- **Globals (logged user, workstation, mode)** → `getSession()` on the client, `ctx.session` on the server. Project constants → one file, values from the constants mapping.

**Values**

- **Dates, times, durations** → the shared helpers named in the values ADR; `Today()` / `Now()` → `ctx.now()` on the server, so tests fix the clock.
- **Decimals** → strings and a decimal helper, never floating-point arithmetic.
- **Date edit control** → the kit's date edit with a draft in state: the text as typed, converted on save to an ISO date, blank, or refused when invalid.
- **NoSpace, Contains, Left, Right, Middle, Val, NumToString** → one helper file, each function tested against [chapter 09](../09-wlanguage-traps.md).

**Outside the window**

- **iPreview + iPrintReport** → `await reports.preview(title, <RPT_X data={…}/>)`; `iPrintReport` alone → `reports.print`. **iListPrinter** → one infrastructure function with a native implementation and a preview stand-in.
- **fCopyFile / fDelete / fMakeDir / ShellExecute** → one infrastructure file behind the files ADR, simulated in the browser preview.

**Evidence gaps**

- **Layout gaps** (missing geometry, unknown control kind) → fix the generator's input and regenerate; never patch geometry in an adapter when the evidence has it. Fields the evidence tools learn later come in with [`refresh_layouts.py`](../scripts/README.md).
- **Controls the kit has no kind for** (image, scheduler, internal window, progress bar) → drawn by the adapter at the control's box from the layout, and listed as handled.
- **Designer flags the evidence lacks** → set in the adapter with a comment citing the open item.
- **`// UNRESOLVED U-nn: <choice>`** wherever a default was chosen with no answer and no proposal.

## Tests a slice must add

1. Unit tests of rules and procedures with the mapping's worked examples, against a real database (embedded), not a mock.
2. A click-through flow per family with the exact legacy messages.
3. The slice's parity rows: `implemented_in`, `test`, `status` (`verified` only after the AGENTS.md checklist).
