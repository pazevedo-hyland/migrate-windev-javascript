#!/usr/bin/env python3
"""Export every table of an HFSQL database through ODBC: a lossless SQLite copy, CSV files and a manifest.

Uses PC SOFT's HFSQL ODBC driver (free download) and a DSN pointing at a COPY of the data folder. Values are
kept as the driver returns them; nothing is converted silently:
  data.sqlite  every value as text (dates ISO, decimals exact), bytes as BLOB, NULL as NULL — the copy to
               profile (scripts/data_profile.py) and import from;
  <table>.csv  the same values for golden scenarios and reconciliation (compare_exports.py); CSV cannot tell
               NULL from an empty string, the SQLite copy can;
  manifest.json  rows read and the table's own COUNT(*) (they must agree), column types, null and binary
               counts, a hash of the rows, the driver and Python architecture.
Requires: `pip install pyodbc`.
"""
import argparse
import base64
import csv
import datetime
import decimal
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import struct


def text(value):
    """Stable, lossless text for driver values."""
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray, memoryview)):
        return 'base64:' + base64.b64encode(bytes(value)).decode('ascii')
    if isinstance(value, (datetime.date, datetime.time, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return format(value, 'f')
    return str(value)


def stored(value):
    """The SQLite copy's value: NULL stays NULL, bytes stay bytes, everything else its lossless text."""
    if value is None or isinstance(value, (bytes, bytearray, memoryview)):
        return None if value is None else bytes(value)
    return text(value)


def driver_info(connection):
    try:
        import pyodbc
        return {'driver': connection.getinfo(pyodbc.SQL_DRIVER_NAME), 'version': connection.getinfo(pyodbc.SQL_DRIVER_VER)}
    except Exception:  # a fake connection in tests, or a driver without the info
        return {}


def export(connection, out, tables=None):
    cursor = connection.cursor()
    names = tables or [row.table_name for row in cursor.tables(tableType='TABLE')]
    manifest = {'exported': datetime.datetime.now().isoformat(timespec='seconds'),
                'python': f"{platform.python_version()} {struct.calcsize('P') * 8}-bit", **driver_info(connection),
                'tables': {}}
    copy = sqlite3.connect(out / 'data.sqlite')
    for name in names:
        cursor.execute(f'SELECT COUNT(*) FROM "{name}"')
        counted = cursor.fetchone()[0]
        cursor.execute(f'SELECT * FROM "{name}"')
        columns = [{'name': d[0], 'type': getattr(d[1], '__name__', str(d[1])), 'size': d[3],
                    'precision': d[4], 'scale': d[5], 'nullable': d[6]} for d in cursor.description]
        copy.execute(f'CREATE TABLE "{name}" (' + ', '.join(f'"{c["name"]}"' for c in columns) + ')')
        insert = f'INSERT INTO "{name}" VALUES ({", ".join("?" * len(columns))})'
        digest, rows = hashlib.sha256(), 0
        nulls, binary = [0] * len(columns), [0] * len(columns)
        with (out / f'{name}.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow([c['name'] for c in columns])
            for record in cursor:
                line = [text(v) for v in record]
                writer.writerow(line)
                copy.execute(insert, [stored(v) for v in record])
                digest.update('\x1f'.join(line).encode('utf-8'))
                for index, value in enumerate(record):
                    nulls[index] += value is None
                    binary[index] += isinstance(value, (bytes, bytearray, memoryview))
                rows += 1
        for column, null, raw in zip(columns, nulls, binary):
            column.update(nulls=null, binary=raw)
        manifest['tables'][name] = {'rows': rows, 'count': counted, 'columns': columns, 'sha256_rows': digest.hexdigest()}
        print(f'{name}: {rows} rows' + ('' if rows == counted else f' — COUNT(*) says {counted}'))
    copy.execute('CREATE TABLE __export (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    copy.execute("INSERT INTO __export VALUES ('manifest', ?)", (json.dumps(manifest, ensure_ascii=False),))
    copy.commit()
    copy.close()
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--dsn', help='ODBC data source name configured with the HFSQL driver')
    source.add_argument('--connection-string', help='full ODBC connection string')
    parser.add_argument('--out', type=Path, required=True, help='new directory for data.sqlite, CSV files and manifest.json')
    parser.add_argument('--table', action='append', help='export only these tables (repeatable)')
    args = parser.parse_args()
    import pyodbc
    args.out.mkdir(parents=True, exist_ok=False)
    connection = pyodbc.connect(args.connection_string or f'DSN={args.dsn}', autocommit=True, readonly=True)
    manifest = export(connection, args.out, args.table)
    short = [n for n, t in manifest['tables'].items() if t['rows'] != t['count']]
    if short:  # rows the driver did not return: the export is incomplete, whatever the files look like
        raise SystemExit(f'rows read differ from COUNT(*) in: {", ".join(short)}')


if __name__ == '__main__':
    main()
