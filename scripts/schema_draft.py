#!/usr/bin/env python3
"""Draft the target SQLite schema from the analysis, with every non-obvious choice listed as a decision.

The XDD (inspector output) is the authority on structure: every file, item, raw type code, size, key type,
default and null support. The dossier extract names the type codes ("Unsigned 8-byte integer") and gives
captions. Pairing the two yields a type legend backed by WINDEV itself, like event_legend.py does for events.
Nothing here is final: the draft is input for the database ADR and the migrations, not a migration.
"""
import argparse
import collections
import json
from pathlib import Path
import re

# WINDEV type name (English dossier) -> (SQLite type, decision to record, or None when the mapping is lossless).
TYPES = [
    (r'Automatic identifier', 'INTEGER', None),
    (r'Unsigned 8-byte integer', 'INTEGER',
     'unsigned 64-bit: SQLite INTEGER is signed (max 2^63-1); values above 2^53 must cross IPC/JSON as strings'),
    (r'(?:Signed |Unsigned )?[124]-byte integer|8-byte integer', 'INTEGER', None),
    (r'Boolean', 'INTEGER', None),
    (r'(?:4|8)-byte real', 'REAL', 'binary floating point: if this holds money or quantities, use integer minor units or TEXT decimals'),
    (r'Decimal|Numeric|Currency', 'TEXT', 'exact decimal: SQLite has none; choose integer minor units (scale?) or TEXT decimals'),
    (r'Date and Time', 'TEXT', 'kept as WINDEV yyyymmddhhmmssccc text, or ISO 8601? Empty/sentinel values keep their meaning'),
    (r'Date', 'TEXT', 'kept as WINDEV yyyymmdd text, or ISO 8601? Empty date ("" / 00000000) is not NULL by default'),
    (r'Time', 'TEXT', 'kept as WINDEV hhmmss[cc] text, or seconds?'),
    (r'Duration', 'INTEGER', 'unit (milliseconds?) to confirm from code'),
    (r'(?:Unicode )?String|Character|Text Memo|Unicode Memo', 'TEXT', None),
    (r'Binary Memo|Image Memo', 'BLOB', 'store in the database or as files with checksums?'),
    (r'Password', 'TEXT', 'HFSQL password item (salted hash): do not copy; plan reset or rehash (08 transformation checklist)'),
]
KEY_TYPES = {'0': None, '1': 'unique', '2': 'duplicates'}


def tag(text, name):
    match = re.search(rf'<{name}>([^<]*)', text)
    return match[1] if match else None


def load_schema(inspect_dir):
    tables = []
    for path in sorted(Path(inspect_dir, 'schema').rglob('*.json')):
        tables += json.loads(path.read_text(encoding='utf-8'))['tables']
    return tables


def load_analysis(dossier_dir):
    """{file name (lower): {item name (lower): dossier item}} from dossier_extract.py output."""
    files = {}
    for path in Path(dossier_dir, 'analysis').glob('*.json') if dossier_dir else []:
        for name, data in json.loads(path.read_text(encoding='utf-8')).get('files', {}).items():
            files[name.lower()] = {item['name'].lower(): item for item in data.get('items', [])}
    return files


def sql_type(type_name):
    for pattern, sqlite, decision in TYPES:
        if type_name and re.fullmatch(rf'(?:{pattern})(?: \(.*\))?', type_name):
            return sqlite, decision
    return None, None


def draft(inspect_dir, dossier_dir=None):
    tables, analysis = load_schema(inspect_dir), load_analysis(dossier_dir)
    votes = collections.defaultdict(collections.Counter)
    result = []
    for table in tables:
        name = table['attributes'].get('Nom') or table['attributes'].get('Name')
        named = analysis.get(name.lower(), {})
        columns, keys = [], []
        for field in table['fields']:
            raw, item = field['raw_metadata'], named.get(field['attributes']['Nom'].lower(), {})
            column = {'name': field['attributes']['Nom'], 'code': tag(raw, 'TYPE'), 'size': tag(raw, 'TAILLE'),
                      'key': KEY_TYPES.get(tag(raw, 'TYPE_CLE')), 'caption': item.get('caption'),
                      'type': item.get('type'),
                      'default': (re.search(r'Valeur="([^"]*)"', raw) or [None, None])[1],
                      'nullable': 'RubNullSupporte="1"' in raw}
            components = re.findall(r'<COMPOSANTE Nom="([^"]+)"', raw)
            if components:
                keys.append({'name': column['name'], 'columns': components, 'key': column['key']})
                continue
            if column['code'] and column['type']:
                votes[column['code']][column['type']] += 1
            if column['key']:
                keys.append({'name': column['name'], 'columns': [column['name']], 'key': column['key']})
            columns.append(column)
        result.append({'table': name, 'columns': columns, 'keys': keys})
    legend = {code: counter.most_common(1)[0][0] for code, counter in votes.items()}
    conflicts = {code: dict(counter) for code, counter in votes.items() if len(counter) > 1}
    for table in result:
        for column in table['columns']:
            column['type'] = column['type'] or legend.get(column['code'])  # an item the dossier missed
            column['sqlite'], column['decision'] = sql_type(column['type'])
    return {'tables': result, 'type_legend': legend, 'conflicts': conflicts}


def ddl(data):
    lines = ['-- DRAFT generated by scripts/schema_draft.py: review every decision in docs/schema-draft.md first.',
             '-- The analysis declares no constraints between files unless listed there; relations live in code.', '']
    for table in data['tables']:
        body = []
        for c in table['columns']:
            sqlite = c['sqlite'] or 'TEXT /* unresolved type */'
            if c['type'] and c['type'].startswith('Automatic identifier'):
                body.append(f'  "{c["name"]}" INTEGER PRIMARY KEY')
                continue
            default = f" DEFAULT {c['default'] if re.fullmatch(r'-?[0-9.]+', c['default']) else repr(c['default'])}" \
                if c['default'] not in (None, '') else ''
            check = f' CHECK ("{c["name"]}" IN (0, 1))' if c['type'] == 'Boolean' else ''
            body.append(f'  "{c["name"]}" {sqlite}{"" if c["nullable"] else " NOT NULL"}{default}{check}')
        lines += [f'CREATE TABLE "{table["table"]}" (', ',\n'.join(body), ');']
        for key in table['keys']:
            unique = 'UNIQUE ' if key['key'] == 'unique' else ''
            cols = ', '.join(f'"{c}"' for c in key['columns'])
            if len(key['columns']) == 1 and any(c['name'] == key['columns'][0] and (c['type'] or '').startswith(
                    'Automatic identifier') for c in table['columns']):
                continue  # already the primary key
            lines.append(f'CREATE {unique}INDEX "{table["table"]}_{key["name"]}" ON "{table["table"]}" ({cols});')
        lines.append('')
    return '\n'.join(lines)


def markdown(data):
    lines = ['# Schema draft (from the analysis)', '',
             'Generated by `scripts/schema_draft.py` from the XDD (structure, keys, sizes, defaults, null support) and the '
             'dossier (type names, captions). Decide each item below in the database ADR before writing migrations.', '',
             '## Type codes', '', '| XDD code | WINDEV type | SQLite | Decision |', '|---|---|---|---|']
    for code, name in sorted(data['type_legend'].items(), key=lambda kv: int(kv[0])):
        sqlite, decision = sql_type(name)
        lines.append(f'| {code} | {name} | {sqlite or "unresolved"} | {decision or "—"} |')
    if data['conflicts']:
        lines += ['', f"Conflicting names for one code (check the extract): {data['conflicts']}"]
    lines += ['', '## Decisions per column', '', '| Table | Column | Caption | WINDEV type | Key | Decision |', '|---|---|---|---|---|---|']
    for table in data['tables']:
        for c in table['columns']:
            if c['decision'] or not c['sqlite']:
                lines.append(f"| {table['table']} | {c['name']} | {c['caption'] or ''} | {c['type'] or 'code ' + str(c['code'])} | "
                             f"{c['key'] or ''} | {c['decision'] or 'unresolved type: name it from WINDEV documentation'} |")
    lines += ['', '## Keys', '', 'Unique keys become UNIQUE indexes; keys with duplicates become plain indexes (HFSQL '
              'searches them with HReadSeek*: keep them for performance and ordering). Key options such as case or accent '
              'insensitivity are not in this draft: check them in WINDEV (08, "Key options").', '']
    for table in data['tables']:
        for key in table['keys']:
            lines.append(f"- {table['table']}.{key['name']}: {key['key']} on ({', '.join(key['columns'])})")
    lines += ['', '## Tables', '']
    for table in data['tables']:
        lines += [f"### {table['table']}", '', '| Column | Caption | WINDEV type | Size | Key | Default | SQLite |',
                  '|---|---|---|---|---|---|---|']
        lines += [f"| {c['name']} | {c['caption'] or ''} | {c['type'] or 'code ' + str(c['code'])} | {c['size'] or ''} | "
                  f"{c['key'] or ''} | {c['default'] if c['default'] not in (None, '') else ''} | {c['sqlite'] or 'unresolved'} |"
                  for c in table['columns']]
        lines.append('')
    nullable = sum(c['nullable'] for t in data['tables'] for c in t['columns'])
    total = sum(len(t['columns']) for t in data['tables'])
    lines += ['', '## Nulls', '', f'{nullable} of {total} items accept NULL in the analysis. HFSQL still writes the default '
              '(empty string, 0) unless code assigns NULL: whether existing data holds NULLs is a data-export question, '
              'not a schema one.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inspect_dir', type=Path, help='inspect_windev.py output that read the .xdd')
    parser.add_argument('--dossier', type=Path, help='dossier_extract.py output, for type names and captions')
    parser.add_argument('--out', type=Path, required=True, help='Markdown decisions (a .sql and .json sibling are written)')
    args = parser.parse_args()
    data = draft(args.inspect_dir, args.dossier)
    args.out.write_text(markdown(data), encoding='utf-8')
    args.out.with_suffix('.sql').write_text(ddl(data), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
    decisions = sum(1 for t in data['tables'] for c in t['columns'] if c['decision'] or not c['sqlite'])
    print(f"{len(data['tables'])} tables, {sum(len(t['columns']) for t in data['tables'])} columns, "
          f"{len(data['type_legend'])} type codes named, {decisions} column decisions")


if __name__ == '__main__':
    main()
