#!/usr/bin/env python3
"""Draw every legacy window to scale from the inspector's control layout (no WINDEV, no app run).

Each control becomes a labelled rectangle at its source position. Captions come from the
dossier extract (dossier_extract.py) when given; otherwise the legacy control name is shown. Output: one SVG per window plus an index.html gallery.
"""
import argparse
from html import escape
import json
from pathlib import Path

COLORS = {'BTN': '#d6e4ff', 'EDT': '#ffffff', 'TABLE': '#f3f3f3', 'COL': '#ececec', 'COMBO': '#fff7d6',
          'STC': 'none', 'CBOX': '#e8f5e9', 'IMG': '#f3e5f5', 'SC': 'none', 'TAB': 'none', 'LAYOUT': 'none'}


def captions_from_dossier(dossier_dir, language=None):
    """{window: {legacy control name: caption}} from dossier_extract.py output."""
    captions = {}
    if not dossier_dir:
        return captions
    for path in Path(dossier_dir, 'windev-window').glob('*.json'):
        for name, control in json.loads(path.read_text(encoding='utf-8')).get('controls', {}).items():
            caption = control.get('caption') or control.get('title')  # table columns have a title
            if isinstance(caption, dict):  # {"PT": "Cancelar", "GB": "Cancel"}: the requested language, else the first
                caption = caption.get(language) or next(iter(caption.values()), None)
            if caption:
                captions.setdefault(path.stem, {})[name] = caption
    return captions


def svg(window, layout, captions):
    items = [i for i in layout if i.get('width') and i.get('height') and i['kind'] == 'control']
    if not items or any(i['kind'] == 'band' for i in layout):  # reports: band-relative millimetres, not a screen
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


def render(inspect_dir, out, dossier_dir=None, language=None):
    out.mkdir(parents=True, exist_ok=True)
    captions = captions_from_dossier(dossier_dir, language)
    rendered = []
    for path in sorted(Path(inspect_dir, 'code').rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        window = data.get('name') or Path(data['path']).stem
        drawing = svg(window, data.get('layout', []), captions.get(window, {}))
        if drawing:
            (out / f'{window}.svg').write_text(drawing, encoding='utf-8')
            rendered.append((window, window in captions))
    cards = ''.join(f'<figure><figcaption>{escape(w)}{" — captions from the dossier" if c else ""}</figcaption>'
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
    parser.add_argument('--dossier', type=Path, help='dossier_extract.py output, for the real captions')
    parser.add_argument('--language', help='caption language in the dossier (PT, GB…); default: the first given')
    args = parser.parse_args()
    rendered = render(args.inspect_dir, args.out, args.dossier, args.language)
    print(f'{len(rendered)} windows rendered, {sum(1 for _, c in rendered if c)} with dossier captions')


if __name__ == '__main__':
    main()
