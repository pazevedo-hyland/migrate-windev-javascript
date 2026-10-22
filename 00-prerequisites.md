# 00 — Prerequisites

Use Git, Python 3.10+ for the optional inspection tool, a supported Node LTS with npm, and the Rust toolchain. Pin actual Node/Rust/dependency versions in the application repository; commit npm and Cargo lockfiles. Install the platform prerequisites listed in [Tauri's guide](https://v2.tauri.app/start/prerequisites/): macOS needs Xcode tooling, Windows needs its C++ build tools and WebView2, and Linux needs its system webview/build libraries.

A Windows machine with the original WINDEV version may still be necessary to run the old app, export binary queries as SQL, inspect encoded designer properties, and export HFSQL data through supported tooling. Reading a text window file does not require WINDEV; reproducing the runtime may.

Work from a copy. Collect text project/window/report source, global procedures and classes where present, XDD or SQL schema, parameterized query definitions, representative screenshots, sample PDFs, hardware dependencies, and sanitized data with encoding notes. A generated documentation PDF can complement missing sources.

Choose one development checkout and an isolated test database. A VM is useful for legacy Windows behavior or platform testing but is not mandatory for every coding session. Configure GitHub authentication without embedding tokens in URLs or files.
