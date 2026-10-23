import csv
import datetime
import decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from helpers import load

exporter = load('scripts/windows/export_odbc.py')

RECORDS = [(1, 'Hélène', decimal.Decimal('12.500000'), datetime.date(2026, 1, 2), b'CP\x00\x01'),
           (2, None, None, None, None),
           (3, '', decimal.Decimal('0'), None, None)]


class FakeCursor:
    description = [('id', int, None, 8, 19, 0, False), ('name', str, None, 50, 50, 0, True),
                   ('price', decimal.Decimal, None, 8, 18, 6, True), ('day', datetime.date, None, 8, 8, 0, True),
                   ('key', bytes, None, 4, 4, 0, True)]

    def __init__(self, counted):
        self.counted = counted

    def tables(self, tableType):
        return [type('Row', (), {'table_name': 'Clientes'})()]

    def execute(self, sql):
        self.sql = sql

    def fetchone(self):
        return (self.counted,)

    def __iter__(self):
        return iter(RECORDS)


def connection(counted=3):
    cursor = FakeCursor(counted)
    return type('Connection', (), {'cursor': lambda self: cursor})()


class ExporterTests(unittest.TestCase):
    def test_export_is_lossless_and_manifested(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            manifest = exporter.export(connection(), out)
            with (out / 'Clientes.csv').open(encoding='utf-8') as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[1], ['1', 'Hélène', '12.500000', '2026-01-02', 'base64:Q1AAAQ=='])
            self.assertEqual(rows[2:], [['2', '', '', '', ''], ['3', '', '0', '', '']])  # CSV: NULL and '' look alike
            copy = sqlite3.connect(out / 'data.sqlite')
            stored = copy.execute('SELECT name, price, key FROM Clientes ORDER BY id').fetchall()
            copy.close()
            self.assertEqual(stored, [('Hélène', '12.500000', b'CP\x00\x01'), (None, None, None), ('', '0', None)])
            table = manifest['tables']['Clientes']
            self.assertEqual((table['rows'], table['count']), (3, 3))
            self.assertEqual([c['nulls'] for c in table['columns']], [0, 1, 1, 2, 2])
            self.assertEqual(table['columns'][4]['binary'], 1)
            self.assertEqual(json.loads((out / 'manifest.json').read_text())['tables']['Clientes']['columns'][2]['scale'], 6)

    def test_rows_short_of_count_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = exporter.export(connection(counted=4), Path(directory))
        self.assertEqual((manifest['tables']['Clientes']['rows'], manifest['tables']['Clientes']['count']), (3, 4))


if __name__ == '__main__':
    unittest.main()
