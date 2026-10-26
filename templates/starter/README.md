# __APP_TITLE__

React/TypeScript + optional Tauri shell, with vendored reusable UI and reporting packages.

```sh
npm ci
npm run dev
```

The included directory is a synthetic, in-memory example. Extracted screens without an adapter show drafts and disabled actions. Add queries, permissions, calculations and transactional saves in maintained application code; bind controls in `src/adapters.ts` using qualified paths. `src/generated/` is generator-owned. Regeneration refuses edited or unexpected files. Layout generation never marks migration parity verified.

The sample definition is in `examples/layouts/`; regenerate it with the guide's `scripts/generate_screens.py --input <app>/examples/layouts --output <app>/src/generated --language en`. Exact recognized dossier kind aliases are normalized with `source_kind` retained. Unconfigured source images use a neutral preview with diagnostics; originals remain unchanged. Supply authorized, checked assets through `UiProvider` when reproducing a skin.

`packages/ui` shares windows, tables (TanStack), drag/resize (react-rnd), forms, masks, dialogs, calendars and geometry stores. Configure `UiProvider` for application namespace, language/labels, theme assets and sound; the default theme uses no WINDEV assets. Date masks retain the supported explicit WINDEV format; check unsupported date/currency conventions before reuse.

`packages/reports` shares offline HTML/CSS pagination (Paged.js), PDF output (Playwright/Chromium), paper/band geometry and pinned fonts. Report data, grouping, calculations and event logic remain application-owned. `npm run report:demo` explicitly uses installed Chrome for development; configure a pinned executable/version/SHA for deployment. Chromium distribution and native printing are separate deployment tasks.

Use the Node/npm versions in `package.json` and an installed Google Chrome. The real PDF assertions also require Python with `pypdf==6.21.2` (`python3 -m pip install pypdf==6.21.2` in a virtual environment); set `PYTHON` to that environment's Python executable. There are no browser downloads during tests.

```sh
npm run verify             # types, production build, unit tests, browser flows (installed Chrome)
npm run tauri -- dev       # optional; Rust + OS Tauri prerequisites required
npm run tauri -- build --debug --no-bundle
```

For actual migrations, retain the guide's evidence, mapping, framing and acceptance stages. Browser checks do not prove Windows/macOS native printing, deployment or legacy parity. Replace the synthetic smoke tests as you wire real workflows. Keep legacy sources, data and credentials out of Git.
