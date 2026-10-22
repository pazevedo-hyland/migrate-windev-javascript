# 07 — Replacing WINDEV platform services

| Legacy facility | TypeScript/Tauri direction | Work to verify |
|---|---|---|
| Windows and event code | React screens + TypeScript use cases | Focus order, keyboard workflows, validation, dense tables |
| HFSQL operations | SQLite native repositories or server API | Transactions, locking, constraints and import parity |
| User Groupware | Explicit roles/permissions and administration | Enforce permissions at native/server boundary; UI visibility is only feedback |
| Reports | HTML print layouts or a selected PDF generation library | Pagination, totals, fonts, barcode/label dimensions and printer behavior |
| Private store and updates | Tauri packaging + updater | Signed updates, OS signing, staged rollout and recovery |
| File dialogs and filesystem | Scoped Tauri plugins/commands | Allowed paths, cancellation, encoding and failure handling |
| Barcode devices | Keyboard input or a device-specific native adapter | Real scanner model, suffix keys, timing and disconnected device |
| Scheduled jobs | OS service/scheduler or server worker | A closed desktop app cannot run its own jobs |
| Logs | Structured native/application logs | Redact customer information and define retention |
| COM/DLL integrations | Windows Rust adapter, sidecar, or remote service | Architecture, licensing, deployment and cross-platform alternatives |
| Replication | Explicit synchronization service if required | Conflict resolution, retries, tombstones and reconciliation |

Tauri does not supply a drop-in WINDEV report designer or Groupware administration system. User-editable reports and fine-grained permissions are features to scope, implement and test. A browser print preview does not prove silent printing works in a packaged desktop app. Keep server-only libraries out of the webview and avoid adding a Node sidecar unless a concrete requirement warrants it.

Check selected library licenses and official APIs before introducing dependencies. Migrate only platform services the actual source application uses.
