#!/usr/bin/env python3
"""Inspect WINDEV text sources and raw XDD metadata; never execute legacy code."""
import argparse
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
                'legacy_behavior', 'target_behavior', 'implemented_in', 'test', 'decision', 'ticket', 'status']
KEY_LINE = re.compile(r'^( *)(- +)?([^\s:#][^:]*?)\s*:(?:\s+(.*))?$')
LITERAL = re.compile(r'^\|[0-9+-]*\s*$')
PROCEDURE = re.compile(r'^\s*(?:INTERNAL\s+|INTERNE\s+)?PROC[EÉ]DURE\s+([\w$]+)', re.I)
# Hints only: report where to look, never the value itself.
SECRET_HINTS = [
    ('credential-assignment', re.compile(
        r'\b(password|passwd|pwd|mot_?de_?passe|motdepasse|secret|token|api_?key|apikey)\w*\s*=\s*"[^"]+"', re.I)),
    ('connection-call', re.compile(r'\b(HOpenConnection|HDescribeConnection|HOuvreConnexion|HDécritConnexion)\s*\(', re.I)),
    ('connection-string', re.compile(r'(Password|PWD)\s*=\s*[^;"\s]+', re.I)),
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


def block_context(lines, mask, index, indent, is_item=False):
    """Ancestor `name` values plus scalar siblings of the mapping holding a block."""
    names = []
    level = indent
    # A block opening a list item has no earlier siblings.
    closed = is_item
    sibling_start = index
    for j in range(index - 1, -1, -1):
        parsed = None if mask[j] else parse_key(lines[j])
        if not parsed:
            continue
        key_indent, key, value, is_item = parsed
        if key_indent == level and not closed:
            if level == indent:
                sibling_start = j
            if key == 'name' and value and level != indent:
                names.append(value)
            if is_item:
                closed = True
        elif key_indent < level:
            level, closed = key_indent, is_item
            if key == 'name' and value:
                names.append(value)
    siblings = {}
    for j in range(sibling_start, len(lines)):
        if j == index or mask[j]:
            continue
        parsed = parse_key(lines[j])
        if not parsed:
            continue
        key_indent, key, value, is_item = parsed
        if key_indent < indent or (j > index and is_item and key_indent == indent):
            break
        if key_indent == indent and value and not LITERAL.match(value):
            siblings[key] = value
    return {'names': list(reversed(names)), 'siblings': siblings}


def extract_blocks(text, keys=('code',)):
    """Recognize WINDEV's indented literal blocks, not general YAML."""
    lines = text.splitlines()
    mask = literal_mask(lines)
    blocks = []
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        parsed = parse_key(line)
        if not parsed or parsed[1] not in keys or not LITERAL.match(parsed[2]):
            continue
        indent = parsed[0]
        body = []
        for following in lines[i + 1:]:
            if following.strip() and len(following) - len(following.lstrip(' ')) <= indent:
                break
            body.append(following)
        # WINDEV's |1- representation uses one extra space for literal content.
        code = '\n'.join(s[indent + 1:] if s.strip() else '' for s in body).rstrip()
        if code.strip():
            blocks.append({'key': parsed[1], 'declaration_line': i + 1, 'start_line': i + 2,
                           'end_line': i + 1 + len(body), 'code': code,
                           'context': block_context(lines, mask, i, indent, parsed[3]),
                           'procedures': [m[1] for m in map(PROCEDURE.match, code.splitlines()) if m]})
    return blocks


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


def seed_rows(relative, kind, blocks):
    rows, seen = [], {}
    element = Path(relative).stem
    for block in blocks:
        names = '/'.join(block['context']['names'])
        event = block['context']['siblings'].get('type', '')
        base = (relative, names, event)
        seen[base] = seen.get(base, 0) + 1
        evidence = f"{relative}:{block['start_line']}-{block['end_line']}"
        procedures = ', '.join(block['procedures'])
        rows.append(seed_row(seed_id(*base, str(seen[base])), kind, element, evidence,
                             names + (f' [{procedures}]' if procedures else ''), event))
    return rows


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
    for current, dirs, names in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP
                         and not d.lower().startswith('bkp_')
                         and not d.lower().endswith('.cpl')
                         and not (Path(current) / d).is_symlink()
                         and (Path(current) / d).resolve() != output)
        for name in sorted(names):
            path = Path(current) / name
            suffix = path.suffix.lower()
            if path.is_symlink() or suffix not in extensions:
                continue
            relative = path.relative_to(source).as_posix()
            kind = KINDS.get(suffix, suffix.lstrip('.'))
            data = path.read_bytes()
            entry = {'path': relative, 'kind': kind, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()}
            if suffix == '.xdd':
                try:
                    schema = raw_schema(data)
                    destination = output / 'schema' / (relative + '.json')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding='utf-8')
                    entry.update(status='schema', tables=len(schema['tables']))
                    for table in schema['tables']:
                        table_name = table['attributes'].get('Nom') or table['attributes'].get('Name', '')
                        seeds.append(seed_row(seed_id(relative, 'table', table_name), 'table', table_name,
                                              relative, 'data mapping and reconciliation'))
                except (ET.ParseError, ValueError) as error:
                    entry.update(status='unresolved-schema', reason=str(error))
                    seeds.append(seed_row(seed_id(relative, 'export'), 'export-needed', path.stem, relative))
            else:
                try:
                    text = decode_text(data, fallback_encoding)
                except UnicodeError:
                    text = None
                if text is None:
                    entry.update(status='binary-or-unsupported',
                                 reason='Requires WINDEV export; no decoding or behavior inferred.')
                    seeds.append(seed_row(seed_id(relative, 'export'), 'export-needed', path.stem, relative))
                else:
                    blocks = extract_blocks(text, literal_block_keys)
                    destination = output / 'code' / (relative + '.json')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(json.dumps({'path': relative, 'blocks': blocks},
                                                      indent=2, ensure_ascii=False), encoding='utf-8')
                    entry.update(status='text', code_blocks=len(blocks),
                                 literal_keys=literal_keys(text),
                                 encoded_properties='internal_properties' in text)
                    seeds.extend(seed_rows(relative, kind, blocks))
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
