#!/usr/bin/env python3
"""Export every table of an HFSQL database to CSV through ODBC, with a manifest.

Uses PC SOFT's HFSQL ODBC driver (free download) and a DSN pointing at a COPY of the data
folder. Values are written as the driver returns them; nothing is converted silently.
Requires: `pip install pyodbc`.
"""
import argparse
import csv
import datetime
import decimal
import hashlib
import json
from pathlib import Path


def text(value):
    """Stable, lossless CSV text for driver values."""
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray, memoryview)):
        return 'base64:' + __import__('base64').b64encode(bytes(value)).decode('ascii')
    if isinstance(value, (datetime.date, datetime.time, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return format(value, 'f')
    return str(value)


def export(connection, out, tables=None):
    cursor = connection.cursor()
    names = tables or [row.table_name for row in cursor.tables(tableType='TABLE')]
    manifest = {'exported': datetime.datetime.now().isoformat(timespec='seconds'), 'tables': {}}
    for name in names:
        cursor.execute(f'SELECT * FROM "{name}"')
        columns = [{'name': d[0], 'type': getattr(d[1], '__name__', str(d[1])), 'size': d[3],
                    'precision': d[4], 'scale': d[5], 'nullable': d[6]} for d in cursor.description]
        path = out / f'{name}.csv'
        digest, rows = hashlib.sha256(), 0
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow([c['name'] for c in columns])
            for record in cursor:
                line = [text(v) for v in record]
                writer.writerow(line)
                digest.update('\x1f'.join(line).encode('utf-8'))
                rows += 1
        manifest['tables'][name] = {'rows': rows, 'columns': columns, 'sha256_rows': digest.hexdigest()}
        print(f'{name}: {rows} rows')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--dsn', help='ODBC data source name configured with the HFSQL driver')
    source.add_argument('--connection-string', help='full ODBC connection string')
    parser.add_argument('--out', type=Path, required=True, help='new directory for CSV files and manifest.json')
    parser.add_argument('--table', action='append', help='export only these tables (repeatable)')
    args = parser.parse_args()
    import pyodbc
    args.out.mkdir(parents=True, exist_ok=False)
    connection = pyodbc.connect(args.connection_string or f'DSN={args.dsn}', autocommit=True, readonly=True)
    export(connection, args.out, args.table)


if __name__ == '__main__':
    main()
