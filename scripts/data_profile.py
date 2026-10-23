#!/usr/bin/env python3
"""Profile the legacy data against the analysis: what the values really are, before deciding the target schema.

Reads a copy of the data — an SQLite staging file, or the CSV folder of scripts/windows/export_odbc.py — and the
schema draft (docs/schema/schema-draft.json), and reports per column: nulls, empty strings, distinct values, value
shapes (digits as 9, letters as A; non-text columns only), lengths against the analysis size, values that do not
parse as the WINDEV type, zeros, constant columns, stray spaces, line breaks and control characters; per key:
duplicates (composite keys rebuilt from their parts); per link: orphans. Findings turn data assumptions into
evidence (`export: docs/data/profile.md#<table>`) and feed the database ADR and the import's quarantine rules.

The report holds counts, shapes, lengths and numeric or date extremes — no record values. Review it before
committing anyway (an extreme can be a real amount).
"""
import argparse
import base64
import collections
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3

DATE_FORMATS = {'Date': ('%Y%m%d', 8), 'Date and Time': ('%Y%m%d%H%M%S', 14), 'Time': ('%H%M%S', 6)}


def as_text(value):
    """A stored value as text: bytes (a binary column of the ODBC export) become base64, as in its CSV files."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return 'base64:' + base64.b64encode(value).decode('ascii')
    return str(value)


def shape(value):
    return re.sub(r'[^\W\d_]', 'A', re.sub(r'\d', '9', value))[:24]


def load(source):
    """An SQLite connection on the data: the file itself (read-only) or the CSV folder loaded in memory."""
    source = Path(source)
    if source.is_file():
        return sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)  # read-only, any OS
    connection = sqlite3.connect(':memory:')
    for path in sorted(source.glob('*.csv')):
        with path.open(newline='', encoding='utf-8') as handle:
            rows = list(csv.reader(handle))
        if not rows:
            continue
        columns = ', '.join(f'"{c}" TEXT' for c in rows[0])
        connection.execute(f'CREATE TABLE "{path.stem}" ({columns})')
        connection.executemany(f'INSERT INTO "{path.stem}" VALUES ({", ".join("?" * len(rows[0]))})', rows[1:])
    return connection


def kind_of(type_name):
    name = type_name or ''
    for date_kind in DATE_FORMATS:
        if name.startswith(date_kind):
            return date_kind
    if 'integer' in name or name.startswith('Automatic identifier'):
        return 'unsigned' if name.startswith(('Unsigned', 'Automatic')) else 'integer'
    if any(word in name for word in ('real', 'Decimal', 'Currency', 'Numeric')):
        return 'number'
    if name == 'Boolean':
        return 'boolean'
    return 'text'


def invalid(value, kind):
    if value in (None, ''):
        return False
    if kind in ('integer', 'unsigned'):
        return not re.fullmatch(r'-?\d+' if kind == 'integer' else r'\d+', value)
    if kind == 'number':
        return not re.fullmatch(r'-?\d+(\.\d+)?', value)
    if kind == 'boolean':
        return value not in ('0', '1')
    if kind in DATE_FORMATS:
        fmt, digits = DATE_FORMATS[kind]
        if set(value) == {'0'}:
            return False  # WINDEV's empty date or time: counted apart
        if re.fullmatch(r'\d{4}-\d\d-\d\d([T ]\d\d:\d\d(:\d\d(\.\d+)?)?)?|\d\d:\d\d(:\d\d(\.\d+)?)?', value):
            value = re.sub(r'\D', '', value)  # the ODBC export writes dates in ISO 8601: compare as WINDEV digits
        try:
            datetime.strptime(value[:digits], fmt)
            return not value.isdigit()
        except ValueError:
            return True
    return False


def column_profile(values, spec):
    kind = kind_of(spec.get('type'))
    present = [v for v in values if v is not None]
    filled = [v for v in present if v != '']
    numbers = sorted(float(v) for v in filled if kind in ('integer', 'unsigned', 'number') and not invalid(v, kind))
    result = {'type': spec.get('type') or f"code {spec.get('code', '?')}", 'rows': len(values),
              'null': len(values) - len(present), 'empty': len(present) - len(filled),
              'distinct': len(set(present)), 'invalid': sum(invalid(v, kind) for v in filled),
              'max_length': max((len(v) for v in filled), default=0)}
    if kind != 'text':
        result['shapes'] = collections.Counter(shape(v) for v in present).most_common(3)
    if numbers:
        result.update(zero=sum(n == 0 for n in numbers), min=numbers[0], max=numbers[-1],
                      p99=numbers[int(0.99 * (len(numbers) - 1))])
        result['above_2_53'] = sum(n > 2 ** 53 for n in numbers)
    if kind in DATE_FORMATS:
        result['zero_date'] = sum(set(v) == {'0'} for v in filled)
        dated = sorted(v for v in filled if set(v) != {'0'} and not invalid(v, kind))
        result.update(min=dated[0] if dated else None, max=dated[-1] if dated else None)
    if kind == 'text':
        result.update(padded=sum(v != v.strip() for v in filled),
                      line_breaks=sum('\n' in v or '\r' in v for v in filled),
                      control=sum(v.startswith('base64:') or bool(re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', v))
                                  for v in filled))
    return result


def findings(profile, spec):
    notes = []
    size = int(spec['size']) if str(spec.get('size', '')).isdigit() else None
    if not spec:
        if profile.get('control'):  # binary bytes read as text: nothing else about it is meaningful
            return ['not in the analysis, binary content: a composite key exported as data — rebuild it as a '
                    'composite index from its parts, do not import its values']
        notes.append('not in the analysis')
    if profile['rows'] > 1 and profile['distinct'] <= 1:
        notes.append('one value in every row: unused or always defaulted — check the code before mapping it')
    if profile['invalid']:
        notes.append(f"{profile['invalid']} values do not parse as {profile['type']}")
    if profile.get('zero') and profile['zero'] >= 0.5 * profile['rows'] and profile['distinct'] > 1:
        notes.append(f"{profile['zero']} zeros of {profile['rows']}: does 0 mean empty here (dossier 'Blank if zero')?")
    if profile['empty'] and kind_of(spec.get('type')) != 'text':
        notes.append(f"{profile['empty']} empty strings in a {profile['type']} column: empty is not NULL in HFSQL")
    if profile.get('zero_date'):
        notes.append(f"{profile['zero_date']} zero dates (WINDEV empty date)")
    if profile.get('above_2_53'):
        notes.append(f"{profile['above_2_53']} values above 2^53: they must cross JSON/IPC as strings")
    if profile.get('p99') and profile['max'] > 20 * max(profile['p99'], 1):
        notes.append(f"maximum {profile['max']:g} is over 20 × the 99th percentile ({profile['p99']:g}): typo or real?")
    memo = 'Memo' in (spec.get('type') or '')  # a memo's analysis size is its pointer, not a length
    if size and not memo and kind_of(spec.get('type')) == 'text' and profile['max_length'] > size:
        notes.append(f"longer than the analysis size ({profile['max_length']} > {size})")
    if profile.get('padded'):
        notes.append(f"{profile['padded']} values with leading or trailing spaces: keep, or trim in the import?")
    if profile.get('line_breaks'):
        notes.append(f"{profile['line_breaks']} values with line breaks (WINDEV writes CR LF)")
    return notes


def candidate_links(tables, schema):
    """(table, column, target table, target key) for columns named after another table (Cliente → Clientes) or
    after its identifier (ClientesID), aimed at that table's single-column unique keys."""
    unique = {t['table'].lower(): (t['table'], [k['columns'][0] for k in t.get('keys', [])
                                                if k['key'] == 'unique' and len(k['columns']) == 1])
              for t in schema}
    links = []
    for table, columns in tables.items():
        for column in columns:
            low = column.lower()
            for key, (target, keys) in unique.items():
                if target == table or not keys:
                    continue
                if key in (low, low + 's', low + 'es') or low == key + 'id':
                    links += [(table, column, target, k) for k in keys]
    return links


def profile(connection, schema, refs=()):
    specs = {(t['table'].lower(), c['name'].lower()): c for t in schema for c in t['columns']}
    tables = {name: [r[1] for r in connection.execute(f'PRAGMA table_info("{name}")')]
              for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                                "AND name NOT LIKE '\\_\\_%' ESCAPE '\\'")}
    report = {'tables': {}, 'keys': [], 'links': [], 'missing_columns': []}
    for table, columns in sorted(tables.items(), key=lambda item: item[0].lower()):
        entry = {'rows': connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0], 'columns': {}}
        for column in columns:
            spec = specs.get((table.lower(), column.lower()), {})
            values = [as_text(v) for (v,) in connection.execute(f'SELECT "{column}" FROM "{table}"')]
            data = column_profile(values, spec)
            data["findings"] = findings(data, spec)
            entry['columns'][column] = data
        report['tables'][table] = entry
    for described in schema:
        table = next((t for t in tables if t.lower() == described['table'].lower()), None)
        if table is None:
            report['missing_columns'].append(f"{described['table']} (whole table)")
            continue
        present = {c.lower(): c for c in tables[table]}
        report['missing_columns'] += [f"{table}.{c['name']}" for c in described['columns'] if c['name'].lower() not in present]
        for key in described.get('keys', []):
            parts = [present.get(c.lower()) for c in key['columns']]
            if key['key'] != 'unique' or None in parts:
                continue
            joined = " || char(31) || ".join(f'"{p}"' for p in parts)  # a composite key rebuilt from its parts
            duplicates = connection.execute(f'SELECT COUNT(*) - COUNT(DISTINCT {joined}) FROM "{table}"').fetchone()[0]
            report['keys'].append({'table': table, 'key': key['name'], 'columns': parts, 'duplicates': duplicates})
    column_values = lambda table, column: [as_text(v) for (v,) in connection.execute(f'SELECT "{column}" FROM "{table}"')]
    candidates = collections.defaultdict(list)
    present = {(table.lower(), column.lower()) for table, columns in tables.items() for column in columns}
    for table, column, target, key in candidate_links(tables, schema):
        if (target.lower(), key.lower()) in present:  # the analysis may list tables the copy does not hold
            candidates[(table, column)].append((target, key))
    for ref in refs:
        table, column, target, key = re.split(r'[.=]', ref)
        candidates[(table, column)] = [(target, key)]
    for (table, column), targets in candidates.items():
        values = [v for v in column_values(table, column) if v not in (None, '')]
        empty = sum(v == '0' for v in values)  # 0 in a numeric link is WINDEV's "no link"
        checked = []
        for target, key in targets:
            known = set(column_values(target, key))
            missing = [v for v in values if v != '0' and v not in known]
            checked.append({'from': f'{table}.{column}', 'to': f'{target}.{key}', 'orphans': len(missing),
                            'orphan_values': len(set(missing)), 'zero': empty, 'rows': len(values)})
        # Named like several keys of the target: the one the values match is the link.
        report['links'].append(min(checked, key=lambda link: link['orphans']))
    return report


def markdown(report, source):
    lines = ['# Legacy data profile', '',
             f'Generated by `scripts/data_profile.py` from {source}. Counts, shapes (9 = digit, A = letter), lengths and '
             'extremes only. Each finding becomes a database-ADR decision, an import rule (keep, convert, quarantine) or '
             'a mapping fact; cite it as `export: docs/data/profile.md#<table>`.', '',
             '## Findings', '']
    for table, entry in report['tables'].items():
        for column, data in entry['columns'].items():
            lines += [f'- **{table}.{column}** ({data["type"]}): {note}' for note in data['findings']]
    lines += [f'- **{k["table"]}** unique key {k["key"]}: {k["duplicates"]} duplicates' for k in report['keys'] if k['duplicates']]
    lines += [f'- **{link["from"]} → {link["to"]}**: {link["orphans"]} rows point to {link["orphan_values"]} missing values'
              for link in report['links'] if link['orphans']]
    lines += [f'- **{link["from"]} → {link["to"]}**: 0 in every row — the link is not used; the real one is elsewhere'
              for link in report['links'] if link['rows'] and link['zero'] == link['rows']]
    lines += [f'- **{c}**: in the analysis, not in the data' for c in report['missing_columns']]
    lines += ['', '## Links checked', '', 'Named after a table or its identifier, or given with `--ref`; the analysis '
              'declares none when relations live in code.', '',
              '| From | To | Rows | 0 (no link) | Orphan rows | Missing values |', '|---|---|---|---|---|---|']
    lines += [f'| {l["from"]} | {l["to"]} | {l["rows"]} | {l["zero"]} | {l["orphans"]} | {l["orphan_values"]} |'
              for l in report['links']]
    for table, entry in report['tables'].items():
        lines += ['', f'## {table}', '', f'{entry["rows"]} rows.', '',
                  '| Column | Type | Null | Empty | Distinct | Invalid | Max length | Range | Shapes |', '|---|---|---|---|---|---|---|---|---|']
        for column, d in entry['columns'].items():
            extent = f'{d["min"]:g} … {d["max"]:g}' if isinstance(d.get('min'), float) else (
                f'{d["min"]} … {d["max"]}' if d.get('min') else '')
            shapes = ', '.join(f'`{s}` {n}' for s, n in d.get('shapes', []))
            lines.append(f'| {column} | {d["type"]} | {d["null"]} | {d["empty"]} | {d["distinct"]} | {d["invalid"]} | '
                         f'{d["max_length"]} | {extent} | {shapes} |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('data', type=Path, help='SQLite copy of the data, or the CSV folder of export_odbc.py')
    parser.add_argument('--schema', type=Path, default=Path('docs/schema/schema-draft.json'), help='schema_draft.py JSON')
    parser.add_argument('--ref', action='append', default=[], help='extra link to check, e.g. ordem.matricula=Viaturas.matricula')
    parser.add_argument('--out', type=Path, default=Path('docs/data/profile.md'), help='Markdown (a .json sibling is written)')
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding='utf-8'))['tables']
    connection = load(args.data)
    try:
        report = profile(connection, schema, args.ref)
    finally:
        connection.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown(report, args.data.name), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    count = sum(len(d['findings']) for e in report['tables'].values() for d in e['columns'].values())
    print(f"{len(report['tables'])} tables, {count} column findings, "
          f"{sum(1 for k in report['keys'] if k['duplicates'])} keys with duplicates, "
          f"{sum(1 for l in report['links'] if l['orphans'])} links with orphans -> {args.out}")


if __name__ == '__main__':
    main()
