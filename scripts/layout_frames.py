#!/usr/bin/env python3
"""What a window's layout needs from the decoded source that the dossier and the inspector do not give.

Measured on a WINDEV 28 project (2,335 windows) against the designer thumbnails (`<window>.wdw.cache`) and screenshots
of the running application:

1. **Tab frames.** The controls of a Tab's pane are positioned relative to the Tab's box, but WINDEV draws the pane
   below the tab strip: `pane_top` pixels lower (26 for top-tab styles, 2 for styles without a top strip; decoded by
   windev_decode.py into the Tab's fields). Without it every pane's controls sit under the strip, and screens that
   draw their own strip draw it above the Tab, over other controls. The pane captions ("[ &1 ] - Linhas") are the
   unnamed `tabs` records of the decoded window, one per pane in pane order.
2. **Edit masks.** The display mask of an edit (`MoneySystemMask`, `999 999,99`, `AAAAMMJJ`) is a decoded string of
   the edit (`display_mask`); a numeric mask means the value is drawn on the right (`h_align: Right` when unknown).
3. **Option captions.** The text WINDEV draws beside a check box is its option's caption, an unnamed `options` record
   of the decoded window ("Corta papel"), not the control's own caption ("Corta papel?" or none). A radio button has
   one record per option. Records holding a control template's path (`TPLC_Ribbon.CBOX_x`) are not captions.
4. **Window frame.** The window's text source gives its outer size and its client size (`width`, `height`,
   `widthClient`, `heightClient`); control coordinates are client-relative. Border = (width - widthClient) / 2, title
   bar = height - heightClient - 2 x border: on one project 668 windows of 2,335 had no title bar (a 3 px raised dialog
   frame and a template "title" button drawn in the client area instead), 988 a 30 px bar and a 1 px border, 543 a
   23 px bar and an 8 px resizable border. Drawing a title bar on every window cut 32 px off the untitled ones.

`enrich(layout, properties)` adds `pane_top` / `pane_captions` to each Tab, `tab_panes` ({tab path: 1-based pane})
and `pane_offset` to each control inside a pane (its `y` moved down by the offsets of every Tab it sits in), the
check boxes' option caption and the radio buttons' `option_captions`. screen_layout.py calls it when the evidence has
a decoded folder (`latest.json` → `decoded`); it can also run over generated layouts:

  python3 scripts/layout_frames.py --decoded analysis-local/decoded-… --legacy <project> src/generated/layouts/*.layout.json [--check]
"""
import argparse
import json
from pathlib import Path
import re

PATHS = ('<REPGABARIT>', 'C:\\', '.\\')
REFERENCE = re.compile(r'^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$')
DEFAULT_PANE_TOP = 26


def _texts(element):
    return [s['text'] for chunk in element.get('chunks', []) for s in chunk.get('strings', [])
            if not s['text'].startswith(PATHS) and not REFERENCE.match(s['text'])]


def tab_frames(properties):
    """{tab path: {'pane_top': n?, 'pane_captions': [...]}}; paths are window-relative and dotted."""
    elements = properties.get('elements', [])
    tabs = {}
    for element in elements:
        if element.get('owner') == 'controls' and str(element.get('type')) == '16' and element.get('name'):
            frame = tabs.setdefault('.'.join(element.get('parents', [])[1:] + [element['name']]), {'pane_captions': []})
            top = (element.get('fields') or {}).get('pane_top')
            if top is not None:
                frame['pane_top'] = top
    for element in sorted((e for e in elements if e.get('owner') == 'tabs'), key=lambda e: e.get('line', 0)):
        path = '.'.join(element.get('parents', [])[1:])
        if path in tabs:
            texts = _texts(element)
            tabs[path]['pane_captions'].append(texts[0] if texts else '')
    return tabs


NAME = re.compile(r'^(\s*)name : (\S+)\s*$')
TABS = re.compile(r'^(\s*)tabs :\s*$')
ITEM = re.compile(r'^(\s*)-\s*$')


def tab_panes_of(text):
    """{Tab name: [[names of the controls directly in pane 1], …]} of a window's text source (`.wdw`): the
    membership is plain text — `tabs :` then one `-` per pane, each with its `controls :` list."""
    lines = text.splitlines()
    result = {}
    for index, line in enumerate(lines):
        match = TABS.match(line)
        if not match:
            continue
        indent = len(match.group(1))
        owner = None
        for back in range(index - 1, max(-1, index - 400), -1):  # the Tab's own `name :` line, same indentation
            named = NAME.match(lines[back])
            if named and len(named.group(1)) == indent:
                owner = named.group(2)
                break
        if not owner:
            continue
        panes, current = [], None
        for other in lines[index + 1:]:
            if other.strip() == '':
                continue
            depth = len(other) - len(other.lstrip())
            if depth <= indent:
                break
            if depth == indent + 1 and ITEM.match(other):
                current = []
                panes.append(current)
                continue
            named = NAME.match(other)
            if named and current is not None and depth == indent + 6:
                current.append(named.group(2))
        if panes:
            result[owner] = panes
    return result


def tab_members(controls, source_text):
    """{control path: {tab path: pane}}: every control under a pane, and everything inside it by path."""
    panes = tab_panes_of(source_text) if source_text else {}
    members = {}
    for tab in (c for c in controls if c.get('kind') == 'Tab' and c['name'] in panes):
        pane_of = {name.lower(): i + 1 for i, names in enumerate(panes[tab['name']]) for name in names}
        prefix = tab['path'] + '.'
        for control in controls:
            if control['path'].startswith(prefix):
                pane = pane_of.get(control['path'][len(prefix):].split('.')[0].lower())
                if pane is not None:
                    members.setdefault(control['path'], {})[tab['path']] = pane
    return members


def option_captions(properties):
    """{control path (lower case): [option captions in source order]}."""
    found = {}
    for element in sorted((e for e in properties.get('elements', []) if e.get('owner') == 'options'),
                          key=lambda e: e.get('line', 0)):
        path = '.'.join(element.get('parents', [])[1:])
        texts = _texts(element)
        if path and texts:
            found.setdefault(path.lower(), []).append(texts[0])
    return found


NUMERIC_MASK = re.compile(r'^[-+]?[9 ,.]*9[9 ,.]*%*$')
NUMERIC_NAMES = {'MoneySystemMask', 'NumericSystemMask'}


def edit_masks(properties):
    """{edit path (lower case): its display mask} from the decoded edit's strings (`MoneySystemMask`, `999 999,99`,
    `999,99%%`, `AAAAMMJJ`…)."""
    found = {}
    for element in properties.get('elements', []):
        if element.get('owner') != 'controls' or str(element.get('type')) != '2' or not element.get('name'):
            continue
        for text in _texts(element):
            if text in NUMERIC_NAMES or NUMERIC_MASK.match(text) or text in ('UseSystemMask', 'AAAAMMJJ') or 'JJ' in text:
                found['.'.join(element.get('parents', [])[1:] + [element['name']]).lower()] = text
                break
    return found


def numeric_mask(mask):
    return bool(mask) and (mask in NUMERIC_NAMES or bool(NUMERIC_MASK.match(mask)))


WINDOW_SIZE = re.compile(r'^window :\s+name : \S+.*?^ properties :\s+(?:x : -?\d+\s+y : -?\d+\s+)?width : (\d+)\s+height : (\d+)'
                         r'\s+widthClient : (\d+)\s+heightClient : (\d+)', re.S | re.M)


def window_frame(text):
    """{'client': {width, height}, 'border': px, 'title_bar': px} of a window's text source, or None."""
    found = WINDOW_SIZE.search(text or '')
    if not found:
        return None
    width, height, client_width, client_height = map(int, found.groups())
    border = max(0, (width - client_width) // 2)
    return {'client': {'width': client_width, 'height': client_height}, 'border': border,
            'title_bar': max(0, height - client_height - 2 * border)}


def enrich(layout, properties, source_text=''):
    """Adds the Tab frames, pane membership and offsets and option captions to one layout (in place); `source_text` is
    the window's text source (`.wdw`), for the pane membership. Returns the number of changes."""
    controls = layout.get('controls', [])
    changes = 0
    frame = window_frame(source_text)
    window = layout.setdefault('window', {})
    if frame:
        flags = window.get('flags') or {}
        wanted = {**{k: v for k, v in window.items() if k not in ('client', 'border', 'title_bar')}, **frame,
                  'flags': {**flags, 'Title bar': frame['title_bar'] > 0}}
        if wanted != window:
            window.clear()
            window.update(wanted)
            changes += 1
    frames = {path.lower(): frame for path, frame in tab_frames(properties).items()}
    tabs = {}
    for control in controls:
        if control.get('kind') != 'Tab':
            continue
        tabs[control['path']] = control
        frame = frames.get(control['path'].lower())
        for key in ('pane_top', 'pane_captions'):
            if frame and frame.get(key) not in (None, []) and control.get(key) != frame[key]:
                control[key] = frame[key]
                changes += 1
    members = tab_members(controls, source_text)
    for control in controls:
        if control.get('tab_panes') is None and control['path'] in members:
            control['tab_panes'] = members[control['path']]
            changes += 1
        panes = control.get('tab_panes') or {}
        if panes and control.get('pane_offset') is None and isinstance(control.get('y'), (int, float)):
            offset = sum(tabs[tab].get('pane_top', DEFAULT_PANE_TOP) for tab in panes if tab in tabs)
            if offset:
                control['y'] += offset
                control['pane_offset'] = offset
                changes += 1
    # a numeric edit's value is drawn on the right (WINDEV's default for a numeric mask) unless an alignment is known
    masks = edit_masks(properties)
    for control in controls:
        mask = masks.get(control['path'].lower())
        if control.get('kind') == 'Edit control' and mask:
            if control.get('display_mask') != mask:
                control['display_mask'] = mask
                changes += 1
            if numeric_mask(mask) and not control.get('h_align'):
                control['h_align'] = 'Right'
                changes += 1
    options = option_captions(properties)
    for control in controls:
        captions = options.get(control['path'].lower())
        if not captions:
            continue
        if control.get('kind') == 'Check Box' and len(captions) == 1 and control.get('caption') != captions[0]:
            control['caption'] = captions[0]
            changes += 1
        elif control.get('kind') in ('RadioButton', 'Radio Button') and control.get('option_captions') != captions:
            control['option_captions'] = captions
            changes += 1
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('layouts', nargs='+', type=Path, help='layout files, or folders of *.layout.json')
    parser.add_argument('--decoded', type=Path, required=True, help='windev_decode.py output folder')
    parser.add_argument('--legacy', type=Path, help='the WINDEV project folder (window text sources, for pane membership)')
    parser.add_argument('--check', action='store_true', help='report only')
    args = parser.parse_args()
    total = files = 0
    paths = [p for given in args.layouts for p in (sorted(given.glob('*.layout.json')) if given.is_dir() else [given])]
    for path in paths:
        layout = json.loads(path.read_text(encoding='utf-8'))
        name = (layout.get('window') or {}).get('name') or path.name.split('.')[0]
        source = args.decoded / 'properties' / f'{name}.wdw.json'
        if not source.exists():
            continue
        text_path = args.legacy / f'{name}.wdw' if args.legacy else None
        text = text_path.read_bytes().decode('utf-8', errors='replace') if text_path and text_path.exists() else ''
        changes = enrich(layout, json.loads(source.read_text(encoding='utf-8')), text)
        if changes and not args.check:
            path.write_text(json.dumps(layout, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        total += changes
        files += bool(changes)
    print(f'layout frames: {total} changes in {files} layouts' + (' (check only)' if args.check else ''))


if __name__ == '__main__':
    main()
