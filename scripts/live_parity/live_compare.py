"""Our running app (the migrated app: {layout, client: {width, height}, controls: [{path, x, y, width, height, text}]}, boxes relative to the client area) against a running WINDEV application (windev_live_capture.py json), control by control.

Pairing: a live control with a caption is paired with the control our app drew with the same text; without one
(edits, combos), through the generated layout (same caption in the layout, nearest designer box) and our control of
that path. Among candidates the closest box wins. Each axis is compared from both sides (left edge and distance to the
right edge; top edge and distance to the bottom edge), so windows of different sizes compare: a control matches when
each axis lines up from one side within 1 px and its size within 1 px.

  py -3 scripts/live_parity/live_compare.py <live.json> <ours.json> [--json]
"""
import glob
import json
import re
import sys

KIND = {'Button': 'Button', 'Edit': 'Edit control', 'ComboBox': 'Combo Box', 'CheckBox': 'Check Box',
        'RadioButton': 'RadioButton', 'Text': 'Caption', 'List': 'List Box'}
TOLERANCE = 1
# the migrated project's generated layouts (pairing of controls without a caption through their designer box)
LAYOUTS = 'src/generated/layouts/*.json'


def text(value):
    return re.sub(r'\s+', ' ', (value or '').replace('&', '')).strip().lower()


def offsets(mine, item, ours_client, live_client):
    left, top = mine['x'] - item['x'], mine['y'] - item['y']
    right = (ours_client['width'] - mine['x'] - mine['width']) - (live_client['width'] - item['x'] - item['width'])
    bottom = (ours_client['height'] - mine['y'] - mine['height']) - (live_client['height'] - item['y'] - item['height'])
    return {'x': min(left, right, key=abs), 'y': min(top, bottom, key=abs),
            'width': mine['width'] - item['width'], 'height': mine['height'] - item['height']}


def compare(live, ours):
    layout_file = next((f for f in glob.glob(LAYOUTS)
                        if f.replace('\\', '/').split('/')[-1].startswith((ours.get('layout') or '?') + '-')), None)
    layout = json.load(open(layout_file, encoding='utf-8'))['controls'] if layout_file else []
    by_path = {c['path']: c for c in ours['controls']}
    by_text = {}
    for c in ours['controls']:
        by_text.setdefault(text(c.get('text')), []).append(c)
    rows = {'match': [], 'differ': [], 'missing': []}
    used = set()
    for item in live['controls']:
        if item['level'] == 0 or not item['visible'] or item['type'] not in KIND or item['width'] <= 0:
            continue
        name = text(item['name'])
        candidates = [c for c in by_text.get(name, []) if c['path'] not in used] if name else []
        if not candidates:
            designed = [c for c in layout if text(c.get('caption')) == name and isinstance(c.get('x'), (int, float))] if name else []
            if designed:
                best = min(designed, key=lambda c: abs(c['x'] - item['x']) + abs(c['y'] - item['y']))
                if best['path'] in by_path and best['path'] not in used:
                    candidates = [by_path[best['path']]]
                elif best['path'] not in by_path:
                    rows['missing'].append({'path': best['path'], 'caption': item['name'], 'live': [item['x'], item['y']]})
                    continue
        if not candidates:
            continue
        cost, mine = min(((sum(abs(v) for v in offsets(c, item, ours['client'], live['client']).values()), c)
                          for c in candidates), key=lambda pair: pair[0])
        used.add(mine['path'])
        delta = offsets(mine, item, ours['client'], live['client'])
        row = {'path': mine['path'], 'caption': item['name'], 'delta': delta}
        rows['match' if all(abs(v) <= TOLERANCE for v in delta.values()) else 'differ'].append(row)
    return rows


def main():
    live = json.load(open(sys.argv[1], encoding='utf-8'))
    ours = json.load(open(sys.argv[2], encoding='utf-8'))
    rows = compare(live, ours)
    if '--json' in sys.argv:
        print(json.dumps(rows, ensure_ascii=False))
        return
    print(f"{ours['layout']}: {len(rows['match'])} at the live place (±{TOLERANCE} px), {len(rows['differ'])} elsewhere, "
          f"{len(rows['missing'])} not drawn by us")
    for row in rows['differ']:
        print('  differ', row['path'], row['delta'])
    for row in rows['missing']:
        print('  not drawn', row['path'], repr(row['caption']))


if __name__ == '__main__':
    main()
