# Portable UI source package

`@windev-migration/ui` is a React 19 workspace package. Import its source through the starter's Vite/TypeScript build. Primitives import their CSS; `@windev-migration/ui/style.css` is also available to hosts. No images, fonts, extracted layouts, native bridge, database or application records ship here.

```tsx
<UiProvider config={{ namespace: "my-application", locale: "en", labels: { close: "Close" } }}>
  <DialogProvider>
    <WdWorkspace>{/* a launcher using useWorkspace().open(...) */}</WdWorkspace>
  </DialogProvider>
</UiProvider>
```

Use a stable namespace per application. Geometry and table preferences are scoped to that provider; changing its namespace remounts descendants. Optional `geometryStore`, `tableLayoutStore` and `playSound(type)` adapters stay with the host. Store factories also accept `(storage, namespace)` for isolated tests or alternate browser storage.

Main exports:

- `LegacyLayout`, `LegacyControl`, `LegacyColumn`, `controlOf`, `controlBox`, anchoring helpers and `WdRadControls`/`WdRadBinding`. Bind values, events and traversal explicitly; duplicate short control names require a qualified `path`.
- `WdFrame`, `WdModal`/`WdModalHandle`, `WdWorkspace`, `useWorkspace`, `useWorkspaceClose`. A known window size/title is enough for neutral chrome. Exact supplied title/chrome controls retain their metadata; absent chrome uses target defaults.
- `WdButton`, `WdEdit`, `WdMemo`, `WdCheckbox`, `WdCheckMark`, `WdRadio`, `WdCombo`, `WdCalendarEdit`, `WdDateEdit`, `WdDateTimeEdit`.
- `WdTable` with explicit `control`, `rows`, `rowId`, `cell(row, column)`, `selectedId`, `onSelect`; optional sorting/search/activation and `useTableLayout(control, settingsKey)` preference callbacks. Rows above 500 use virtualization.
- `DialogProvider`/`useDialogs`, `MessageController`, message/resource request/result types, optional exact calculator. Each `message(...)` or `resource(...)` returns one awaited result; concurrent requests queue. Destructive resources require an explicit non-mutating `safeIndex`.
- Pure integer/decimal mask helpers, date/date-time draft helpers, suggestion/mnemonic helpers and browser clipboard adapter.

Labels and mnemonic case folding are configurable. Date entry currently uses `DD/MM/YYYY` display with compact `YYYYMMDD` storage, including explicit zero dates; decimal masks use comma fractions and ASCII-space grouping. NULL, empty, opaque originals and hidden datetime precision remain distinct until an explicit edit. These formats are declared target defaults; other formats need their own adapters.

The default theme and message/resource geometry are original starter designs, not a WINDEV skin or a parity claim. A host may supply an authorized `assets` inventory such as `{ action: { source: "/assets/action.svg", states: ["/assets/normal.svg", "/assets/hover.svg"] } }`; controls refer to inventory keys, never unchecked paths. URLs must be same-origin files. One image, two button states, or five button states are supported; two-state buttons reuse hover for pressed. No graphics are extracted or downloaded by this package.
