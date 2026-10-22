#!/usr/bin/env python3
"""Draw every legacy window to scale from the inspector's control layout (no WINDEV, no app run).

Each control becomes a labelled rectangle at its source position. Captions come from capture-kit
`tree.json` files when available (elements labelled with `legacy_name`); otherwise the legacy
control name is shown. Output: one SVG per window plus an index.html gallery.
"""
import argparse
from html import escape
import json
from pathlib import Path

COLORS = {'BTN': '#d6e4ff', 'EDT': '#ffffff', 'TABLE': '#f3f3f3', 'COL': '#ececec', 'COMBO': '#fff7d6',
          'STC': 'none', 'CBOX': '#e8f5e9', 'IMG': '#f3e5f5', 'SC': 'none', 'TAB': 'none', 'LAYOUT': 'none'}


def captions_from_captures(capture_dir):
    """{window: {legacy control name: caption}} from capture-kit tree.json files."""
    captions = {}
    if not capture_dir:
        return captions
    for tree in Path(capture_dir).rglob('tree.json'):
        window = tree.parent.name
        for element in json.loads(tree.read_text(encoding='utf-8')):
            if element.get('legacy_name') and element.get('name'):
                captions.setdefault(window, {})[element['legacy_name']] = element['name']
    return captions


def svg(window, layout, captions):
    items = [i for i in layout if i.get('width') and i.get('height') and i['kind'] == 'control']
    if not items:
        return None
    width = max(i['x'] + i['width'] for i in items) + 10
    height = max(i['y'] + i['height'] for i in items) + 10
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="10">',
             f'<rect width="{width}" height="{height}" fill="#fafafa" stroke="#999"/>']
    # Containers first, so the controls inside stay visible.
    for item in sorted(items, key=lambda i: -(i['width'] * i['height'])):
        prefix = item['name'].split('_')[0].upper()
        fill = COLORS.get(prefix, '#ffffff')
        label = captions.get(item['name'], item['name'])
        parts.append(f'<g><title>{escape(item["name"])} ({item["x"]},{item["y"]} {item["width"]}×{item["height"]})</title>'
                     f'<rect x="{item["x"]}" y="{item["y"]}" width="{item["width"]}" height="{item["height"]}" '
                     f'fill="{fill}" stroke="#6b7280" stroke-dasharray="{"3,2" if fill == "none" else "0"}"/>'
                     f'<text x="{item["x"] + 3}" y="{item["y"] + 12}" fill="#111">{escape(label)}</text></g>')
    parts.append('</svg>')
    return '\n'.join(parts)


def render(inspect_dir, out, capture_dir=None):
    out.mkdir(parents=True, exist_ok=True)
    captions = captions_from_captures(capture_dir)
    rendered = []
    for path in sorted(Path(inspect_dir, 'code').rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        window = Path(data['path']).stem
        drawing = svg(window, data.get('layout', []), captions.get(window, {}))
        if drawing:
            (out / f'{window}.svg').write_text(drawing, encoding='utf-8')
            rendered.append((window, window in captions))
    cards = ''.join(f'<figure><figcaption>{escape(w)}{" — captions from capture" if c else ""}</figcaption>'
                    f'<img src="{escape(w)}.svg"></figure>' for w, c in rendered)
    (out / 'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>Legacy layouts</title><style>body{font-family:sans-serif}'
        'figure{display:inline-block;margin:12px;vertical-align:top}img{border:1px solid #ccc;max-width:720px}'
        '</style>' + cards, encoding='utf-8')
    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inspect_dir', type=Path, help='inspect_windev.py output directory')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--captures', type=Path, help='capture-kit output (tree.json files) for real captions')
    args = parser.parse_args()
    rendered = render(args.inspect_dir, args.out, args.captures)
    print(f'{len(rendered)} windows rendered, {sum(1 for _, c in rendered if c)} with captured captions')


if __name__ == '__main__':
    main()
