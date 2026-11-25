# Source-based WINDEV visual QA

The extractor reads editable window metadata and project-local assets. It writes a layout JSON and a standalone HTML preview. Generate first and use a native screenshot only for QA. These commands do not start the WINDEV application.

Use Python 3.10+ with Pillow. For browser capture, add Playwright and install Chromium with `python -m playwright install chromium`, or pass the executable of an installed Chromium browser via `--browser`.

```sh
python scripts/visual_qa/extract_windev_visual.py --tools . --project "<WINDEV project>" --unit WIN_Example --out analysis-local/example
python scripts/visual_qa/capture_windev_visual.py analysis-local/example/preview.html --viewport 1600x1000 --out analysis-local/example-qa
```

Use `--viewport WIDTHxHEIGHT` on the extractor to apply decoded anchors to a resized design. Use `--ribbon-tab "Caption" --ribbon-only` to inspect just one ribbon page. The extractor walks ancestor tab requirements, clips child controls to pane bounds, and suppresses table cell editors in the window layer. The optional `--profile` JSON supplies named, source-backed visibility scenarios through `unit` and `scenarios` entries. Each scenario has a `label` and a list of `modes`, each with a `label` and a `visibility` mapping from qualified control paths to booleans.

Capture measures the selected element at browser scale 1. The default is the whole preview canvas. Pass `--selector` to capture a region such as the modal frame. Use `--expect` with a JSON object containing `present`, `absent` and `boxes` as needed. A box is `[x, y, width, height]` relative to the canvas. The report identifies the browser and hashes the preview and capture.

For an aligned visual comparison, pass `--reference original.png` and optionally `--reference-box X,Y,WIDTH,HEIGHT`. Both regions must have equal pixel dimensions. The report records exact RGB equality, grayscale similarity and edge overlap. The comparison image shows the native region, the preview and the difference. Use corresponding states, DPI and crop boundaries. Scores do not establish parity. Keep generated captures, layouts and configuration data local.

Use the audit to find explicit visual property writes and compare editable and compiled metadata:

```sh
python scripts/visual_qa/windev_visual_audit.py audit --tools . --source "<project>/WIN_Example.wdw" --layout analysis-local/example/layout.json --compiled "<compiled>/WIN_Example.wdw" --out analysis-local/example/audit.json
python scripts/visual_qa/windev_visual_audit.py inventory --project "<project>" --compiled-directory "<compiled>" --out analysis-local/visual-inventory.json
```

Review unresolved paths, first-state sprite choices, native font metrics, and runtime visibility and positioning before using the render as a target. Compiled controls corroborate decoded fields. They do not attest to runtime execution or final painting.
