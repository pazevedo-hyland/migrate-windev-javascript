# __APP_TITLE__

React/TypeScript + optional Tauri shell, with vendored reusable UI and reporting packages.

```sh
npm ci
npm run dev
```

The included directory is a synthetic, in-memory example. Extracted screens without an adapter show drafts and disabled actions. Add queries, permissions, calculations and transactional saves in maintained application code; bind controls in `src/adapters.ts` using qualified paths. `src/generated/` is generator-owned. Regeneration refuses edited or unexpected files. Layout generation never marks migration parity verified.

The sample definition is in `examples/layouts/`; regenerate it with the guide's `scripts/generate_screens.py --input <app>/examples/layouts --output <app>/src/generated --language en`. Exact recognized dossier kind aliases are normalized with `source_kind` retained. Unconfigured source images use a neutral preview with diagnostics; originals remain unchanged. Supply authorized, checked assets through `UiProvider` when reproducing a skin.

Window chrome: a layout with a `RADTitle` control or extracted system buttons draws them where the layout puts them (a skinned title bar). A layout with neither gets a system title bar **above** its client area (`wd-frame--native`, height `--wd-native-title`), because WINDEV control coordinates are client-relative; drawing the title and close box inside the client area put the close box over a form's top-right buttons (layout match with the designer image 32 % → 79 % once fixed). Buttons with a skin image (`background_image`) get the class `wd-button--skin`; their caption colour is a skin-specific setting, neutral by default: set `--wd-skin-button-color` and `--wd-skin-button-text-shadow` on a container when the skin's button image is dark (a blue WINDEV skin needed `#fff` and `0 1px 1px #0006`; dark text on it was unreadable in the installed app).

Windows open through `src/runtime/windows.tsx` (`WindowManager`, `useOpenWindow`): Open(WIN_X, params) resolves with the value given to Close(); OpenChild windows close with their opener; a window opened by another blocks its opener until it closes; the adapter's `onClosing` is the Closing event (resolve false = ReturnToCapture); Esc presses the window's Abort-type button; `title` sets ..Title at runtime. Tables sort on a click on a column title and the magnifier selects the first row starting with the typed text, unless the screen passes its own `onSort`/`onColumnSearch`. Decimal edits follow `setDecimalSeparator` (WINDEV uses the Windows regional setting). WLanguage built-ins live in `src/domain/wl/` (pure, tested; extend with golden values from the legacy app).

`packages/ui` shares windows, tables (TanStack), drag/resize (react-rnd), forms, masks, dialogs, calendars and geometry stores. Configure `UiProvider` for application namespace, language/labels, theme assets and sound; the default theme uses no WINDEV assets. Date masks retain the supported explicit WINDEV format; check unsupported date/currency conventions before reuse.

`packages/testing` shares Playwright scenarios for create/edit/reopen, cancel, rejected saves, search/selection and delete confirmation. Configure UI drivers, an independent persistence reader and explicit expected values; see [its contract](packages/testing/README.md) and `ui-check/workflow-contracts.spec.ts` for two different consumers. Successful saves reload and reopen records; comparisons retain unaffected rows and string IDs. The synthetic browser fixtures use scratch SQLite through a test-only server, separate from the in-memory demo and production build. Driver actions must await completion; bounded unchanged-data checks do not establish all future behavior or legacy parity.

`packages/reports` shares offline HTML/CSS pagination (Paged.js), PDF output (Playwright/Chromium), paper/band geometry and pinned fonts. Report data, grouping, calculations and event logic remain application-owned. `npm run report:demo` explicitly uses installed Chrome for development; configure a pinned executable/version/SHA for deployment. Chromium distribution and native printing are separate deployment tasks.

The report renderer runs on a Node host, outside the Tauri webview. Decide its hosting/distribution during framing; using the UI starter does not choose a server topology. The pure report geometry adapter can be consumed independently.

Use the Node/npm versions in `package.json` and an installed Google Chrome. The real PDF assertions also require Python with `pypdf==6.21.2` (`python3 -m pip install pypdf==6.21.2` in a virtual environment); set `PYTHON` to that environment's Python executable. There are no browser downloads during tests.

```sh
npm run verify             # types, production build, unit tests, production-build smoke, browser flows (installed Chrome)
npm run smoke:prod         # after vite build: the built app (vite preview) renders its first window, no data: images
npm run tauri -- dev       # optional; Rust + OS Tauri prerequisites required
npm run tauri -- build --debug --no-bundle
```

The dev server and the browser flows do not exercise the production build. Vite inlines files under 4 KiB as `data:` URLs only when building, and the skin resolver refuses `data:` URLs: on a real migration the packaged app rendered a blank window while every flow passed. `vite.config.ts` therefore sets `build.assetsInlineLimit: 0`, and `npm run smoke:prod` (`ui-check/prod.smoke.spec.ts`) opens the built app; extend it to the application's first real window with its skin.

For actual migrations, retain the guide's evidence, mapping, framing and acceptance stages. Browser checks do not prove Windows/macOS native printing, deployment or legacy parity. Replace the synthetic smoke tests as you wire real workflows. Keep legacy sources, data and credentials out of Git.
