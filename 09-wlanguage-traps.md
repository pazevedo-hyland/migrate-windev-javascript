# 09 — WLanguage → TypeScript traps

Agents fail silently where WLanguage and TypeScript **look** alike but behave differently. Copy this chapter into the application as `docs/wlanguage-traps.md`, keep it referenced from `AGENTS.md`, and **add every new trap found** during the migration.

> **Verify against your version.** Semantics vary across WINDEV versions and project settings (Unicode or ANSI, null handling, French or English keywords). Each item says what to check; confirm it in the [WLanguage documentation](https://doc.windev.com/) and, when it matters, with a golden case recorded in the legacy app. Never "fix" a legacy behavior silently: preserve it or record an ADR.

## Reading the code

- **Keywords may be French**: `SI … ALORS … SINON … FIN`, `POUR … ALLANT DE … A`, `TANTQUE`, `PROCÉDURE`, `RENVOYER`, `HLitRecherchePremier`. The same project can be shown in English (`IF … THEN`, `HReadSeekFirst`). Map names through the official function list; do not guess from the spelling.
- **Comments** start with `//`; `/* */` blocks exist. Strings use `"…"`; `""` inside is an escaped quote.
- **Event code is spread** over the window (global declarations, end of initialization, closing), each control (initialization, entry, whenever modified, exit, click…), the project (initialization, closing) and procedure sets. The inspector records the path and raw event code; map the order of execution explicitly (see [Events](#events-and-ui)).

## Strings

| WLanguage | Trap | TypeScript rule |
|---|---|---|
| `Middle(s, start, len)`, `s[[i]]`, `s[[a TO b]]`, `Position` | **1-based** positions; `Position` returns **0** when not found | Use helpers `middle()`, `position()` with 1-based tests; never raw `substring`/`indexOf` |
| `Replace(s, a, b)` | Replaces **all** occurrences by default | `replaceAll`, never `replace` |
| `=` on strings | Exact comparison; trailing spaces and case handling depend on operator and settings — check | Write tests from real examples |
| `~=`, `~~`, `[=`, `[~` | **Flexible** equality (case, spaces, accents, punctuation ignored to different degrees), "starts with" | Implement as named functions with tests per operator, using `normalize('NFD')` for accents |
| `Upper`, `Lower`, `NoAccent` | Locale and accent handling | `toLocaleUpperCase('fr-FR')`, explicit accent stripping |
| `ExtractString(s, n, sep)` | 1-based occurrence; special return when out of range — check | Helper with tests |
| `Complete`, `Left`/`Right` padding | Pad or truncate to a length | Helper; check behavior with shorter strings |
| String ↔ number | **Implicit conversion** in assignments and some operations (`"12" + 1`?) — check each case | Explicit `parse`/`format`; never rely on JS coercion |
| `NumToString(x, "08.2f")`, display masks | Format masks and locale (decimal comma, thousands separator) | A tested `format()` per mask used; `Intl.NumberFormat` with explicit locale |
| ANSI vs Unicode projects, `Buffer` | Older projects store ANSI (Windows-1252) strings; byte length ≠ character length | Decode at import; buffers stay `Uint8Array` |

## Numbers and money

| WLanguage | Trap | TypeScript/Rust rule |
|---|---|---|
| `currency` (*monétaire*) | Fixed-point type with many significant digits and several decimals — not a binary float | Never `number` for money. Integer minor units (`bigint`) or a decimal library (decimal.js, big.js); `rust_decimal` in Rust |
| `numeric` (*numérique*) | High-precision decimal | Same as above |
| `int`, 8-byte `int`, automatic IDs | Values above 2^53 lose precision in JS `number` | `bigint` or decimal **strings** across IPC |
| `real` | Binary double, like JS `number` | `number` is fine — but check whether the legacy item was really real |
| `Round(x, n)` | Rounding mode differs from `Math.round` (which rounds .5 toward +∞: `Math.round(-2.5) === -2`) | One tested `round()` built from legacy golden values, including negatives and .5 cases |
| Integer division, `Modulo`, `IntegerPart`, `Truncate` | Result type and sign handling — check | Explicit helpers with negative test cases |
| Implicit type of a variable | Assigning a real to an int truncates or rounds — check | Explicit conversions |
| Order of VAT/discount/rounding | Line-level vs total-level rounding changes cents | Encode the order in the domain function; golden test with many lines |

## Dates, times and durations

| WLanguage | Trap | TypeScript rule |
|---|---|---|
| `Date` as string `"YYYYMMDD"`, `Time` `"HHMMSSCC"` (hundredths), `DateTime` | Dates are often stored and compared **as strings**; empty date `""` or `"00000000"` | A `PlainDate` type (Temporal polyfill or date-fns with plain dates); explicit empty value |
| `DateSys()`, `TimeSys()`, `Today` | Local time of the workstation | Inject a clock; never `new Date()` inside domain code |
| `new Date("2026-01-02")` in JS | Parsed as **UTC** — shifts the day in negative offsets | Never parse ISO dates with `Date` in domain code |
| Date arithmetic (`+ 1`, `DateDifference`) | Day-based arithmetic, inclusive/exclusive bounds | Tested helpers; check month ends and leap years |
| `Duration` | Units (ms, s, min, hundredths) | Store integer units, name them (`durationMinutes`) |

## Arrays, loops and control flow

| WLanguage | Trap | TypeScript rule |
|---|---|---|
| Arrays `t[1]`, `ArrayAdd`, `ArrayCount` | **1-based** indexes | Convert loops explicitly; tests on first/last element |
| `FOR i = 1 TO n` | Inclusive upper bound; whether the bound is re-evaluated each iteration — check | `for (let i = 1; i <= n; i++)` with a captured bound if legacy captured it |
| `FOR EACH x OF array`, `FOR EACH File` | Iterates and positions the **current record** (see HFSQL) | Explicit query + loop over rows |
| `SWITCH … CASE 1, 2`, `CASE 3 TO 5`, `CASE > 10`, `OTHER CASE` | Ranges and comparisons in cases | `if/else` chains; no fall-through |
| `RESULT`, `RETURN` | Return value vs leaving a procedure | Map each exit path |
| Procedure parameters | **Passed by reference by default** in WLanguage (unless `LOCAL` or an expression is passed) — a callee can modify the caller's variable | Return new values explicitly; search callers for parameters modified in callees |
| Optional parameters, `MyParameters` | Defaults and "not given" vs empty | Explicit `undefined` handling |

## HFSQL access (the biggest trap)

| WLanguage | Trap | Target rule |
|---|---|---|
| `HReadSeekFirst`, `HReadNext`, `HFound`, `HOut`, `File.Item` | A **global current record buffer per file**: reading sets `Customer.Name`, which other code then uses implicitly | Make every read return a value; trace which code reads the buffer later |
| `HAdd`, `HModify`, `HDelete` (without explicit record) | Write **the current buffer** | Explicit entity passed to the command |
| Window "independent HFSQL context" option | Without it, windows share file positions and filters | Per-window state; test two windows open at once |
| `HFilter`, `HActivateFilter`, `HDeactivateFilter` | Filters persist on the file until removed | Explicit query parameters |
| Queries with parameters | A condition whose **parameter is not given (or null) is ignored** by default | Build dynamic `WHERE` clauses replicating this, with tests for each omitted parameter |
| `ScreenToFile` / `FileToScreen` | Automatic binding between controls and file items | Explicit mapping in the form model; list linked items in `docs/screens/` |
| Table controls **bound to a file/query** | Automatic paging, sorting, filtering, in-place edits written directly | Paginated query command + explicit save command |
| `HExecuteSQLQuery(q, "select … where numero='" + x + "'")` | SQL **built by string concatenation**: injection risk, and quoting/escaping, `LIKE` and date formats are part of the behavior | Parameterized queries in the command; tests with quotes, wildcards and empty values in the inputs |
| `TableDisplay`, `TableDisplay(…, taCurrentSelection)` | Refreshes a table control from its source and keeps or moves the selection | Re-run the query command after each save; test selection and scroll position after refresh |
| `HTransactionStart/End/Cancel` | Transaction scope across calls | One command, one transaction |
| `HLockRecord`, lock modes, `HOnError` | Custom handlers change what happens on lock/duplicate/integrity errors **globally** | Find every `HOnError`; map each error to a typed result and the same user message |
| `HDescribeTrigger` | WLanguage procedures run before/after H functions on a file | Inventory them; call the logic explicitly in commands |
| Automatic error dialogs | HFSQL errors can show WINDEV's default dialogs if unhandled | Decide explicit messages per error |

## Events and UI

| WLanguage | Trap | Target rule |
|---|---|---|
| Event order: window global declarations (with parameters) → controls initialization → window end of initialization | Initialization order affects values | Map into an explicit `load()` sequence per screen; test it |
| `Open(WIN_X, params)` returning a value, `Close(WIN_X, value)` | **Blocks** until the window closes | `await openDialog(...)` and keep the following code after it |
| `Info`, `Error`, `YesNo`, `OKCancel`, `Dialog` | Modal and **blocking**; code continues after the answer | Awaited dialog service; keep exact texts and button order |
| `Dialog` resources (`dialogs` in the inspector output) | `cancel_button` names the button triggered by Esc/close — by position or by value is not documented in the source; when button 1 has value 1 ("Sim" / "&Delete"), Esc may **confirm** a delete | Treat as unresolved until observed in the running app; never default Esc to the destructive answer silently |
| `OpenChild`, `OpenSister`, `OpenMobileWindow` | Non-modal; several windows alive with shared globals | Multi-window or tabs per ADR; explicit shared state |
| `ExecuteProcess(BTN_X, trtClick)` | Runs another control's event code | Extract the code into a named function called from both |
| `{"EDT_" + n}` indirection, `..Property` | Dynamic access to controls and properties by name | Keyed maps of fields; list every indirection in the mapping note |
| `MySelf`, `MyWindow`, `..Value`, `..Visible`, `..State`, `..Color` | Properties changed from code drive UI rules | Derived state from data; document each rule in the screen spec |
| "Whenever modified", "Exit" events | Fire per keystroke vs on focus loss | `onChange` vs `onBlur`; test with keyboard |
| `Timer`, `TimerSys`, `Multitask`, `ThreadExecute` | Periodic code, yielding, background threads | `setInterval` with cleanup, async tasks, Rust background tasks |
| Input masks, uppercase fields, max lengths | Defined in the designer, often not in code | Screen spec from screenshots/designer; tests per field |
| Keyboard: Enter as Tab, default/cancel button, shortcuts (`&` in captions) | Users depend on them | Global keyboard handling per ADR; walkthrough tests |

## Errors and exceptions

- `WHEN EXCEPTION IN … DO`, `CASE ERROR:`, `CASE EXCEPTION:`, `ErrorOccurred`, `ErrorInfo`, `ExceptionChange`: WLanguage separates **errors** and **exceptions** with their own handlers. Map each to a typed result or a thrown error, deliberately; keep the messages.
- Default WINDEV error windows shown to users are behavior too: decide the replacement message per case.

## Project-level state and environment

- **Globals** declared in the project initialization code or window global declarations are visible across windows (`WIN_X.variable`). Inventory them; replace with explicit stores.
- **Paths**: `fExeDir`, `fCurrentDir`, `fDataDir`, backslashes, drive letters → Tauri path API (`appDataDir`, `appConfigDir`) and `path.join`.
- **INI/registry**, environment variables, command-line parameters (`CommandLine`) → explicit config with a Windows migration path.
- **Printing, external programs, DLL/COM, email** → adapters ([07 §G](https://github.com/pazevedo-hyland/migrate-windev-javascript/blob/main/07-platform-replacements.md#g-desktop-integrations)).

## How to use this chapter

1. During mapping, flag each construct found in a block in the note (`HFSQL current record`, `modal Open`, `by-reference parameter`…).
2. Write shared helpers (`middle`, `position`, `round`, `formatMask`, `plainDate`) **once**, in `src/domain/wl/`, each with golden tests from the legacy app.
3. The review skill checks every translated block against this list.
