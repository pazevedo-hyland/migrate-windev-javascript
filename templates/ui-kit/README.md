# UI kit — the legacy skin as React primitives

Starting point for the foundation slice "skin kit" (ADR: keep the legacy look). Copy to `src/ui/legacy/` in the application.

- `wd.tsx` — primitives driven by the generated layout (`scripts/screen_layout.py` → `<WINDOW>.layout.json`): `WdWindow` (skinned frame, title as drag area, system buttons driving the native window), `WdButton` (9-slice background, 5-state icon), `captionSplit` (edit captions inside the legacy width), `WdMessage` (Info / Error / YesNo boxes in the skin). Controls keep `data-testid` = legacy name; edit captions are `<label htmlFor>` so the UI check reads them.
- `skin.css` — written for WINDEV's "120 MediaPlayer" template, measured on its images: window 9-slice 25/8/8/8, button 4, Trebuchet MS 8 pt. **Another skin template needs its own margins and font**: measure them on its images (`scripts/skin_assets.py` exports them) and mark colors sampled from the dossier image as `sampled`.
- Skin images go to `public/skin/` via `scripts/skin_assets.py`; the app's `tauri.conf.json` sets `decorations: false` and its capability allows `core:window:allow-start-dragging`, `allow-minimize`, `allow-toggle-maximize`, `allow-close`.

Measured on the pilot (client list and form): layout match 75 % and 91 %, pixel similarity 97 % and 98 % against the dossier images, behavior tests unchanged.
