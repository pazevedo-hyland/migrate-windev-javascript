import csv
import datetime
import decimal
import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

exporter = load('scripts/windows/export_odbc.py')


class FakeCursor:
    description = [('id', int, None, 8, 19, 0, False), ('name', str, None, 50, 50, 0, True),
                   ('price', decimal.Decimal, None, 8, 18, 6, True), ('day', datetime.date, None, 8, 8, 0, True)]

    def tables(self, tableType):
        return [type('Row', (), {'table_name': 'Clientes'})()]

    def execute(self, sql):
        self.sql = sql

    def __iter__(self):
        return iter([(1, 'Hélène', decimal.Decimal('12.500000'), datetime.date(2026, 1, 2)), (2, None, None, None)])


class ExporterTests(unittest.TestCase):
    def test_export_is_lossless_and_manifested(self):
        connection = type('Connection', (), {'cursor': lambda self: FakeCursor()})()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            manifest = exporter.export(connection, out)
            with (out / 'Clientes.csv').open(encoding='utf-8') as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows, [['id', 'name', 'price', 'day'], ['1', 'Hélène', '12.500000', '2026-01-02'],
                                    ['2', '', '', '']])
            self.assertEqual(manifest['tables']['Clientes']['rows'], 2)
            self.assertEqual(json.loads((out / 'manifest.json').read_text())['tables']['Clientes']['columns'][2]['scale'], 6)


if __name__ == '__main__':
    unittest.main()
