#!/usr/bin/env python3
"""Convert the ANSI ODBC export (hfsql-export.ps1: one <table>.jsonl per table) into export_odbc.py's output.

Each JSONL file starts with a header line {table, count, columns, encoding}; every next line is one row, a JSON array of
values: text as strings (numbers too, in the driver's text form), NULL as null, binary as {"base64": "..."}.
The output is exactly export_odbc.py's: data.sqlite (every value as text, bytes as BLOB, NULL as NULL), one CSV per
table and manifest.json with rows read and the source COUNT(*) — the export fails when they differ. The conversion
reuses export_odbc.export, so data_profile.py, compare_exports.py and importers read both the same way.

  python3 scripts/windows/hfsql_jsonl.py --in <work>/jsonl --out <new folder>

Standard library only; runs on any OS (the export itself needs Windows and the HFSQL ODBC driver).
"""
import argparse
import base64
import importlib.util
import json
from pathlib import Path
import re


def _exporter():
    path = Path(__file__).with_name('export_odbc.py')
    spec = importlib.util.spec_from_file_location('export_odbc', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _value(value, where):
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, dict) and set(value) == {'base64'} and isinstance(value['base64'], str):
        return base64.b64decode(value['base64'], validate=True)
    raise ValueError(f'{where}: unexpected JSON value {value!r} (strings, null or {{"base64": ...}} only)')


class _Table:
    """One JSONL file: its header and a streaming row reader."""

    def __init__(self, path):
        self.path = path
        with path.open(encoding='utf-8') as handle:
            first = handle.readline()
        if not first.strip():
            raise ValueError(f'{path.name}: empty file, no header line')
        self.header = json.loads(first)
        for key in ('table', 'count', 'columns'):
            if key not in self.header:
                raise ValueError(f'{path.name}: header without "{key}"')
        if self.header['table'] != path.stem:
            raise ValueError(f'{path.name}: header names table {self.header["table"]!r}')
        if not isinstance(self.header['count'], int) or self.header['count'] < 0:
            raise ValueError(f'{path.name}: header count is not a row count')
        self.columns = self.header['columns']

    def rows(self):
        width = len(self.columns)
        with self.path.open(encoding='utf-8') as handle:
            handle.readline()
            for number, line in enumerate(handle, start=2):
                if not line.strip():
                    continue
                values = json.loads(line)
                where = f'{self.path.name}:{number}'
                if not isinstance(values, list) or len(values) != width:
                    raise ValueError(f'{where}: row has {len(values) if isinstance(values, list) else "no"} values, header {width}')
                yield tuple(_value(v, where) for v in values)


class _Cursor:
    """The minimal DB-API surface export_odbc.export uses, served from JSONL files."""

    def __init__(self, tables):
        self.tables, self.current, self.description = tables, None, None

    def execute(self, sql):
        match = re.fullmatch(r'SELECT (COUNT\(\*\)|\*) FROM "(.+)"', sql)
        self.current = self.tables[match.group(2)]
        self.counting = match.group(1) != '*'
        self.description = [(c['name'], bytes if c.get('type') == 'bytes' else str, None, c.get('size'), None,
                             c.get('scale'), c.get('nullable')) for c in self.current.columns]

    def fetchone(self):
        return (self.current.header['count'],)

    def __iter__(self):
        return self.current.rows()


def convert(source, out):
    """Write data.sqlite, CSV files and manifest.json for every <table>.jsonl in `source`; return the manifest."""
    source, out = Path(source), Path(out)
    tables = {path.stem: _Table(path) for path in sorted(source.glob('*.jsonl'))}
    if not tables:
        raise ValueError(f'no .jsonl files in {source}')
    out.mkdir(parents=True, exist_ok=False)
    encodings = sorted({t.header.get('encoding', '') for t in tables.values()} - {''})
    cursor = _Cursor(tables)
    connection = type('JsonlConnection', (), {'cursor': lambda self: cursor})()
    info = {'source': 'HFSQL ANSI ODBC export (hfsql-export.ps1, JSONL)', 'encoding': '; '.join(encodings),
            'odbc_sql_types': {name: {c['name']: c.get('odbc_sql_type') for c in t.columns} for name, t in tables.items()}}
    return _exporter().export(connection, out, list(tables), info=info)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--in', dest='source', type=Path, required=True, help='the jsonl folder written by hfsql-export.ps1')
    parser.add_argument('--out', type=Path, required=True, help='new directory for data.sqlite, CSV files and manifest.json')
    args = parser.parse_args()
    manifest = convert(args.source, args.out)
    short = [n for n, t in manifest['tables'].items() if t['rows'] != t['count']]
    if short:
        raise SystemExit(f'rows read differ from COUNT(*) in: {", ".join(short)}')
    total = sum(t['rows'] for t in manifest['tables'].values())
    print(f'{len(manifest["tables"])} tables, {total} rows -> {args.out}')


if __name__ == '__main__':
    main()
