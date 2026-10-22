# 02 — Infrastructure and delivery

Use a GitHub repository for the reusable playbook, and separate repositories for private business migrations. Keep legacy input and raw analysis local. CI uses synthetic fixtures rather than customer databases.

Application CI should install locked dependencies (`npm ci`), type-check, lint, run domain tests, and build the frontend. Rust changes add `cargo fmt --check`, `cargo clippy --locked -- -D warnings`, and `cargo test --locked`. Run native builds on each intended OS with its Tauri prerequisites. A browser test does not prove native IPC, persistence, printing, or installer behavior.

Tauri's [GitHub pipeline guide](https://v2.tauri.app/distribute/pipelines/github/) describes native packaging. Build Windows artifacts on Windows and macOS artifacts on macOS. Test Linux if it is a supported target. Keep smoke-test records for install, start, database migration, save/reopen, upgrade, and uninstall behavior.

Use [Tauri's updater](https://v2.tauri.app/plugin/updater/) if automatic updates are required. Updater signatures and operating-system code signing are distinct. Signing private keys belong in release secrets; verification public keys can ship with the app. Never embed a reusable GitHub access token to let desktops fetch private releases; provide an appropriate distribution service instead.

Keep release and test channels separate. App rollback may require data restoration if a migration is incompatible. Test a real old-to-new upgrade and backup restoration before rollout. Nightly checks are optional infrastructure, not a required AI loop.
