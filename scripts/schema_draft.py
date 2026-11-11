#!/usr/bin/env python3
"""Draft the target SQLite schema from the analysis, with every non-obvious choice listed as a decision.

The XDD (inspector output) is the authority on structure: every file, item, raw type code, size, key type,
default and null support. The dossier extract names the type codes ("Unsigned 8-byte integer") and gives
captions. Pairing the two yields a type legend backed by WINDEV itself, like event_legend.py does for events.
Without an XDD, the structure comes from the analysis file itself (windev_decode.py, `analysis.json`): the same
codes, sizes, keys and defaults, plus captions and the digits of each decimal; null support is not read there.
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
KEY_TYPES = {'0': None, '1': 'unique', '2': 'duplicates', '4': 'unique'}  # 4: the file's primary key
# XDD type code -> WINDEV type name, for a project without a dossier. Each pair was named by a dossier (the second
# migration's project, 249 items): a code not listed here stays `code N` until a dossier or WINDEV's documentation
# names it.
TYPE_CODES = {'2': 'String', '9': 'Unsigned 2-byte integer', '11': 'Time (hhmm)', '14': 'Date (yyyymmdd)',
              '26': 'Unsigned 4-byte integer', '27': 'Unsigned 8-byte integer', '29': 'Text Memo',
              '34': 'Date and Time (yyyymmddhhmmssccc)', '35': 'Duration', '36': 'Unsigned 1-byte integer', '37': 'Boolean',
              '41': 'Decimal'}
KEY_CODES = {None: '0', 'unique': '1', 'duplicates': '2'}


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


def load_decoded(decoded_dir):
    """windev_decode.py's reading of the analysis file (`analysis.json`): `tables` and the older `records`."""
    path = Path(decoded_dir, 'analysis.json') if decoded_dir else None
    return json.loads(path.read_text(encoding='utf-8')) if path and path.exists() else {}


def load_records(decoded_dir):
    """[name, caption] records of the analysis file, from windev_decode.py (`analysis.json`)."""
    return load_decoded(decoded_dir).get('records', [])


def tables_from_analysis(tables):
    """The analysis file's tables in the shape the inspector gives an XDD, for a project that has none. Deleted
    files and items are left out; null support is not in what the decoder reads (`RubNullSupporte="?"`)."""
    escape = lambda text: str(text).replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
    result = []
    for table in tables:
        if table.get('deleted'):
            continue
        fields = []
        for item in sorted(table['items'], key=lambda item: item.get('order', 0)):  # the editor's order, as in an XDD
            if item.get('deleted'):
                continue
            name, key = escape(item['name']), KEY_CODES.get(item['key'], '0')
            if item.get('parts'):
                parts = ''.join(f'<COMPOSANTE Nom="{escape(part)}">0</COMPOSANTE>' for part in item['parts'])
                raw = f'<RUBRIQUE Nom="{name}"><TYPE_CLE>{key}</TYPE_CLE><COMPOSEE>0{parts}</COMPOSEE></RUBRIQUE>'
            else:
                raw = (f'<RUBRIQUE Nom="{name}"><TYPE>{item["type_code"]}</TYPE><TYPE_CLE>{key}</TYPE_CLE>'
                       f'<TAILLE>{item["size"]}</TAILLE><INDICERUBRIQUE Indice="0" Valeur="{escape(item.get("default", ""))}" '
                       f'RubNullSupporte="?">0</INDICERUBRIQUE></RUBRIQUE>')
            fields.append({'attributes': {'Nom': item['name']}, 'raw_metadata': raw})
        result.append({'attributes': {'Nom': table['name']}, 'fields': fields})
    return result


def items_by_table(tables):
    """{table name lower: {item name lower: item}} of the analysis file's items still in use."""
    return {table['name'].lower(): {item['name'].lower(): item for item in table['items'] if not item.get('deleted')}
            for table in tables if not table.get('deleted')}


def captions_by_table(tables, records):
    """{table index: {item name lower: caption}}. The records follow the analysis file by file, with items deleted
    since in between: a table takes the run of records that carry its item and key names; the run ends at a name it
    already has (the next file's first item is usually named like one of its own) or at a name only the next
    table has."""
    names_of = lambda t: ({f['attributes']['Nom'].lower() for f in t['fields']})
    result, cursor = {}, 0
    for index, table in enumerate(tables):
        wanted = names_of(table)
        following = names_of(tables[index + 1]) if index + 1 < len(tables) else set()
        found = {}
        while cursor < len(records):
            name = records[cursor][0].lower()
            if name in found or (name not in wanted and name in following and found):
                break
            if name in wanted:
                found[name] = records[cursor][1]
            cursor += 1
        result[index] = found
    return result


def sql_type(type_name):
    for pattern, sqlite, decision in TYPES:
        if type_name and re.fullmatch(rf'(?:{pattern})(?: \(.*\))?', type_name):
            return sqlite, decision
    return None, None


def draft(inspect_dir, dossier_dir=None, decoded_dir=None):
    tables, analysis = load_schema(inspect_dir), load_analysis(dossier_dir)
    decoded = load_decoded(decoded_dir)
    source = 'xdd'
    if not tables and decoded.get('tables'):
        tables, source = tables_from_analysis(decoded['tables']), 'analysis file'
    in_file = items_by_table(decoded.get('tables', []))
    from_file = captions_by_table(tables, decoded.get('records', []))
    votes = collections.defaultdict(collections.Counter)
    result = []
    for index, table in enumerate(tables):
        name = table['attributes'].get('Nom') or table['attributes'].get('Name')
        named = analysis.get(name.lower(), {})
        columns, keys = [], []
        for field in table['fields']:
            raw, item = field['raw_metadata'], named.get(field['attributes']['Nom'].lower(), {})
            column = {'name': field['attributes']['Nom'], 'code': tag(raw, 'TYPE'), 'size': tag(raw, 'TAILLE'),
                      'key': KEY_TYPES.get(tag(raw, 'TYPE_CLE')), 'caption': item.get('caption'),
                      'type': item.get('type'),
                      'default': (re.search(r'Valeur="([^"]*)"', raw) or [None, None])[1],
                      'nullable': None if 'RubNullSupporte="?"' in raw else 'RubNullSupporte="1"' in raw}
            stored = in_file.get(name.lower(), {}).get(column['name'].lower(), {})
            own_caption = stored.get('caption') or from_file.get(index, {}).get(column['name'].lower())
            if not column['caption'] and own_caption:
                # The analysis file's own caption (exact accents), when no dossier gave one.
                column['caption'], column['caption_source'] = own_caption, 'analysis file'
            if 'decimals' in stored:
                column['scale'], column['integer_digits'] = stored['decimals'], stored['integer_digits']
            components = re.findall(r'<COMPOSANTE Nom="([^"]+)"', raw)
            options = {k: stored[k] for k in ('key_options_code', 'key_compares') if k in stored}
            if components:
                keys.append({'name': column['name'], 'columns': components, 'key': column['key']})
                continue
            if column['code'] and column['type']:
                votes[column['code']][column['type']] += 1
            if column['key']:
                keys.append({'name': column['name'], 'columns': [column['name']], 'key': column['key'], **options})
            columns.append(column)
        result.append({'table': name, 'columns': columns, 'keys': keys})
    legend = {code: counter.most_common(1)[0][0] for code, counter in votes.items()}
    # Codes this project's dossier did not name: the names other dossiers gave them.
    used = {column['code'] for table in result for column in table['columns'] if column['code']}
    built_in = sorted(code for code in used if code not in legend and code in TYPE_CODES)
    legend.update({code: TYPE_CODES[code] for code in built_in})
    conflicts = {code: dict(counter) for code, counter in votes.items() if len(counter) > 1}
    for table in result:
        for column in table['columns']:
            column['type'] = column['type'] or legend.get(column['code'])  # an item the dossier missed
            column['sqlite'], column['decision'] = sql_type(column['type'])
            if 'scale' in column and column['decision']:
                # The analysis file says how many digits the decimal has: the question left is the representation.
                column['decision'] = (f"exact decimal, {column['integer_digits']} integer digits and {column['scale']} decimals "
                                      'in the analysis: SQLite has none; choose integer minor units or TEXT decimals')
    return {'source': source, 'tables': result, 'type_legend': legend, 'conflicts': conflicts, 'built_in_codes': built_in,
            'unnamed_codes': sorted(used - set(legend), key=int)}


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
            body.append(f'  "{c["name"]}" {sqlite}{" NOT NULL" if c["nullable"] is False else ""}{default}{check}')
        lines += [f'CREATE TABLE "{table["table"]}" (', ',\n'.join(body), ');']
        for key in table['keys']:
            unique = 'UNIQUE ' if key['key'] == 'unique' else ''
            cols = ', '.join(f'"{c}"' for c in key['columns'])
            if len(key['columns']) == 1 and any(c['name'] == key['columns'][0] and (c['type'] or '').startswith(
                    'Automatic identifier') for c in table['columns']):
                continue  # already the primary key
            note = f"  -- HFSQL {key['key_compares']} on this key" if key.get('key_compares') else ''
            lines.append(f'CREATE {unique}INDEX "{table["table"]}_{key["name"]}" ON "{table["table"]}" ({cols});{note}')
        lines.append('')
    return '\n'.join(lines)


def markdown(data):
    origin = ('the analysis file itself (structure, keys, sizes, defaults, captions, digits of decimals; this project has no '
              'XDD, and null support is not read from the analysis file)' if data.get('source') == 'analysis file' else
              'the XDD (structure, keys, sizes, defaults, null support) and the dossier (type names, captions)')
    lines = ['# Schema draft (from the analysis)', '',
             f'Generated by `scripts/schema_draft.py` from {origin}. Decide each item below in the database ADR before '
             'writing migrations.', '',
             '## Type codes', '', '| XDD code | WINDEV type | SQLite | Decision |', '|---|---|---|---|']
    for code, name in sorted(data['type_legend'].items(), key=lambda kv: int(kv[0])):
        sqlite, decision = sql_type(name)
        lines.append(f'| {code} | {name} | {sqlite or "unresolved"} | {decision or "—"} |')
    if data['conflicts']:
        lines += ['', f"Conflicting names for one code (check the extract): {data['conflicts']}"]
    if data.get('built_in_codes'):
        lines += ['', f"Named from the built-in table, not from this project's dossier: codes {', '.join(data['built_in_codes'])}."]
    if data.get('unnamed_codes'):
        lines += ['', f"Codes nothing names yet: {', '.join(data['unnamed_codes'])}. Name them from WINDEV (the item's "
                  'description in the analysis editor) before writing migrations.']
    lines += ['', '## Decisions per column', '', '| Table | Column | Caption | WINDEV type | Key | Decision |', '|---|---|---|---|---|---|']
    for table in data['tables']:
        for c in table['columns']:
            if c['decision'] or not c['sqlite']:
                lines.append(f"| {table['table']} | {c['name']} | {c['caption'] or ''} | {c['type'] or 'code ' + str(c['code'])} | "
                             f"{c['key'] or ''} | {c['decision'] or 'unresolved type: name it from WINDEV documentation'} |")
    text_keys = [key for table in data['tables'] for key in table['keys'] if 'key_options_code' in key]
    lines += ['', '## Keys', '', 'Unique keys become UNIQUE indexes; keys with duplicates become plain indexes (HFSQL '
              'searches them with HReadSeek*: keep them for performance and ordering).'
              + ('' if text_keys else ' Key options such as case or accent insensitivity are not in this draft: check them '
                 'in WINDEV (08, "Key options"), or pass --decoded to read them from the analysis file.'), '']
    if text_keys:
        folded = sum('key_compares' in key for key in text_keys)
        lines += [f'**Text keys do not compare byte for byte**: {folded} of the {len(text_keys)} text keys ignore case and accents '
                  '(some also spaces and punctuation), as read from the analysis file. A search on such a key finds '
                  '`abc` for `ABC`, and a unique key refuses the second of the two: give the target index and its lookups the '
                  'same folding (a normalised column or an expression index; SQLite `NOCASE` folds ASCII letters only), '
                  'and decide it in the database ADR.', '']
    for table in data['tables']:
        for key in table['keys']:
            compares = (f": {key['key_compares']}" if 'key_compares' in key else
                        f": text key options code {key['key_options_code']}, not measured" if 'key_options_code' in key else '')
            lines.append(f"- {table['table']}.{key['name']}: {key['key']} on ({', '.join(key['columns'])}){compares}")
    lines += ['', '## Tables', '']
    for table in data['tables']:
        lines += [f"### {table['table']}", '', '| Column | Caption | WINDEV type | Size | Key | Default | SQLite |',
                  '|---|---|---|---|---|---|---|']
        digits = lambda c: f" ({c['integer_digits']}+{c['scale']} digits)" if 'scale' in c else ''
        lines += [f"| {c['name']} | {c['caption'] or ''} | {c['type'] or 'code ' + str(c['code'])}{digits(c)} | {c['size'] or ''} | "
                  f"{c['key'] or ''} | {c['default'] if c['default'] not in (None, '') else ''} | {c['sqlite'] or 'unresolved'} |"
                  for c in table['columns']]
        lines.append('')
    nullable = sum(bool(c['nullable']) for t in data['tables'] for c in t['columns'])
    unknown = sum(c['nullable'] is None for t in data['tables'] for c in t['columns'])
    total = sum(len(t['columns']) for t in data['tables'])
    counted = (f'Null support is not read from the analysis file ({unknown} items): the draft leaves every column nullable; '
               'check the items in WINDEV or export the XDD.' if unknown else
               f'{nullable} of {total} items accept NULL in the analysis.')
    lines += ['', '## Nulls', '', f'{counted} HFSQL still writes the default '
              '(empty string, 0) unless code assigns NULL: whether existing data holds NULLs is a data-export question, '
              'not a schema one.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inspect_dir', type=Path, help='inspect_windev.py output (its schema/ folder holds what the .xdd says)')
    parser.add_argument('--dossier', type=Path, help='dossier_extract.py output, for type names and captions')
    parser.add_argument('--decoded', type=Path, help='windev_decode.py output: captions and decimal digits from the analysis file, and the whole structure when there is no .xdd')
    parser.add_argument('--out', type=Path, required=True, help='Markdown decisions (a .sql and .json sibling are written)')
    args = parser.parse_args()
    data = draft(args.inspect_dir, args.dossier, args.decoded)
    args.out.write_text(markdown(data), encoding='utf-8')
    args.out.with_suffix('.sql').write_text(ddl(data), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
    decisions = sum(1 for t in data['tables'] for c in t['columns'] if c['decision'] or not c['sqlite'])
    print(f"{len(data['tables'])} tables, {sum(len(t['columns']) for t in data['tables'])} columns, "
          f"{len(data['type_legend'])} type codes named, {decisions} column decisions")


if __name__ == '__main__':
    main()
