#!/usr/bin/env python3
"""Copy the skin images screens use from the WINDEV project folder, as PNG, one file per state.

WINDEV draws buttons and window chrome from image strips: `Nb. image states 5` means the strip holds five
side-by-side states (normal, hover, pressed, focused, disabled). For each asset named in screen_layout.py
outputs, this writes `<out>/<name>.png` and, for strips, `<out>/<name>.<state>.png` (0 = normal), so the new
UI can use them as CSS backgrounds or 9-slice `border-image`. Pure magenta, the skins' transparent color,
becomes transparent. Requires Pillow. The images are the project's
own resources: copy only into the application repository.
"""
import argparse
import json
from pathlib import Path


def states_by_asset(layouts):
    states = {}
    for layout in layouts:
        for control in layout['controls']:
            for image, count in ((control.get('image'), control.get('image_states')),
                                 (control.get('background_image'), control.get('background_states'))):
                if image and count and str(count).isdigit():
                    states[image] = max(states.get(image, 1), int(count))
    return states


def magenta_to_transparent(image):
    """WINDEV skins mark transparent pixels with pure magenta (255, 0, 255)."""
    image.putdata([(r, g, b, 0) if (r, g, b) == (255, 0, 255) else (r, g, b, a) for r, g, b, a in image.getdata()])
    return image


def export(layouts, project, out):
    from PIL import Image
    out.mkdir(parents=True, exist_ok=True)
    files = {p.name.lower(): p for p in Path(project).rglob('*') if p.suffix.lower() in ('.gif', '.png', '.jpg', '.bmp')}
    states = states_by_asset(layouts)
    written, missing = [], []
    for asset in sorted({a for layout in layouts for a in layout['assets']}):
        source = files.get(asset.lower())
        if source is None:
            missing.append(asset)
            continue
        image = magenta_to_transparent(Image.open(source).convert('RGBA'))
        stem = Path(asset).stem
        image.save(out / f'{stem}.png')
        written.append(f'{stem}.png')
        count = states.get(asset, 1)
        if count > 1 and image.width % count == 0:
            width = image.width // count
            for state in range(count):
                image.crop((state * width, 0, (state + 1) * width, image.height)).save(out / f'{stem}.{state}.png')
                written.append(f'{stem}.{state}.png')
    return {'written': written, 'missing': missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('layouts', nargs='+', type=Path, help='screen_layout.py outputs')
    parser.add_argument('--project', type=Path, default=Path('legacy'),
                        help="where the project's images and skin template are, searched recursively (default legacy/)")
    parser.add_argument('--out', type=Path, required=True, help='e.g. public/skin')
    args = parser.parse_args()
    layouts = [json.loads(p.read_text(encoding='utf-8')) for p in args.layouts]
    result = export(layouts, args.project, args.out)
    print(json.dumps({'written': len(result['written']), 'missing': result['missing']}, indent=1))
    if result['missing']:  # a missing image renders as a blank in the new screen: copy it into legacy/images/
        raise SystemExit(f"{len(result['missing'])} images not found under {args.project}")


if __name__ == '__main__':
    main()
