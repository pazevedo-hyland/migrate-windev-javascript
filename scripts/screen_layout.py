#!/usr/bin/env python3
"""One window's visual layout as UI-ready JSON: geometry, captions, images and skin, from the evidence.

Joins the inspector's control layout (pixel positions, absolute in the window) with the dossier's parsed fields
(captions, anchoring, button types, images and their states, background images and stretching, caption widths,
table columns). The implementer generates the screen's markup from it instead of retyping captions and
coordinates, and lists the skin files to copy from the WINDEV project folder (`assets`). Fonts and colors come
from the skin template, which this does not read: see `unknown`.
"""
import argparse
import json
from pathlib import Path
import re


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if path and Path(path).exists() else {}


def pick(value, language):
    if isinstance(value, dict):
        return value.get(language) or next(iter(value.values()), None)
    return value


def raw_value(raw, key):
    """The value of a dossier detail line "Key value" (raw lines keep what the parser does not name)."""
    for line in raw:
        if line.startswith(key + ' '):
            return line[len(key) + 1:].strip()
    return None


def basename(path):
    return re.split(r'[\\/]', path)[-1] if path else None


def layout(unit, latest, language=None):
    inspect, dossier = Path(latest['inspect']), latest.get('dossier')
    source = next((s for s in (load(p) for p in (inspect / 'code').rglob('*.json'))
                   if s.get('name', '').lower() == unit.lower()), None)
    if source is None:
        raise SystemExit(f'{unit}: not in {inspect}')
    element = load(Path(dossier, 'windev-window', f'{unit}.json')) if dossier else {}
    described = element.get('controls', {})
    controls, columns, assets, unknown = [], {}, set(), []
    for item in source.get('layout', []):
        details = described.get(item['name']) or {}
        raw = details.get('raw', [])
        image = basename(pick(details.get('image'), language))
        background = basename(pick(details.get('background_image'), language))
        assets.update(a for a in (image, background) if a)
        entry = {'name': item['name'], 'kind': details.get('kind') or item['kind'],
                 'x': item['x'], 'y': item['y'], 'width': item.get('width'), 'height': item.get('height'),
                 'caption': pick(details.get('caption') or details.get('title'), language),
                 'visible': (details.get('flags') or {}).get('Visible', True), 'state': details.get('state'),
                 'anchoring': details.get('anchoring'), 'tab_order': details.get('tab_order'),
                 'button_type': details.get('button_type'), 'h_align': details.get('h_align') or raw_value(raw, 'Horz. alignment'),
                 'input_mask': pick(details.get('input_mask'), language), 'image': image,
                 'image_states': raw_value(raw, 'Nb. image states'),
                 'background_image': background, 'background_states': raw_value(raw, 'Nb. background states'),
                 'background_stretch': raw_value(raw, 'Stretch background image')}
        inside = raw_value(raw, 'Inside width')
        if inside and inside.isdigit() and entry['width'] and entry['caption']:
            # Edits, combos, lists: the caption is drawn left of the input box, which is the last `Inside width`.
            entry['caption_width'] = entry['width'] - int(inside)
        entry['displayed_item'] = details.get('displayed_item')
        if item['kind'] == 'column':
            columns[item['name']] = {'name': item['name'], 'title': entry['caption'], 'width': details.get('width'),
                                     'h_align': details.get('h_align'), 'input_type': details.get('input_type'),
                                     'linked_item': details.get('linked_item'), 'index': details.get('column_index'),
                                     'flags': details.get('flags')}
            continue
        controls.append({k: v for k, v in entry.items() if v is not None})
    for control in controls:
        if control['kind'] == 'Table':
            names = [n for n, c in columns.items() if (described.get(n) or {}).get('path', '').startswith(control['name'] + '.')]
            control['columns'] = sorted((columns[n] for n in names), key=lambda c: c['index'] or 0)
    window = {'name': unit, 'title': pick(element.get('title'), language), 'size': element.get('size'),
              'opening_mode': element.get('opening_mode'), 'window_type': element.get('window_type'),
              'background_image': basename((raw_value(element.get('lines', []), 'Background image') or '').split(': ', 1)[-1]) or None,
              'flags': element.get('flags', {})}
    if window['background_image']:
        assets.add(window['background_image'])
    if not element:
        unknown.append('no dossier entry: captions, images and skin unknown')
    unknown.append('fonts, font sizes and colors: from the skin template (.sty), not extracted — read them from the dossier image')
    return {'window': window, 'controls': controls, 'assets': sorted(assets), 'unknown': unknown,
            'image': f'docs/evidence/images/{unit}.jpg'}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('unit', help='window name, e.g. WIN_Table_Clientes')
    parser.add_argument('--latest', type=Path, default=Path('analysis-local/latest.json'))
    parser.add_argument('--language', help='caption language (PT, GB…); default: the first given')
    parser.add_argument('--out', type=Path, help='default: stdout (e.g. src/ui/legacy/<unit>.layout.json)')
    args = parser.parse_args()
    text = json.dumps(layout(args.unit, load(args.latest), args.language), indent=1, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + '\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
