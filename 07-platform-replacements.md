# 07 — Replacing WINDEV platform services

Migrating code and data does not replace *everything* PC SOFT provided "in the box". This chapter maps the remaining services to TypeScript/Tauri options. Each is a **project choice**, recorded as an ADR; none is mandatory. Licence (open source or proprietary) and hosting (yours or third-party) are stated as facts, without preference. **Migrate only the services the application actually uses** — the mapping notes tell you which. Check licences and official APIs before adding a dependency, keep server-only libraries out of the webview, and add a Node sidecar only for a concrete requirement.

*Abbreviations are expanded at first use and collected in the [glossary](#glossary).*

## Quick map

| Legacy facility | TypeScript/Tauri direction | Work to verify |
|---|---|---|
| Windows and event code | React screens + TypeScript use cases | Focus order, keyboard, validation, dense tables, modal flow ([09](09-wlanguage-traps.md)) |
| HFSQL operations | Rust commands over SQLite, or server API over PostgreSQL ([08](08-data-migration.md)) | Transactions, locking, constraints, collation, import parity |
| Error reporting / telemetry | Structured logs + OpenTelemetry or an error tracker (§A) | Redaction, retention, offline buffering |
| OAuth server, login, **User Groupware** | OIDC provider + control-level permissions (§B) | Enforcement in commands, admin screen |
| Private store, network install, updates | Tauri bundler + updater + optional portal (§C) | Signing, channels, rollback |
| Report editor, Reports & Queries | Code-defined PDF/HTML layouts, or an embeddable designer (§D) | Pagination, totals, fonts, labels, printing |
| Scheduled tasks, automata | OS scheduler or server worker (§E) | A closed desktop app runs nothing |
| File dialogs, filesystem, INI, registry | Scoped Tauri plugins/commands; app config dir (§G) | Allowed paths, encoding, settings migration |
| Barcode, scanners, serial, label printers | Keyboard-wedge input or native adapter (§G) | Real device model, suffix keys, timing, disconnection |
| Excel/Word/Outlook automation, email | File generation libraries; SMTP from Rust (§G) | Formats, templates, attachments |
| COM/DLL/ActiveX | Windows-only Rust adapter, sidecar or remote service (§G) | Architecture (32/64-bit), licensing, cross-platform alternative |
| Replication, offline mode, mobile | Explicit synchronization service (§F) | Conflicts, retries, tombstones, reconciliation |
| Real-time, web services, WebDev server | TypeScript API + WebSockets (§F) | Authentication, reconnection |
| HFSQL Control Center | The target database's own admin tools (§F) | — |

> **No drop-in equivalents.** Tauri provides no WINDEV report designer and no Groupware administration system. User-editable reports and fine-grained, user-administered permissions are **features to scope, implement and test** like any module. A browser print preview does not prove silent printing works in a packaged app.

---

## A. Telemetry and error reporting

**Need** (≈ WINDEV automatic error reports / anomaly feedback): see what happens in production — errors, slowness, volumes, and a trace of an operation end to end. (Not the HFSQL Control Center, which administers the database — see §F.)

**Direction.**

- **Logs**: [tauri-plugin-log](https://v2.tauri.app/plugin/logging/) for structured Rust + webview logs to rotating files in the app log directory. Redact customer data; define retention.
- **Traces/metrics**: [OpenTelemetry](https://opentelemetry.io/) (open standard, CNCF — *Cloud Native Computing Foundation*), with the Rust and JavaScript SDKs, exported to a backend you host such as [SigNoz](https://signoz.io/) (open source core). OpenTelemetry is how the app **emits**; the backend is where you **look**; you can switch backends without touching instrumented code.
- **Error tracking**: an error tracker with Rust and JavaScript SDKs (e.g. Sentry, self-hosted or SaaS) is often the fastest win for a desktop app: crash and exception reports with release versions.

**Start**: log to file first; add one error-reporting path; verify a **real** error arrives with version and OS before broadening. Desktop apps go offline: buffer and send later, never block the UI.

## B. Identity, OAuth and rights

Three PC SOFT needs land here: the **OAuth server**, **authentication**, and — the hardest — **User Groupware administration**.

**Need.**

- **OAuth server / login** (≈ WEBDEV OAuth server): authenticate users and issue tokens using **OAuth 2.0** (authorization) and **OpenID Connect / OIDC** (authentication on top of OAuth 2.0).
- **User Groupware** (≈ WINDEV built-in module): far more than login. Its core — and **the real challenge** — is that **an authorized end user administers rights from inside the app, down to the button**: who may click what, who sees which window or field, **without a developer, without recompiling, effective immediately**.

**Direction.**

- **Authentication**: an OIDC provider such as [Keycloak](https://www.keycloak.org/) (open source, CNCF; OIDC/OAuth 2.0/SAML, SSO, directory federation such as Microsoft Entra ID, MFA, passkeys), or your organization's existing provider. Desktop apps use the **system browser with PKCE** (RFC 8252, "OAuth for native apps") and a loopback or deep-link redirect ([deep-link plugin](https://v2.tauri.app/plugin/deep-linking/)); never an embedded login form. Store refresh tokens in the OS keychain (e.g. the `keyring` crate), never in plain files.
- **Local-only apps without a server** can keep local accounts: hash passwords with Argon2id (`argon2` crate). Do not import unknown legacy password formats; plan a reset or a supported rehash path.
- **Groupware-style rights — the pattern to build**:
  1. a **control catalog** with a stable key `Window.Control` (e.g. `WIN_Order.BTN_Delete` — the legacy names, already used as `data-testid`), generated statically from the mapping, or registered at first display of each screen as WINDEV does;
  2. a **rights table** `(user or role × control × action: see / enable / edit)` edited by an **admin screen** available to authorized users;
  3. **application** of rights when a screen opens (`visible / disabled / readOnly`) **and** an **authorization check in every command** (hiding a button is not security);
  4. a decision engine if rules grow complex: [Casbin](https://casbin.org/) (Rust and JS), [OpenFGA](https://openfga.dev/), or Keycloak authorization services.
- Migrate Groupware users/groups and rights from their HFSQL files if they are used; never their passwords.

> **The hard part, with a way through.** There is no packaged equivalent of user-administered, button-level rights editable live. **Estimate it as a module in its own right** (catalog + table + admin screen + enforcement), with parity rows for each right that exists today.

**Start**: inventory Groupware use (which windows/controls, how many groups); decide provider and rights model in an ADR; implement enforcement in commands before the admin screen. No client secret in the app: public clients use PKCE.

## C. Distribution and updates — the private store

**Need** (≈ WINDEV private store, network install): an internal entry point where an **authorized** user sees the applications for them, clicks **download / install**, then receives **updates automatically**, with version history and rollback.

**Direction: Tauri bundler + updater (engine) + a small portal (store front) + identity (rights).**

- **Tauri bundler** produces installers (MSI/NSIS on Windows, DMG/app on macOS, AppImage/deb/rpm on Linux); **[updater plugin](https://v2.tauri.app/plugin/updater/)** checks an endpoint returning the latest version per platform and channel, verifies the **signature**, installs. Keep previous artifacts for rollback.
- **Portal**: a minimal web page listing apps and channels with download buttons, hosting the update manifests (static files, object storage, or a small TypeScript service).
- **Rights**: put the store front behind the OIDC login (§B); groups decide which apps and channels a user sees.

> **An honest nuance.** Protect **the store front** (human access, first download) with login. The **automatic update** is fetched by the client without a browser: serve it from an endpoint that needs no embedded long-lived secret (public signed artifacts, or short-lived signed URLs issued to an authenticated app). Never embed a reusable Git host token in the app.

**Start**: two channels (`prod`, `test`); publish to `test`; perform a **real** version bump (publish → client updates itself) before `prod`; test rollback.

## D. Reports and printing

**Need** (≈ WINDEV report editor and **Reports & Queries**): produce prints, **PDF**, barcode labels, composite reports, charts — and often let **end users create or customize their own reports**. Almost every WINDEV business app depends on it.

**Two directions.**

- **Code-defined reports** (layouts fixed by developers): HTML/CSS print templates rendered in a hidden window, or PDF generation with a library such as [pdfmake](https://pdfmake.github.io/docs/) (TypeScript, declarative) or [Typst](https://typst.app/) (Rust-embeddable typesetting). Barcodes with [bwip-js](https://github.com/metafloor/bwip-js). **Limit**: no end-user designer — self-service stays a module to build.
- **Embeddable designers** (end users draw reports, ≈ Reports & Queries): commercial JavaScript reporting suites with an in-app designer (evaluate, for example, ActiveReportsJS or Stimulsoft Reports.JS). Proprietary, usually per-developer licences; they run inside your app. Check licences and offline operation.

**Printing**: `window.print()` goes through the OS print dialog. **Silent printing** to a named printer, label printers and tray selection need a native command per OS (e.g. generate PDF, then print through the platform spooler; raw ZPL/EPL for label printers). Prove it on the real printer models.

**Start**: inventory reports (how many, fixed vs user-defined, labels, silent print); collect a sample PDF **with its input data** for each; implement one complex report (breaks, subtotals, chart) and compare its extracted text and totals against the legacy PDF before generalizing ([10](10-parity-and-verification.md)).

## E. Scheduled tasks and batch

**Need** (≈ HFSQL scheduled tasks, WEBDEV server scheduled tasks, WINDEV automata): run jobs **at a set time** or from a queue — imports, nightly calculations, sending, purges.

**Direction**: a desktop app that is closed runs nothing.

- **Local topology**: an OS-level scheduler (Windows Task Scheduler, launchd, systemd timers) launching the app or a small CLI built from the same Rust crate in headless mode.
- **Shared topology**: a server worker next to the API, e.g. a queue on PostgreSQL such as [pg-boss](https://github.com/timgit/pg-boss), or cron-style scheduling in the service.

**Start**: inventory jobs (what, when, safe to re-run?); make each **idempotent** and **logged** (§A); test a missed run and a double run.

## F. Depending on your profile — offline/mobile, real-time, database admin

Conditional services; handle them only if they apply.

- **Replication / offline mode** (≈ HFSQL universal replication, embedded databases): **no packaged equivalent ⚠️**. It is a **synchronization engine to build**: local SQLite + sync service + conflict rules + tombstones + reconciliation. A big project: estimate it seriously. Tauri 2 also targets iOS/Android if WINDEV Mobile parts must follow, with the same sync problem.
- **Push notifications**: mobile push goes through FCM (Google) and APNs (Apple). Desktop notifications: [notification plugin](https://v2.tauri.app/plugin/notification/); self-hosted push for web/desktop: ntfy or Gotify.
- **Real-time and web hosting** (≈ WEBDEV application server, web services, WebSockets): a TypeScript API (e.g. Fastify) with WebSockets for live notifications and refreshing screens. Low effort once a server exists.
- **Database administration** (≈ HFSQL Control Center): the target's native tools — DB Browser for SQLite, DBeaver (multi-database), pgAdmin (PostgreSQL). Not development work; install for administrators.

## G. Desktop integrations

- **Files and dialogs**: [dialog](https://v2.tauri.app/plugin/dialog/) and [fs](https://v2.tauri.app/plugin/file-system/) plugins with **scoped** paths; handle cancellation, encoding (legacy files are often Windows-1252) and failures.
- **INI files and registry** (`INIRead`, registry functions): move settings to a config file in the app config directory; write a one-time migration that reads the old INI/registry values on Windows.
- **Barcode scanners**: most act as keyboards (keyboard wedge) — handle suffix keys (Enter/Tab) and fast input timing in the focused field. Serial or USB devices need a Rust adapter (e.g. the `serialport` crate). Test with the real model and a disconnected device.
- **Excel/Word/Outlook**: replace OLE automation with file generation (e.g. [ExcelJS](https://github.com/exceljs/exceljs) for XLSX, docx templates), and email via SMTP from Rust (e.g. the `lettre` crate) or a `mailto:` handoff.
- **COM/DLL/ActiveX**: a Windows-only Rust adapter (`windows` crate / FFI), a sidecar process, or a remote service. Check 32/64-bit, licensing and deployment; record the cross-platform consequence in an ADR.
- **External programs** (`ExeRun`): the [shell plugin](https://v2.tauri.app/plugin/shell/) with an explicit allow-list of commands and arguments.

---

## Summary

| PC SOFT service | TypeScript/Tauri option | Licence | Hosting |
|---|---|---|---|
| Error reports / telemetry | tauri-plugin-log + OpenTelemetry → SigNoz, or an error tracker | open source / mixed | yours or SaaS |
| OAuth server + login | Keycloak or the organization's OIDC provider | open source / varies | yours or provider |
| Groupware rights administration | Control catalog + rights table + admin screen (+ Casbin/OpenFGA) | open source | yours *(module to build)* |
| Private store / updates | Tauri bundler + updater + portal | open source | yours |
| Fixed reports | HTML/CSS print, pdfmake, Typst | open source | in the app |
| Reports + end-user designer | Commercial JS reporting suite | proprietary | in the app |
| Scheduled tasks / batch | OS scheduler + headless CLI, or server worker (pg-boss) | open source | yours |
| Replication / offline | Custom sync engine | — | yours *(to build)* |
| Push notifications | FCM/APNs (mobile), ntfy/Gotify, notification plugin | proprietary / open source | Google/Apple or yours |
| Real-time / web services | TypeScript API + WebSockets | open source | yours |
| Database admin | DB Browser for SQLite, DBeaver, pgAdmin | varies | administrators |

> **How to read this table.** Licence and hosting are stated as **facts**; the guide favors none of these criteria. **No service is mandatory**: take what the project uses, record the choice in an ADR, **verify reality before wiring it**, and **version no secret**.

## Glossary

- **ADR** (*Architecture Decision Record*): a file recording one decision — context, choice, consequences.
- **APNs / FCM**: Apple and Google push notification services.
- **CNCF** (*Cloud Native Computing Foundation*): hosts projects such as Kubernetes, OpenTelemetry, Keycloak.
- **IPC** (*Inter-Process Communication*): here, calls between the webview (TypeScript) and the Rust core.
- **MFA** (*Multi-Factor Authentication*): login with a second factor.
- **OAuth 2.0**: standard authorization protocol (delegate access without sharing a password).
- **OIDC** (*OpenID Connect*): standard authentication protocol on top of OAuth 2.0.
- **PKCE** (*Proof Key for Code Exchange*): OAuth extension that lets public clients (desktop apps) log in safely without a client secret.
- **SAML**: an enterprise authentication/SSO protocol.
- **SSO** (*Single Sign-On*): one login for several applications.
- **Webview**: the system browser engine that renders a Tauri app's UI (WebView2, WKWebView, WebKitGTK).

## References

- WINDEV: [private store](https://doc.pcsoft.fr/fr-FR/?name=store_prive_des_applications_windev) · [User Groupware tips](https://doc.windev.com/en-US/?name=Tips_for_user_groupware&lf=fr) · [WEBDEV OAuth server](https://doc.windev.com/en-US/?name=Server_OAuth_WEBDEV&lf=fr)
- Tauri: [capabilities](https://v2.tauri.app/security/capabilities/) · [plugins](https://v2.tauri.app/plugin/) · [distribution](https://v2.tauri.app/distribute/)
- [OpenTelemetry](https://opentelemetry.io/) · [SigNoz](https://signoz.io/) · [Keycloak](https://www.keycloak.org/) · [Casbin](https://casbin.org/) · [OpenFGA](https://openfga.dev/) · [RFC 8252](https://www.rfc-editor.org/rfc/rfc8252)
