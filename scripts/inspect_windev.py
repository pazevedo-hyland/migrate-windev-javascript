#!/usr/bin/env python3
"""Inspect WINDEV text sources and raw XDD metadata; never execute legacy code."""
import argparse
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

EXTENSIONS = {'.wdp', '.wdw', '.wde', '.wdr', '.wdg', '.wdc', '.xdd'}
KINDS = {'.wdp': 'project', '.wdw': 'window', '.wde': 'report', '.wdr': 'query',
         '.wdg': 'procedures', '.wdc': 'class', '.xdd': 'schema'}
SKIP = {'.git', 'node_modules', 'target', 'dist', 'backup', 'exe',
        'cache.gestion de sources', 'history', 'groupware'}
SEED_COLUMNS = ['id', 'kind', 'element', 'context', 'event', 'evidence', 'confidence',
                'legacy_behavior', 'target_behavior', 'implemented_in', 'test', 'decision', 'status']
KEY_LINE = re.compile(r'^( *)(- +)?([^\s:#][^:]*?)\s*:(?:\s+(.*))?$')
LITERAL = re.compile(r'^\|[0-9+-]*\s*$')
PROCEDURE = re.compile(r'^\s*(?:INTERNAL\s+|INTERNE\s+)?PROC[EÉ]DURE\s+([\w$]+)', re.I)
# Hints only: report where to look, never the value itself.
SECRET_HINTS = [
    ('credential-assignment', re.compile(
        r'\b(password|passwd|pwd|mot_?de_?passe|motdepasse|secret|token|api_?key|apikey)\w*\s*=\s*"[^"]+"', re.I)),
    ('connection-call', re.compile(r'\b(HOpenConnection|HDescribeConnection|HOuvreConnexion|HDécritConnexion)\s*\(', re.I)),
    # Inside connection strings: start of line or after ; or a quote, not variables like sPassword=.
    ('connection-string', re.compile(r'(^|[;"\'])\s*(Password|PWD)\s*=\s*[^;"\s]+', re.I)),
]


def decode_text(data, fallback=None):
    """Only accept identifiable Unicode text unless an explicit fallback codec is given."""
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = data.decode('utf-16')
    else:
        if b'\0' in data:
            return None
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            if not fallback:
                return None
            text = data.decode(fallback)
    if any(ord(c) < 32 and c not in '\r\n\t' for c in text):
        return None
    return text


def parse_key(line):
    """Return (key_indent, key, value, is_item) for a `key : value` line, else None."""
    match = KEY_LINE.match(line)
    if not match:
        return None
    indent = len(match[1]) + (len(match[2]) if match[2] else 0)
    return indent, match[3].strip(), (match[4] or '').strip(), bool(match[2])


def literal_mask(lines):
    """Mark literal block bodies so their text is never mistaken for structure."""
    mask = [False] * len(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        parsed = parse_key(line)
        if not parsed or not LITERAL.match(parsed[2]):
            continue
        for j in range(i + 1, len(lines)):
            following = lines[j]
            if following.strip() and len(following) - len(following.lstrip(' ')) <= parsed[0]:
                break
            mask[j] = True
    return mask


def structure(lines, mask):
    """Parsed key lines; a key following a bare `-` line opens a list item."""
    parsed, pending = [None] * len(lines), False
    for i, line in enumerate(lines):
        if mask[i] or not line.strip():
            continue
        if line.strip() == '-':
            pending = True
            continue
        entry = parse_key(line)
        if entry:
            parsed[i] = entry[:3] + (entry[3] or pending,)
        pending = False
    return parsed


def block_context(parsed, index, indent, is_item=False):
    """Ancestor `name` values plus scalar siblings of the mapping holding a block."""
    names = []
    level = indent
    # A block opening a list item has no earlier siblings.
    closed = is_item
    sibling_start = index
    for j in range(index - 1, -1, -1):
        if not parsed[j]:
            continue
        key_indent, key, value, item = parsed[j]
        if key_indent == level and not closed:
            if level == indent:
                sibling_start = j
            if key == 'name' and value and level != indent:
                names.append(value)
            if item:
                closed = True
        elif key_indent < level:
            level, closed = key_indent, item
            if key == 'name' and value:
                names.append(value)
    siblings = {}
    for j in range(sibling_start, len(parsed)):
        if j == index or not parsed[j]:
            continue
        key_indent, key, value, item = parsed[j]
        if key_indent < indent or (j > index and item and key_indent == indent):
            break
        if key_indent == indent and value and not LITERAL.match(value):
            siblings[key] = value
    return {'names': list(reversed(names)), 'siblings': siblings}


def extract_blocks(text, keys=('code',)):
    """Recognize WINDEV's indented literal blocks, not general YAML."""
    lines = text.splitlines()
    mask = literal_mask(lines)
    parsed = structure(lines, mask)
    blocks = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        entry = parsed[i]
        if not entry or entry[1] not in keys or not LITERAL.match(entry[2]):
            continue
        indent = entry[0]
        body = []
        for following in lines[i + 1:]:
            if following.strip() and len(following) - len(following.lstrip(' ')) <= indent:
                break
            body.append(following)
        # WINDEV's |1- representation uses one extra space for literal content.
        code = '\n'.join(s[indent + 1:] if s.strip() else '' for s in body).rstrip()
        if code.strip():
            blocks.append({'key': entry[1], 'declaration_line': i + 1, 'start_line': i + 2,
                           'end_line': i + 1 + len(body), 'code': code,
                           'context': block_context(parsed, i, indent, parsed[i][3]),
                           'procedures': [m[1] for m in map(PROCEDURE.match, code.splitlines()) if m]})
    return blocks


def encoded_slots(text, blocks):
    """Event slots carrying encoded `internal_properties`: WINDEV keeps a button's predefined action there
    (close, validate, print a report, open a window…). A slot with no code is behavior visible nowhere else;
    a slot with code may run an action besides it. Marks the matching blocks and returns the slots."""
    lines = text.splitlines()
    parsed = structure(lines, literal_mask(lines))
    coded = {(tuple(b['context']['names']), b['context']['siblings'].get('type')): b for b in blocks}
    slots = []
    for i, entry in enumerate(parsed):
        if not entry or entry[1] != 'internal_properties':
            continue
        # Only items of an event list (`code_elements: p_codes:`) are event slots. A column's `content`,
        # a date's `calendar` or a combo's dropdown also pair `type` with encoded properties: there `type`
        # is the sub-object's type, not an event.
        holder = next((parsed[j] for j in range(i - 1, -1, -1) if parsed[j] and parsed[j][0] < entry[0]), None)
        if not holder or holder[1] != 'p_codes':
            continue
        context = block_context(parsed, i, entry[0], entry[3])
        siblings = context['siblings']
        if 'type' not in siblings or 'name' in siblings:
            continue  # a control's or window's own properties, not an event slot
        block = coded.get((tuple(context['names']), siblings['type']))
        if block:
            block['encoded_properties'] = True
        # Equal encoded values mean the same action: an opaque ID groups them (nothing is decoded).
        action = 'A-' + hashlib.sha1((entry[2] or '').encode('utf-8')).hexdigest()[:6]
        slots.append({'names': context['names'], 'event': siblings['type'], 'line': i + 1, 'has_code': bool(block),
                      'action': action})
    return slots


NUMBER = re.compile(r'-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


def control_layout(text):
    """Every control and table column in source order, with its position inside the window.

    Readable `properties` x/y/width/height are relative to the parent control; nested controls
    get their parents' offsets added. Missing x or y means 0 (as WINDEV omits them). A report's
    bands (`blocks`: START_OF_DOCUMENT, PAGE_HEADER, BODY…) are items of kind `band`; their
    controls name the band and keep band-relative positions, in millimetres.
    """
    lines = text.splitlines()
    parsed = structure(lines, literal_mask(lines))
    items, stack = [], []  # stack: (indent, absolute x, absolute y, band) of enclosing controls
    for i, entry in enumerate(parsed):
        if not entry or entry[1] != 'name' or not entry[2]:
            continue
        # The nearest less-indented key is the list holding this item (bare `-` lines are not keys).
        parent = next((parsed[j] for j in range(i - 1, -1, -1) if parsed[j] and parsed[j][0] < entry[0]), None)
        if not parent or parent[1] not in ('controls', 'columns', 'blocks'):
            continue
        indent = entry[0]
        geometry, in_properties = {}, None
        for j in range(i + 1, len(parsed)):
            line = parsed[j]
            if not line:
                continue
            if line[0] < indent or (line[0] == indent and line[3]):
                break
            if line[0] == indent:
                in_properties = line[0] if line[1] == 'properties' else None
            elif in_properties is not None and line[1] in ('x', 'y', 'width', 'height') and NUMBER.fullmatch(line[2]):
                # Windows use whole pixels; reports use millimetres, written "60." or "4.e-003".
                number = round(float(line[2]), 3)
                geometry.setdefault(line[1], int(number) if number.is_integer() else number)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        base_x, base_y, band = stack[-1][1:] if stack else (0, 0, None)
        if parent[1] == 'blocks':
            items.append({'name': entry[2], 'kind': 'band', 'x': 0, 'y': geometry.get('y', 0),
                          'width': geometry.get('width'), 'height': geometry.get('height')})
            stack.append((indent, 0, 0, entry[2]))  # band controls are positioned within the band
            continue
        x, y = base_x + geometry.get('x', 0), base_y + geometry.get('y', 0)
        item = {'name': entry[2], 'kind': 'column' if parent[1] == 'columns' else 'control',
                'x': x, 'y': y, 'width': geometry.get('width'), 'height': geometry.get('height')}
        if band:
            item['band'] = band
        items.append(item)
        stack.append((indent, x, y, band))
    return items


def control_names(text):
    """Every control and table column declared in a window/report, in source order."""
    return [item['name'] for item in control_layout(text) if item['kind'] != 'band']


def dialogs(text):
    """Dialog boxes declared in the window resources: message and button labels per language,
    button values and the cancel button (all readable in the text format)."""
    lines = text.splitlines()
    parsed = structure(lines, literal_mask(lines))
    found, current, button, field, depth = [], None, None, None, None
    for entry in parsed:
        if not entry:
            continue
        indent, key, value, item = entry
        if key == 'dialogs' and not value:
            depth, current = indent, None
            continue
        if depth is None:
            continue
        if indent <= depth:
            depth = None
            continue
        if key == 'identifier' and (current is None or indent <= current['_indent']):
            current = {'identifier': value, 'label': {}, 'buttons': [], 'cancel_button': None, '_indent': indent}
            found.append(current)
            button, field = None, None
        elif current is None:
            continue
        elif key == 'buttons':
            field = 'buttons'
        elif key == 'label':
            if field == 'buttons':
                button = {'label': {}, 'value': None, '_indent': indent}
                current['buttons'].append(button)
                field = 'button-label'
            else:
                field = 'dialog-label'
        elif key == 'cancel_button':
            current['cancel_button'] = int(value) if value.lstrip('-').isdigit() else value
        elif key == 'value' and button is not None:
            button['value'] = int(value) if value.lstrip('-').isdigit() else value
            field = 'buttons'
        elif value and field in ('dialog-label', 'button-label') and '-' in key and len(key) <= 6:
            target = current['label'] if field == 'dialog-label' else button['label']
            target[key] = value.strip('"')
        elif key == 'image':
            field = 'buttons' if field == 'button-label' else field
    for dialog in found:
        dialog.pop('_indent')
        for b in dialog['buttons']:
            b.pop('_indent')
    return found


def element_name(text, fallback):
    """The element's own name (`info : / name :`), which can differ from its file name."""
    match = re.search(r'^info :\s*\n name : ([A-Za-z_][\w$]*)', text, re.M)
    return match[1] if match else fallback


def literal_keys(text):
    """Count every literal block key so other embedded sources (SQL, text) are visible."""
    counts = {}
    for line in text.splitlines():
        parsed = parse_key(line)
        if parsed and LITERAL.match(parsed[2]):
            counts[parsed[1]] = counts.get(parsed[1], 0) + 1
    return counts


def secret_hints(path, blocks):
    hints = []
    for block in blocks:
        for offset, line in enumerate(block['code'].splitlines()):
            for label, pattern in SECRET_HINTS:
                if pattern.search(line):
                    hints.append({'path': path, 'line': block['start_line'] + offset, 'hint': label})
    return hints


def raw_schema(data):
    """Keep raw metadata without asserting WINDEV-to-SQL type equivalence."""
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper() or b'\0' in data:
        raise ValueError('DTD/entity declarations and non-ASCII-compatible XML are unsupported')
    root = ET.fromstring(data)
    if root.tag != 'ANALYSE':
        raise ValueError('Expected an ANALYSE XDD document')
    tables = []
    for table in root.findall('FICHIER'):
        fields = []
        for field in table.findall('RUBRIQUE'):
            fields.append({'attributes': dict(field.attrib),
                           'raw_metadata': ET.tostring(field, encoding='unicode')})
        tables.append({'attributes': dict(table.attrib), 'fields': fields})
    return {'tables': tables,
            'raw_relationships': [ET.tostring(n, encoding='unicode')
                                  for n in root if n.tag != 'FICHIER'],
            'note': 'Raw WINDEV codes; resolve types and constraints before generating SQL.'}


def seed_id(*parts):
    """Stable across re-runs of the same frozen sources."""
    return 'SRC-' + hashlib.sha1('|'.join(parts).encode('utf-8')).hexdigest()[:10]


def seed_row(row_id, kind, element, evidence, context='', event=''):
    row = dict.fromkeys(SEED_COLUMNS, '')
    row.update(id=row_id, kind=kind, element=element, context=context, event=event,
               evidence=evidence, confidence='unresolved', status='unmapped')
    return row


def seed_rows(relative, kind, blocks, element=None, key=None):
    rows, seen = [], {}
    element = element or Path(relative).stem
    for block in blocks:
        names = '/'.join(block['context']['names'])
        event = block['context']['siblings'].get('type', '')
        base = (key or relative, names, event)
        seen[base] = seen.get(base, 0) + 1
        evidence = f"{relative}:{block['start_line']}-{block['end_line']}"
        procedures = ', '.join(block['procedures'])
        rows.append(seed_row(seed_id(*base, str(seen[base])), kind, element, evidence,
                             names + (f' [{procedures}]' if procedures else ''), event))
    return rows


def source_files(source, output, extensions):
    """Files to inspect, in a stable order: backups, compile folders, symlinks and the output are skipped."""
    files = []
    for current, dirs, names in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP
                         and not d.lower().startswith('bkp_')
                         and not d.lower().endswith('.cpl')
                         and not (Path(current) / d).is_symlink()
                         and (Path(current) / d).resolve() != output)
        for name in sorted(names):
            path = Path(current) / name
            if not path.is_symlink() and path.suffix.lower() in extensions:
                files.append(path)
    return files


def inspect(source, output, fallback_encoding=None, extra_extensions=(), literal_block_keys=('code',)):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_dir():
        raise ValueError('Source must be a directory')
    if output == source or output in source.parents:
        raise ValueError('Output must not equal or contain the source directory')
    extensions = EXTENSIONS | {e.lower() if e.startswith('.') else '.' + e.lower() for e in extra_extensions}
    # Refuse reuse: stale artifacts must never be mistaken for current evidence.
    output.mkdir(parents=True, exist_ok=False)
    inventory, seeds, hints = [], [], []
    seen_digests = {}
    files = source_files(source, output, extensions)
    # Seed IDs key on the file name, so they do not change with the folder the inspector is pointed at
    # (legacy/ or legacy/code/); the relative path only when two files share a name.
    file_names = collections.Counter(path.name.lower() for path in files)
    for path in files:
        suffix = path.suffix.lower()
        relative = path.relative_to(source).as_posix()
        key = path.name if file_names[path.name.lower()] == 1 else relative
        kind = KINDS.get(suffix, suffix.lstrip('.'))
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        entry = {'path': relative, 'kind': kind, 'bytes': len(data), 'sha256': digest}
        if digest in seen_digests:
            # Identical copies (e.g. the analysis folder's XDD) must not double the parity seed.
            entry.update(status='duplicate', duplicate_of=seen_digests[digest])
            inventory.append(entry)
            continue
        seen_digests[digest] = relative
        if suffix == '.xdd':
            try:
                schema = raw_schema(data)
                destination = output / 'schema' / (relative + '.json')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding='utf-8')
                entry.update(status='schema', tables=len(schema['tables']))
                for table in schema['tables']:
                    table_name = table['attributes'].get('Nom') or table['attributes'].get('Name', '')
                    seeds.append(seed_row(seed_id(key, 'table', table_name), 'table', table_name,
                                          relative, 'data mapping and reconciliation'))
            except (ET.ParseError, ValueError) as error:
                entry.update(status='unresolved-schema', reason=str(error))
                seeds.append(seed_row(seed_id(key, 'export'), 'export-needed', path.stem, relative))
        else:
            try:
                text = decode_text(data, fallback_encoding)
            except UnicodeError:
                text = None
            if text is None:
                entry.update(status='binary-or-unsupported',
                             reason='Requires WINDEV export; no decoding or behavior inferred.')
                seeds.append(seed_row(seed_id(key, 'export'), 'export-needed', path.stem, relative))
            else:
                blocks = extract_blocks(text, literal_block_keys)
                destination = output / 'code' / (relative + '.json')
                destination.parent.mkdir(parents=True, exist_ok=True)
                name = element_name(text, path.stem)
                layout = control_layout(text)
                controls = [item['name'] for item in layout if item['kind'] != 'band']
                slots = encoded_slots(text, blocks)
                destination.write_text(json.dumps({'path': relative, 'name': name, 'controls': controls, 'layout': layout,
                                                   'dialogs': dialogs(text), 'encoded_slots': slots, 'blocks': blocks},
                                                  indent=2, ensure_ascii=False), encoding='utf-8')
                entry.update(status='text', name=name, code_blocks=len(blocks), controls=len(controls),
                             literal_keys=literal_keys(text),
                             encoded_properties='internal_properties' in text,
                             encoded_actions=sum(1 for s in slots if not s['has_code']))
                seeds.extend(seed_rows(relative, kind, blocks, name, key))
                # A code-less slot with encoded properties is behavior too (a predefined action): seed it.
                for slot in slots:
                    if not slot['has_code']:
                        names = '/'.join(slot['names'])
                        seeds.append(seed_row(seed_id(key, names, slot['event'], 'encoded'), 'encoded-action',
                                              name, f"{relative}:{slot['line']}", f"{names} [encoded action {slot['action']}]",
                                              slot['event']))
                hints.extend(secret_hints(relative, blocks))
        inventory.append(entry)
    with (output / 'parity-seed.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=SEED_COLUMNS)
        writer.writeheader()
        writer.writerows(seeds)
    (output / 'secret-hints.json').write_text(json.dumps(hints, indent=2), encoding='utf-8')
    manifest = {'format_version': 2, 'files': inventory, 'seed_rows': len(seeds), 'secret_hints': len(hints),
                'limitations': ['Literal blocks only; not a complete WINDEV parser or transpiler.',
                                'Binary queries and encoded designer metadata require exports.',
                                'Context names/event codes are raw; event codes are not interpreted.',
                                'Menus, Groupware rights and runtime-only behavior need manual seed rows.',
                                'Data files are not read. Source and outputs may contain secrets.']}
    (output / 'inventory.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path, help='New output directory; may contain sensitive code')
    parser.add_argument('--fallback-encoding', help='Codec for non-UTF text sources, e.g. cp1252')
    parser.add_argument('--extra-ext', action='append', default=[],
                        help='Additional source extension to inventory, e.g. .wwh (repeatable)')
    parser.add_argument('--block-key', action='append', default=[],
                        help='Extra literal block key to extract besides "code" (repeatable)')
    args = parser.parse_args()
    try:
        result = inspect(args.source, args.out, args.fallback_encoding, args.extra_ext,
                         ('code', *args.block_key))
    except (OSError, ValueError, LookupError) as error:
        parser.exit(1, f'Inspection failed: {error}\n')
    counts = {}
    for item in result['files']:
        counts[item['status']] = counts.get(item['status'], 0) + 1
    print(json.dumps({'files': len(result['files']), 'statuses': counts,
                      'seed_rows': result['seed_rows'], 'secret_hints': result['secret_hints']}, indent=2))


if __name__ == '__main__':
    main()
