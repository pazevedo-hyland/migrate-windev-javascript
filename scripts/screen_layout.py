#!/usr/bin/env python3
"""One window's visual layout as UI-ready JSON: geometry, captions, images and skin, from the evidence.

Joins the inspector's control layout (pixel positions, absolute in the window) with the dossier's parsed fields
(captions, anchoring, button types, images and their states, background images and stretching, caption widths,
table columns). The implementer generates the screen's markup from it instead of retyping captions and
coordinates, and lists the skin files to copy from the WINDEV project folder (`assets`). Fonts and colors come
from the skin template, which this does not read: see `unknown`.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path, PureWindowsPath
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


def table_options(raw):
    """Retain named literal table details; absent properties stay unknown."""
    names = {
        'magnifier_mode': 'Magnifier mode', 'horizontal_scrollbar': 'Horz. scrollbar',
        'vertical_scrollbar': 'Vert. scrollbar', 'truncated_tooltip': 'Tooltip when truncated',
        'pixel_scrolling': 'Per-pixel scrolling', 'touch_scrolling': 'Touch scrolling',
        'column_context_menu': 'Column context menu', 'context_menu': 'Context menu mode.',
        'remember_filters': 'Remember filters', 'remember_sorts': 'Remember sorts',
        'row_height': 'Row height (without margin)', 'selection_mode': 'Selection mode',
        'column_selection': 'Select. columns', 'cell_selection': 'Select. cells',
    }
    return {key: value for key, name in names.items() if (value := raw_value(raw, name)) is not None}


def caption_summary_alignment(details):
    """Use only complete literal caption summaries, with neither missing axis inferred."""
    if details.get('kind') != 'Caption':
        return {}
    summary = re.fullmatch(r'(?:Active|Read-only|Read-onl|Grayed|Inactive) '
                           r'(Left|Right|Center|Justified) (Top|Center|Bottom)', details.get('row') or '')
    return {'h_align': summary[1], 'v_align': summary[2]} if summary else {}


def date_edit_options(details):
    """Keep named date details literal; display masks do not establish return formats."""
    if details.get('kind') != 'Edit control' or details.get('input_type') != 'Date':
        return {}
    names = {'return_format': 'Return format', 'calendar_button': 'Calendar button',
             'calculator_button': 'Calculator button', 'blocking_validation': 'Blocking validation'}
    return {key: value for key, name in names.items()
            if (value := raw_value(details.get('raw', []), name)) is not None}


def source_context(source, latest):
    """Read scoped identities from an available text source; never guess duplicate leaf ownership.

    Old inspector outputs have no paths. Without the private source, caller-supplied qualified
    paths are retained; missing identities stay unresolved instead of borrowing another column.
    """
    identities, size = [], None
    source_path = None
    if source.get('path') is not None:
        raw_path = source['path']
        if not isinstance(raw_path, str):
            raise ValueError('Window source path must be relative text')
        relative = Path(raw_path.replace('\\', '/'))
        windows_path = PureWindowsPath(raw_path)
        if relative.is_absolute() or windows_path.drive or windows_path.root or '..' in relative.parts:
            raise ValueError('Window source path must stay inside the legacy root')
        if relative.suffix.lower() != '.wdw':
            raise ValueError('Window layout requires a .wdw source')
        if latest.get('legacy'):
            legacy_root = Path(latest['legacy']).resolve()
            candidate = legacy_root
            for part in relative.parts:
                candidate = candidate / part
                if candidate.is_symlink():
                    raise ValueError('Window source symlinks are refused')
            source_path = candidate.resolve()
            if not source_path.is_relative_to(legacy_root):
                raise ValueError('Window source path escapes the legacy root')
    if source_path and source_path.is_file():
        spec = importlib.util.spec_from_file_location('layout_inspector', Path(__file__).with_name('inspect_windev.py'))
        inspector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inspector)
        text = inspector.decode_text(source_path.read_bytes(), latest.get('fallback_encoding'))
        if text is not None:
            parsed = inspector.structure(text.splitlines(), inspector.literal_mask(text.splitlines()))
            stack = []
            for index, entry in enumerate(parsed):
                if not entry or entry[1] != 'name' or not entry[2]:
                    continue
                parent = next((parsed[j] for j in range(index - 1, -1, -1)
                               if parsed[j] and parsed[j][0] < entry[0]), None)
                if not parent or parent[1] not in ('controls', 'columns', 'blocks'):
                    continue
                while stack and stack[-1][0] >= entry[0]:
                    stack.pop()
                names = [name for _, name in stack]
                identities.append({'name': entry[2], 'path': '.'.join([*names, entry[2]]),
                                   'parent': '.'.join(names), 'line': index + 1})
                stack.append((entry[0], entry[2]))
            entries = [entry for entry in parsed if entry]
            start = next((index for index, entry in enumerate(entries) if entry[0] == 0 and entry[1] == 'window'), None)
            if start is not None:
                properties, dimensions = False, {}
                for indent, key, value, *_ in entries[start + 1:]:
                    if indent == 0:
                        break
                    if indent == 1:
                        properties = key == 'properties'
                    elif properties and indent == 2 and key in ('width', 'height') and str(value).isdigit():
                        dimensions[key] = int(value)
                if all(dimensions.get(key, 0) > 0 for key in ('width', 'height')):
                    size = dimensions
            if [item['name'] for item in identities] != [item['name'] for item in source.get('layout', [])]:
                raise ValueError('Source hierarchy differs from inspected layout; refresh the inspector output')
    return identities, size


def layout(unit, latest, language=None):
    inspect, dossier = Path(latest['inspect']), latest.get('dossier')
    matches = [s for s in (load(p) for p in sorted((inspect / 'code').rglob('*.json')))
               if s.get('name', '').lower() == unit.lower()]
    if not matches:
        raise SystemExit(f'{unit}: not in {inspect}')
    if len(matches) != 1:
        raise ValueError(f'{unit}: ambiguous inspected unit')
    source = matches[0]
    element = load(Path(dossier, 'windev-window', f'{unit}.json')) if dossier else {}
    described = element.get('controls', {})
    controls, columns, assets, unknown, diagnostics = [], [], set(), [], []
    identities, source_size = source_context(source, latest)
    repeated = {name for name, count in Counter(item['name'] for item in source.get('layout', [])).items() if count > 1}

    def choose(value, context):
        if isinstance(value, dict) and value:
            selected = language if language in value else sorted(value)[0]
            if language != selected:
                diagnostics.append(f'{context}: language {language or "unspecified"} unavailable; preview uses {selected}')
            return value[selected]
        return pick(value, language)

    for index, item in enumerate(source.get('layout', [])):
        identity = identities[index] if identities else {'name': item['name'], 'path': item.get('path'), 'parent': item.get('parent')}
        details = described.get(identity.get('path')) or described.get(item['name']) or {}
        if item['name'] in repeated:
            # A merged leaf entry cannot establish which repeated column it describes.
            details = described.get(identity.get('path')) or {}
            if not details:
                unknown.append(f'{identity.get("path") or item["name"]}: duplicate leaf metadata unresolved')
        path = identity.get('path') or details.get('path') or item['name']
        parent = identity.get('parent') or (path.rsplit('.', 1)[0] if '.' in path else '')
        raw = details.get('raw', [])
        caption_alignment = caption_summary_alignment(details)
        image = basename(choose(details.get('image'), f'{path}.image'))
        if not image and details.get('kind') == 'Image':
            image = basename(choose(details.get('initial_value'), f'{path}.initial_value'))
        background = basename(choose(details.get('background_image'), f'{path}.background_image'))
        assets.update(a for a in (image, background) if a)
        entry = {'name': item['name'], 'path': path, 'kind': details.get('kind') or item['kind'],
                 'x': item['x'], 'y': item['y'], 'width': item.get('width'), 'height': item.get('height'),
                 'caption': choose(details.get('caption') or details.get('title'), f'{path}.caption'),
                 'visible': (details.get('flags') or {}).get('Visible'), 'flags': details.get('flags'), 'state': details.get('state'),
                 'anchoring': details.get('anchoring'), 'tab_order': details.get('tab_order'),
                 'button_type': details.get('button_type'),
                 'h_align': details.get('h_align') or raw_value(raw, 'Horz. alignment') or caption_alignment.get('h_align'),
                 'input_mask': choose(details.get('input_mask'), f'{path}.input_mask'),
                 'input_size': details.get('input_size'), 'input_type': details.get('input_type'), 'image': image,
                 'image_states': raw_value(raw, 'Nb. image states'),
                 'background_image': background, 'background_states': raw_value(raw, 'Nb. background states'),
                 'background_stretch': raw_value(raw, 'Stretch background image')}
        if entry['kind'] == 'Caption':
            entry['v_align'] = details.get('v_align') or raw_value(raw, 'Vert. alignment') or caption_alignment.get('v_align')
        entry.update(date_edit_options(details))
        if entry['kind'] == 'Table':
            entry['table_options'] = table_options(raw)
        inside = raw_value(raw, 'Inside width')
        if inside and inside.isdigit() and entry['width'] and entry['caption']:
            # Edits, combos, lists: the caption is drawn left of the input box, which is the last `Inside width`.
            entry['caption_width'] = entry['width'] - int(inside)
        entry['displayed_item'] = details.get('displayed_item')
        if item['kind'] == 'column':
            columns.append({'name': item['name'], 'path': path, 'parent': parent,
                                     'title': entry['caption'], 'width': details.get('width'),
                                     'h_align': details.get('h_align'), 'input_type': details.get('input_type'),
                                     'linked_item': details.get('linked_item'), 'index': details.get('column_index'),
                                     'flags': details.get('flags'),
                                     'metadata_unresolved': item['name'] in repeated and not details})
            continue
        controls.append({k: v for k, v in entry.items() if v is not None})
    for control in controls:
        if control['kind'] == 'Table':
            control['columns'] = sorted((column for column in columns if column['parent'] == control['path']), key=lambda c: c['index'] or 0)
    attached = {id(column) for control in controls for column in control.get('columns', [])}
    for column in columns:
        if id(column) not in attached:
            unknown.append(f'{column["path"]}: column parent unknown; retained as unresolved control')
            controls.append({**column, 'kind': 'column', 'metadata_unresolved': True})
    window = {'name': unit, 'title': choose(element.get('title'), 'window.title'), 'size': element.get('size') or source_size,
              'opening_mode': element.get('opening_mode'), 'window_type': element.get('window_type'),
              'background_image': basename((raw_value(element.get('lines', []), 'Background image') or '').split(': ', 1)[-1]) or None,
              'flags': element.get('flags', {})}
    if window['background_image']:
        assets.add(window['background_image'])
    if not element:
        unknown.append('no dossier entry: captions, images and skin unknown')
    unknown.append('fonts, font sizes and colors: from the skin template (.sty), not extracted — read them from the dossier image')
    return {'format_version': 1, 'window': window, 'controls': controls, 'assets': sorted(assets),
            'unknown': sorted(set(unknown)), 'diagnostics': sorted(set(diagnostics)),
            'source': source.get('path'), 'language': language,
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
