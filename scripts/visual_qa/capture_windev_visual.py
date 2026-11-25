"""Capture a source-rendered WINDEV preview and optionally compare an aligned native region."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import sys


def dimensions(value):
    try:
        width, height = (int(part) for part in value.lower().split("x"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected WIDTHxHEIGHT") from error
    if min(width, height) < 1:
        raise argparse.ArgumentTypeError("Viewport dimensions must be positive")
    return width, height


def region(value):
    try:
        x, y, width, height = (int(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected X,Y,WIDTH,HEIGHT") from error
    if min(x, y) < 0 or min(width, height) < 1:
        raise argparse.ArgumentTypeError("Crop must have positive dimensions and a nonnegative origin")
    return x, y, x + width, y + height


def browser_capture(html, png, viewport, selector, browser_path, expectations):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as tools:
        options = {"executable_path": str(browser_path)} if browser_path else {}
        browser = tools.chromium.launch(**options)
        try:
            page = browser.new_page(viewport=dict(zip(("width", "height"), viewport)), device_scale_factor=1)
            # A standalone preview contains its images and does not need network access.
            page.route("**/*", lambda route: route.abort() if route.request.url.startswith(
                ("http://", "https://", "ws://", "wss://")) else route.continue_())
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(html.as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            target = page.locator(selector)
            if target.count() != 1 or not target.is_visible():
                raise ValueError(f"Capture selector must find exactly one visible element: {selector}")
            broken = target.locator("img").evaluate_all("(items) => items.filter(i => !i.naturalWidth).length")
            if broken or errors:
                raise ValueError(f"{broken} broken images; browser errors: {errors}")
            controls = page.locator("[data-control]").evaluate_all("""items => {
              const canvas = document.querySelector("#canvas").getBoundingClientRect();
              return Object.fromEntries(items.map(item => {
                const {x,y,width,height} = item.getBoundingClientRect();
                return [item.dataset.control, [x-canvas.x, y-canvas.y, width, height]];
              }));
            }""")
            for path in expectations.get("present", []):
                if path not in controls:
                    raise ValueError(f"Missing rendered control: {path}")
            for path in expectations.get("absent", []):
                if path in controls:
                    raise ValueError(f"Unexpected rendered control: {path}")
            for path, expected in expectations.get("boxes", {}).items():
                if controls.get(path) != expected:
                    raise ValueError(f"{path}: expected {expected}, got {controls.get(path)}")
            target.screenshot(path=png, animations="disabled", scale="css")
            return {
                "browser_version": browser.version, "viewport": list(viewport), "device_scale_factor": 1,
                "selector": selector, "controls_rendered": len(controls),
                "checked_boxes": {path: controls[path] for path in expectations.get("boxes", {})},
            }
        finally:
            browser.close()


def compare_aligned(reference, png, crop, diff):
    from PIL import Image, ImageChops
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from visual_compare import compare

    with Image.open(reference) as original, Image.open(png) as captured:
        image = original.convert("RGB")
        if crop:
            if crop[2] > image.width or crop[3] > image.height:
                raise ValueError("Reference crop lies outside the screenshot")
            image = image.crop(crop)
        if image.size != captured.size or min(image.size) < 5:
            raise ValueError(f"Comparison requires equal regions at least 5×5 px: {image.size}, {captured.size}")
        difference = ImageChops.difference(image, captured.convert("RGB"))
        mask = ImageChops.lighter(ImageChops.lighter(difference.getchannel("R"),
                                                   difference.getchannel("G")), difference.getchannel("B"))
        equal = mask.histogram()[0]
        with tempfile.TemporaryDirectory(prefix="windev-compare-") as directory:
            cropped = Path(directory) / "reference.png"
            image.save(cropped)
            scores = compare(cropped, png, diff)
        return {**scores, "exact_rgb_equal_percent": round(100 * equal / (image.width * image.height), 2),
                "reference_crop": list(crop) if crop else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preview", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--viewport", required=True, type=dimensions)
    parser.add_argument("--browser", type=Path, help="Local Chromium executable, otherwise use Playwright Chromium")
    parser.add_argument("--selector", default="#canvas")
    parser.add_argument("--expect", type=Path, help="JSON with optional present, absent and boxes expectations")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-box", type=region, metavar="X,Y,WIDTH,HEIGHT")
    args = parser.parse_args()
    if args.reference_box and not args.reference:
        parser.error("--reference-box requires --reference")
    html = args.preview.resolve(strict=True)
    expectations = json.loads(args.expect.read_text(encoding="utf-8")) if args.expect else {}
    try:
        args.out.mkdir(parents=True, exist_ok=False)
        png = args.out.resolve() / "capture.png"
        report = browser_capture(html, png, args.viewport, args.selector, args.browser, expectations)
        report["preview_sha256"] = hashlib.sha256(html.read_bytes()).hexdigest()
        report["capture_sha256"] = hashlib.sha256(png.read_bytes()).hexdigest()
        if args.reference:
            report["comparison"] = compare_aligned(args.reference, png, args.reference_box,
                                                   args.out / "comparison.png")
        (args.out / "qa.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
