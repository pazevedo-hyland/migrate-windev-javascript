import contextlib
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from helpers import ROOT, load

converter = load('scripts/windows/hfsql_jsonl.py')

COLUMNS = [{'name': 'id', 'odbc_sql_type': 4, 'size': 10, 'scale': 0, 'nullable': False, 'type': 'str'},
           {'name': 'name', 'odbc_sql_type': 12, 'size': 50, 'scale': 0, 'nullable': True, 'type': 'str'},
           {'name': 'price', 'odbc_sql_type': 8, 'size': 15, 'scale': 0, 'nullable': True, 'type': 'str'},
           {'name': 'key', 'odbc_sql_type': -2, 'size': 4, 'scale': 0, 'nullable': True, 'type': 'bytes'}]
ROWS = [['1', 'Hélène', '12.5', {'base64': 'Q1AAAQ=='}], ['2', None, None, None], ['3', '', '0', None]]


def write_table(folder, name='Clientes', count=3, rows=ROWS, columns=COLUMNS):
    header = {'table': name, 'count': count, 'columns': columns, 'encoding': 'code page 1252 (windows-1252) via SQL_C_CHAR'}
    lines = [json.dumps(header)] + [json.dumps(row, ensure_ascii=False) for row in rows]
    (folder / f'{name}.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')


class HfsqlJsonlTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # Windows: a refused export may hold data.sqlite open
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / 'jsonl'
        self.source.mkdir()
        self.out = Path(temporary.name) / 'data'

    def convert(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return converter.convert(self.source, self.out)

    def test_output_matches_export_odbc_format(self):
        write_table(self.source)
        write_table(self.source, 'Empty', count=0, rows=[])
        manifest = self.convert()
        copy = sqlite3.connect(self.out / 'data.sqlite')
        stored = copy.execute('SELECT id, name, price, key FROM Clientes ORDER BY id').fetchall()
        embedded = json.loads(copy.execute("SELECT value FROM __export WHERE key = 'manifest'").fetchone()[0])
        copy.close()
        self.assertEqual(stored, [('1', 'Hélène', '12.5', b'CP\x00\x01'), ('2', None, None, None), ('3', '', '0', None)])
        with (self.out / 'Clientes.csv').open(encoding='utf-8', newline='') as handle:
            self.assertEqual(list(csv.reader(handle))[1], ['1', 'Hélène', '12.5', 'base64:Q1AAAQ=='])
        table = manifest['tables']['Clientes']
        self.assertEqual((table['rows'], table['count']), (3, 3))
        self.assertEqual([c['nulls'] for c in table['columns']], [0, 1, 1, 2])
        self.assertEqual(table['columns'][3]['binary'], 1)
        self.assertEqual(manifest['tables']['Empty']['rows'], 0)
        self.assertEqual(manifest['odbc_sql_types']['Clientes']['key'], -2)
        self.assertIn('windows-1252', manifest['encoding'])
        self.assertEqual(json.loads((self.out / 'manifest.json').read_text(encoding='utf-8')), embedded)

    def test_rows_short_of_the_source_count_fail_the_command(self):
        write_table(self.source, count=4)
        self.assertEqual(self.convert()['tables']['Clientes']['rows'], 3)
        main = converter.main
        import sys
        argv = sys.argv
        sys.argv = ['hfsql_jsonl.py', '--in', str(self.source), '--out', str(self.out.with_name('again'))]
        try:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stop:
                main()
        finally:
            sys.argv = argv
        self.assertIn('Clientes', str(stop.exception))

    def test_malformed_input_is_refused(self):
        cases = {
            'width': [['1', 'only two']],
            'number': [[1, 'x', '1', None]],
            'object': [['1', {'text': 'x'}, '1', None]],
        }
        for label, rows in cases.items():
            with self.subTest(label):
                for path in self.source.glob('*.jsonl'):
                    path.unlink()
                write_table(self.source, count=len(rows), rows=rows)
                out = self.out.with_name(label)
                with self.assertRaises(ValueError):
                    with contextlib.redirect_stdout(io.StringIO()):
                        converter.convert(self.source, out)

    def test_header_must_name_its_own_table_and_output_must_be_new(self):
        write_table(self.source)
        (self.source / 'Clientes.jsonl').rename(self.source / 'Other.jsonl')
        with self.assertRaises(ValueError):
            self.convert()
        (self.source / 'Other.jsonl').unlink()
        write_table(self.source)
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            self.convert()

    def test_powershell_export_keeps_its_safety_steps(self):
        # The export itself needs Windows and the HFSQL driver; pin the safety properties of the script text.
        script = (ROOT / 'scripts/windows/hfsql-export.ps1').read_text(encoding='utf-8')
        self.assertIn('[IntPtr]::Size -ne 4', script)  # 32-bit host only
        self.assertIn('Get-Sha256', script)  # hash-checked copy
        self.assertRegex(script, r'finally \{\s*if \(\$created\) \{ \$sources\.DeleteValue')  # DSN always deleted
        adapter = (ROOT / 'scripts/windows/HfSqlOdbcAnsi.cs').read_text(encoding='utf-8')
        self.assertIn('SQLDriverConnectA', adapter)
        self.assertNotRegex(adapter, r'SQL\w+W\(')  # no Unicode entry point


if __name__ == '__main__':
    unittest.main()
