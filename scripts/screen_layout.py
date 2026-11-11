#!/usr/bin/env python3
"""One window's visual layout as UI-ready JSON: geometry, captions, images and skin, from the evidence.

Joins the inspector's control layout (pixel positions, absolute in the window) with the dossier's parsed fields
(captions, anchoring, button types, images and their states, background images and stretching, caption widths,
table columns). The implementer generates the screen's markup from it instead of retyping captions and
coordinates, and lists the skin files to copy from the WINDEV project folder (`assets`). Fonts and colors come
from the skin template, which this does not read: see `unknown`.

From the dossier's raw control tables it also fills what the parsed fields miss: geometry of controls whose names the
tables cut (`geometry_source`), table column widths (`width_source`) and the kind of controls the inspector names
generically; it joins words the PDF wrapped ("produç ão") when the evidence attests the joined word (`diagnostics`),
and renames kinds the RAD kit spells differently (`source_kind` keeps the dossier's). What the tables do not state
stays missing and is listed in `unknown`: geometry is never invented here.
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


# Image files of the WINDEV project whose names hold spaces, keyed by the name without them; set by `layout`.
PROJECT_FILES = {}


def basename(path):
    # The dossier PDF wraps long names inside a word ("AquaBlue_Btn_Std.pn g"), so spaces are dropped, unless the
    # project folder holds a file whose real name has them ("SIXTIES TV0101.png").
    if not path:
        return None
    joined = re.sub(r'\s+', '', re.split(r'[\\/]', path)[-1])
    return PROJECT_FILES.get(joined.lower(), joined)


def geometry(item, details):
    """Source positions first; when the text source keeps them encoded (all zero or absent), the dossier's."""
    source = {key: item.get(key) for key in ('x', 'y', 'width', 'height')}
    if not any(source.values()) and any(details.get(key) for key in ('x', 'y', 'width', 'height')):
        return {key: details.get(key) for key in ('x', 'y', 'width', 'height')}
    return source


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


ANCHOR_RATES = re.compile(r'Anchor rate to right (\d+) Anchor rate bottom (\d+) Anc\. rate width (\d+) Anchor rate height (\d+)')


def anchor(raw):
    """WINDEV anchoring: which edges follow the window when it grows, and by how much (rates in thousandths).

    "Anchor Right and bottom" + "Anchor rate to right 500 …" moves the control right by half the window's growth.
    Absent lines stay unknown (the control keeps its designer position)."""
    kind = next((line[len('Anchor '):].strip() for line in raw
                 if line.startswith('Anchor ') and not line.startswith(('Anchor rate', 'Anchor to content'))), None)
    rates = next((ANCHOR_RATES.search(line) for line in raw if ANCHOR_RATES.search(line)), None)
    if kind is None and rates is None:
        return {}
    inferred = False
    if kind is None and 'Anchor' in raw and rates and int(rates[1]) < 1000 and int(rates[3]) < 1000:
        # The dossier prints a bare "Anchor" (its type drawn, not written) for fields that share the window's extra width
        # with a neighbour: reduced right and width rates only act together ("Right and width"). Inferred, not printed.
        kind, inferred = 'Right and width', True
    # Field names of the UI kit's LegacyControl (packages/ui layout.ts); rates there are percentages.
    result = {'anchoring': kind, 'anchoring_inferred': inferred or None}
    if rates:
        result['anchorRates'] = {'right': int(rates[1]) / 10, 'bottom': int(rates[2]) / 10,
                                 'width': int(rates[3]) / 10, 'height': int(rates[4]) / 10}
    return {key: value for key, value in result.items() if value is not None}


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


# The dossier's control tables: a kind title, the column headers ("X position", "Y position"…), then one row per
# control, "<name> <x> <y> <width> <height> …"; "<Kind> : <path>" names the container of the next tables; a
# "Table column" table lists "<column>" then " <width> <state> …" for the table named by the context.
CONTROL_ROW = re.compile(r'^(\S+) (-?\d+) (-?\d+) (\d+) (\d+)(?: |$)')
TABLE_CONTEXT = re.compile(r'^([A-Z][A-Za-z .()]*?) : (\S+)$')
COLUMN_ROW = re.compile(r'^\s*(\d+) (?:Read-onl|Read-on|Active|Grayed|Inactive|Invisible)\b')
# The control tables cut long names ("EDT_quantidade_pecas_inicio_pro"); a shorter row name is a whole name.
TRUNCATED_MIN = 12
# Kind names the RAD kit spells differently from the dossier; the original stays in `source_kind`.
KIND_RENAMES = {'Radio Button': 'RadioButton', 'Static': 'Caption', 'List box': 'List Box'}


def section_key(kind):
    """One key for a layout kind and the dossier table title listing it ("Static" for a Caption, "Supercontrol" for
    the inspector's generic "control")."""
    key = re.sub(r'\s+', '', kind or '').lower()
    return {'caption': 'static', 'control': 'supercontrol'}.get(key, key)


def dossier_tables(lines):
    """Control rows and table-column rows of a window's dossier text (the tables `dossier_extract` leaves raw)."""
    rows, columns, context, section = [], [], '', None
    for index, line in enumerate(lines):
        following = lines[index + 1] if index + 1 < len(lines) else ''
        match = TABLE_CONTEXT.match(line)
        if match:
            context = match[2] if match[1] != 'Window' else ''
            continue
        row = CONTROL_ROW.match(line)
        if following == 'X position' and not row:  # a kind title, or a page break repeating the headers
            section = line
            continue
        if line == 'Table column':
            section = line
            continue
        if row and section and section != 'Table column':
            rows.append({'name': row[1], 'x': int(row[2]), 'y': int(row[3]), 'width': int(row[4]),
                         'height': int(row[5]), 'kind': section, 'context': context})
            continue
        column = COLUMN_ROW.match(following)
        if section == 'Table column' and re.fullmatch(r'\S+', line) and column:
            columns.append({'name': line, 'width': int(column[1]), 'context': context})
    return rows, columns


def row_matches(name, row_name):
    return name == row_name or (len(row_name) >= TRUNCATED_MIN and name.startswith(row_name))


BOX = ('x', 'y', 'width', 'height')


def assign_rows(wanted, rows, claimed):
    """Unique assignment of (possibly truncated) dossier rows to controls {key: (name, kind)}: exact names first,
    then the longest prefix, a row only taken when no other unresolved control needs it. Returns (assigned, by_order):
    controls cut to the same prefix are matched in the table's order (sorted by full name), listed in by_order."""
    free = [index for index in range(len(rows)) if index not in claimed]
    candidates = {key: [i for i in free if row_matches(name, rows[i]['name']) and section_key(rows[i]['kind']) == kind]
                  for key, (name, kind) in wanted.items()}
    result, taken, by_order = {}, set(), set()

    def best(key):
        options = [i for i in candidates[key] if i not in taken]
        exact = [i for i in options if rows[i]['name'] == wanted[key][0]]
        if exact:
            return exact
        longest = max((len(rows[i]['name']) for i in options), default=0)
        return [i for i in options if len(rows[i]['name']) == longest]

    for lenient in (False, True):
        changed = True
        while changed:
            changed = False
            for key in candidates:
                if key in result:
                    continue
                options = best(key)
                contested = any(other != key and other not in result and set(options) & set(best(other))
                                for other in candidates)
                boxes = {tuple(rows[i][k] for k in BOX) for i in options}
                if len(options) == 1 and (not contested or lenient) or (lenient and options and len(boxes) == 1):
                    result[key] = options[0]
                    taken.add(options[0])
                    changed = True
    groups = {}
    for key in candidates:
        if key not in result and (options := best(key)):
            groups.setdefault(tuple(options), []).append(key)
    for options, keys in groups.items():
        if len(keys) == len(options):
            for key, index in zip(sorted(keys, key=lambda k: wanted[k][0]), sorted(options)):
                result[key] = index
                by_order.add(key)
    return result, by_order


def caption_width(entry, raw):
    """Edits, combos, lists: the caption is drawn left of the input box (`Inside width`)."""
    inside = raw_value(raw, 'Inside width')
    if inside and inside.isdigit() and entry.get('width') and entry.get('caption'):
        return entry['width'] - int(inside)
    return None


def repair_from_dossier(controls, lines, raws, unknown):
    """Fill what the dossier's control tables state and the parsed fields miss: kinds of controls the inspector
    names generically, geometry of controls whose names the tables cut, and table column widths."""
    rows, column_rows = dossier_tables(lines)
    exact_kinds = {}
    for row in rows:
        exact_kinds.setdefault(row['name'], set()).add(row['kind'])
    for control in controls:
        kinds = exact_kinds.get(control['name'], set())
        if control.get('kind') == 'control' and len(kinds) == 1:
            control['source_kind'], control['kind'] = 'control', next(iter(kinds))
    complete = lambda c: all(isinstance(c.get(k), (int, float)) for k in ('width', 'height'))
    claimed = set()
    for control in filter(complete, controls):
        index = next((i for i, row in enumerate(rows) if row_matches(control['name'], row['name'])
                      and all(row[k] == control.get(k) for k in BOX)), None)
        if index is not None:
            claimed.add(index)
    missing = [control for control in controls if not complete(control) and control.get('kind') != 'column']
    wanted = {control['path']: (control['name'], section_key(control.get('kind'))) for control in missing}
    found, by_order = assign_rows(wanted, rows, claimed)
    for control in missing:
        if control['path'] not in found:
            unknown.append(f'{control["path"]}: geometry not in the dossier control tables')
            continue
        control.update({k: rows[found[control['path']]][k] for k in BOX})
        control['geometry_source'] = 'dossier (row order)' if control['path'] in by_order else 'dossier'
        if control.get('caption_width') is None and (width := caption_width(control, raws.get(control['path'], []))):
            control['caption_width'] = width
    for control in controls:
        for column in control.get('columns') or []:
            if column.get('width') is not None:
                continue
            listed = [row for row in column_rows if row['context'] == control['path']]
            same = [row for row in listed if row['name'] == column['name']] or \
                   [row for row in listed if row_matches(column['name'], row['name'])]
            widths = {row['width'] for row in same}
            if len(widths) == 1:
                column['width'], column['width_source'] = widths.pop(), 'dossier'
            else:
                unknown.append(f'{column["path"]}: column width not in the dossier column tables')


WORD = re.compile(r'[^\W\d_]+')
VOCABULARIES = {}


def vocabulary(latest):
    """Word counts of the evidence: the dossier text and the inspected source code (identifiers left out)."""
    key = (latest.get('dossier'), latest.get('inspect'))
    if key not in VOCABULARIES:
        counts = Counter()

        def add(text):
            counts.update(token.lower() for token in re.findall(r'\w+', text) if WORD.fullmatch(token))
        if latest.get('dossier') and Path(latest['dossier']).is_dir():
            for path in sorted(Path(latest['dossier']).rglob('*.json')):
                data = load(path)
                if isinstance(data, dict):
                    add('\n'.join(line for line in data.get('lines', []) if isinstance(line, str)))
        if latest.get('inspect') and Path(latest['inspect'], 'code').is_dir():
            for path in sorted(Path(latest['inspect'], 'code').rglob('*.json')):
                data = load(path)
                for block in data.get('blocks', []) if isinstance(data, dict) else []:
                    if isinstance(block, dict) and isinstance(block.get('code'), str):
                        add(block['code'])
        VOCABULARIES[key] = counts
    return VOCABULARIES[key]


WRAPPED = re.compile(r'([^\W\d_]+) (?=([^\W\d_]+))')


def join_wrapped(text, words, known=3):
    """The dossier PDF wraps long texts inside a word ("produç ão"). Join two fragments when the joined word occurs
    in the evidence, the right one continues in lower case, and one of them is not a word of its own (seen fewer
    than `known` times)."""
    if not isinstance(text, str):
        return text

    def fix(match):
        left, right = match[1], match[2]
        if right[0].islower() and words.get((left + right).lower(), 0) >= 1 and \
                min(words.get(left.lower(), 0), words.get(right.lower(), 0)) < known:
            return left
        return match[0]
    previous = None
    while previous != text:
        previous, text = text, WRAPPED.sub(fix, text)
    return text


UNIT_FILES = {}  # inspect folder -> {unit name, lower case: [files]}


def layout(unit, latest, language=None):
    inspect, dossier = Path(latest['inspect']), latest.get('dossier')
    if not PROJECT_FILES and latest.get('legacy') and Path(latest['legacy']).is_dir():
        PROJECT_FILES.update({re.sub(r'\s+', '', file.name).lower(): file.name for file in Path(latest['legacy']).rglob('*')
                              if ' ' in file.name and file.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico')})
    # Which file holds which unit, read once per inspect folder: reading every file again for each unit made a
    # project of a few thousand windows take hours (readiness_report.py asks for every layout).
    if inspect not in UNIT_FILES:
        UNIT_FILES[inspect] = index = {}
        for path in sorted((inspect / 'code').rglob('*.json')):
            index.setdefault(load(path).get('name', '').lower(), []).append(path)
    matches = [load(path) for path in UNIT_FILES[inspect].get(unit.lower(), [])]
    if not matches:
        raise SystemExit(f'{unit}: not in {inspect}')
    if len(matches) != 1:
        raise ValueError(f'{unit}: ambiguous inspected unit')
    source = matches[0]
    element = load(Path(dossier, 'windev-window', f'{unit}.json')) if dossier else {}
    described = element.get('controls', {})
    controls, columns, assets, unknown, diagnostics, raws = [], [], set(), [], [], {}
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
                 **geometry(item, details),
                 'caption': choose(details.get('caption') or details.get('title'), f'{path}.caption'),
                 'visible': (details.get('flags') or {}).get('Visible'), 'flags': details.get('flags'), 'state': details.get('state'),
                 'plane': details.get('plane'), 'tab_order': details.get('tab_order'),
                 'anchoring': details.get('anchoring'), **anchor(raw),
                 'button_type': details.get('button_type'),
                 'h_align': details.get('h_align') or raw_value(raw, 'Horz. alignment') or caption_alignment.get('h_align'),
                 'input_mask': choose(details.get('input_mask'), f'{path}.input_mask'),
                 'input_size': details.get('input_size'), 'input_type': details.get('input_type'), 'image': image,
                 'image_states': raw_value(raw, 'Nb. image states'),
                 'background_image': background, 'background_states': raw_value(raw, 'Nb. background states'),
                 'background_stretch': raw_value(raw, 'Stretch background image'),
                 # Read from the source: the skin style the control was created from (`170 AquaBlue.BTN_Ok`), and
                 # its frames (border type, background and border colours) in file order.
                 'style': details.get('style'), 'frames': details.get('frames'),
                 'differs_from_style': details.get('differs_from_style')}
        if entry['kind'] == 'Caption':
            entry['v_align'] = details.get('v_align') or raw_value(raw, 'Vert. alignment') or caption_alignment.get('v_align')
        entry.update(date_edit_options(details))
        if entry['kind'] == 'Table':
            entry['table_options'] = table_options(raw)
        entry['caption_width'] = caption_width(entry, raw)
        raws[path] = raw
        entry['displayed_item'] = details.get('displayed_item')
        if details.get('fonts'):
            # Read from the source: the first font is the control's own (a button repeats it per state); the others
            # are kept in order, their role (caption, input area, states) is not named.
            entry['font'], entry['fonts'] = details['fonts'][0], details['fonts']
        if item['kind'] == 'column':
            columns.append({'name': item['name'], 'path': path, 'parent': parent,
                                     # The source's own width first (read in file order, so right for columns
                                     # that share a name across tables); the dossier's otherwise.
                                     'title': entry['caption'], 'width': item.get('width') or details.get('width'),
                                     **({'width_source': 'source'} if item.get('width') else {}),
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
    if element:
        repair_from_dossier(controls, element.get('lines', []), raws, unknown)
        words = vocabulary(latest)

        def unwrap(holder, key, where):
            if isinstance(holder.get(key), str) and (joined := join_wrapped(holder[key], words)) != holder[key]:
                diagnostics.append(f'{where}: PDF-wrapped word joined (dossier text {holder[key]!r})')
                holder[key] = joined
        for control in controls:
            for key in ('caption', 'title'):
                unwrap(control, key, f'{control["path"]}.{key}')
            for column in control.get('columns') or []:
                unwrap(column, 'title', f'{column["path"]}.title')
    for control in controls:
        if control.get('kind') in KIND_RENAMES:
            control.setdefault('source_kind', control['kind'])
            control['kind'] = KIND_RENAMES[control['kind']]
    window = {'name': unit, 'title': choose(element.get('title'), 'window.title'), 'size': element.get('size') or source_size,
              'opening_mode': element.get('opening_mode'), 'window_type': element.get('window_type'),
              # The source's own value first (exact path), the dossier's line otherwise.
              'background_image': basename(choose(element.get('background_image'), 'window.background_image')
                                           or (raw_value(element.get('lines', []), 'Background image') or '').split(': ', 1)[-1]) or None,
              'flags': element.get('flags', {})}
    if element:
        unwrap(window, 'title', 'window.title')
    if window['background_image']:
        assets.add(window['background_image'])
    if not element:
        unknown.append('no dossier entry: captions, images and skin unknown')
    if not any(control.get('font') or control.get('fonts') for control in controls):
        unknown.append('fonts, font sizes and colors: not in this evidence (run windev_decode.py, or read them from the dossier image)')
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
