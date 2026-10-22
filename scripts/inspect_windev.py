#!/usr/bin/env python3
"""Inspect WINDEV text sources and raw XDD metadata; never execute legacy code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

EXTENSIONS = {'.wdp', '.wdw', '.wde', '.wdr', '.wdg', '.wdc', '.xdd'}
SKIP = {'.git', 'node_modules', 'target', 'dist', 'backup', 'exe',
        'cache.gestion de sources', 'history', 'groupware'}


def decode_text(data):
    """Only accept identifiable Unicode text; do not guess binary encodings."""
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = data.decode('utf-16')
    else:
        if b'\0' in data:
            return None
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            return None
    if any(ord(c) < 32 and c not in '\r\n\t' for c in text):
        return None
    return text


def extract_blocks(text):
    """Recognize WINDEV's indented code literal blocks, not general YAML."""
    lines = text.splitlines()
    blocks = []
    for i, line in enumerate(lines):
        match = re.match(r'^( *)code\s*:\s*\|[0-9+-]*\s*$', line)
        if not match:
            continue
        indent = len(match[1])
        body = []
        for following in lines[i + 1:]:
            if following.strip() and len(following) - len(following.lstrip(' ')) <= indent:
                break
            body.append(following)
        # WINDEV's |1- representation uses one extra space for literal content.
        code = '\n'.join(s[indent + 1:] if s.strip() else '' for s in body).rstrip()
        if code.strip():
            blocks.append({'declaration_line': i + 1, 'start_line': i + 2,
                           'end_line': i + 1 + len(body), 'code': code})
    return blocks


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


def inspect(source, output):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_dir():
        raise ValueError('Source must be a directory')
    if output == source or output in source.parents:
        raise ValueError('Output must not equal or contain the source directory')
    # Refuse reuse: stale artifacts must never be mistaken for current evidence.
    output.mkdir(parents=True, exist_ok=False)
    inventory = []
    for current, dirs, names in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP
                         and not d.lower().startswith('bkp_')
                         and not d.lower().endswith('.cpl')
                         and not (Path(current) / d).is_symlink()
                         and (Path(current) / d).resolve() != output)
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink() or path.suffix.lower() not in EXTENSIONS:
                continue
            relative = path.relative_to(source).as_posix()
            data = path.read_bytes()
            entry = {'path': relative, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()}
            if path.suffix.lower() == '.xdd':
                try:
                    schema = raw_schema(data)
                    destination = output / 'schema' / (relative + '.json')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding='utf-8')
                    entry.update(status='schema', tables=len(schema['tables']))
                except (ET.ParseError, ValueError) as error:
                    entry.update(status='unresolved-schema', reason=str(error))
            else:
                try:
                    text = decode_text(data)
                except UnicodeError:
                    text = None
                if text is None:
                    entry.update(status='binary-or-unsupported',
                                 reason='Requires WINDEV export; no decoding or behavior inferred.')
                else:
                    blocks = extract_blocks(text)
                    destination = output / 'code' / (relative + '.json')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(json.dumps({'path': relative, 'blocks': blocks},
                                                      indent=2, ensure_ascii=False), encoding='utf-8')
                    entry.update(status='text', code_blocks=len(blocks),
                                 encoded_properties='internal_properties' in text)
            inventory.append(entry)
    manifest = {'format_version': 1, 'files': inventory,
                'limitations': ['Code blocks only; not a complete WINDEV parser or transpiler.',
                                'Binary queries and encoded designer metadata require exports.',
                                'Data files are not read. Source and outputs may contain secrets.']}
    (output / 'inventory.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path, help='New output directory; may contain sensitive code')
    args = parser.parse_args()
    try:
        result = inspect(args.source, args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Inspection failed: {error}\n')
    counts = {}
    for item in result['files']:
        counts[item['status']] = counts.get(item['status'], 0) + 1
    print(json.dumps({'files': len(result['files']), 'statuses': counts}, indent=2))


if __name__ == '__main__':
    main()
