import csv
from pathlib import Path
import sqlite3
import tempfile
import unittest

from helpers import load

module = load('scripts/data_profile.py')

SCHEMA = [
    {'table': 'Clientes', 'keys': [{'name': 'Codigo', 'columns': ['Codigo'], 'key': 'unique'}], 'columns': [
        {'name': 'Codigo', 'type': 'Unsigned 8-byte integer', 'size': '8'},
        {'name': 'Nome', 'type': 'String', 'size': '5'},
        {'name': 'Obs', 'type': 'Text Memo', 'size': '8'}]},
    {'table': 'Viaturas', 'keys': [{'name': 'Matricula', 'columns': ['Matricula'], 'key': 'unique'},
                                    {'name': 'MC', 'columns': ['Matricula', 'Cliente'], 'key': 'unique'}], 'columns': [
        {'name': 'Matricula', 'type': 'String', 'size': '10'},
        {'name': 'Cliente', 'type': 'Unsigned 8-byte integer', 'size': '8'},
        {'name': 'Ano', 'type': 'Unsigned 2-byte integer', 'size': '2'},
        {'name': 'Entrada', 'type': 'Date (yyyymmdd)', 'size': '8'},
        {'name': 'EstadoID', 'type': '8-byte integer', 'size': '8'},
        {'name': 'Ativo', 'type': 'Boolean', 'size': '1'}]},
    {'table': 'Estado', 'keys': [{'name': 'EstadoID', 'columns': ['EstadoID'], 'key': 'unique'}],
     'columns': [{'name': 'EstadoID', 'type': 'Automatic identifier (8 bytes)', 'size': '8'}]},
]


class DataProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)  # registered first, so it runs after the connections close
        self.db = Path(self.directory.name) / 'copy.sqlite'
        con = sqlite3.connect(self.db)
        con.execute('CREATE TABLE Clientes (Codigo TEXT, Nome TEXT, Obs TEXT)')
        con.executemany('INSERT INTO Clientes VALUES (?, ?, ?)',
                        [('1', 'Ana ', 'linha 1\r\nlinha 2 that is long'), ('2', 'Rui', ''), ('2', 'Eva', '')])
        con.execute('CREATE TABLE Viaturas (Matricula TEXT, Cliente TEXT, Ano TEXT, Entrada TEXT, EstadoID TEXT, '
                    'Ativo TEXT, ChaveComposta TEXT)')
        con.executemany('INSERT INTO Viaturas VALUES (?, ?, ?, ?, ?, ?, ?)', [
            ('AA-00-01', '1', '0', '20240131', '0', '1', 'AA\x00\x01'),
            ('BB-11-22', '9', '0', '', '0', '0', 'BB\x00\x02'),
            ('CC-22-33', '2', '2015', '20241301', '0', 'x', 'CC\x00\x03')])
        con.execute('CREATE TABLE Estado (EstadoID TEXT)')
        con.execute("INSERT INTO Estado VALUES ('1')")
        con.commit()
        con.close()

    def test_findings_keys_and_links(self):
        connection = module.load(self.db)
        self.addCleanup(connection.close)  # Windows cannot delete an open database file
        report = module.profile(connection, SCHEMA)
        notes = lambda table, column: ' '.join(report['tables'][table]['columns'][column]['findings'])
        self.assertIn('leading or trailing spaces', notes('Clientes', 'Nome'))
        self.assertNotIn('longer than', notes('Clientes', 'Obs'))  # a memo's size is not a length
        self.assertIn('line breaks', notes('Clientes', 'Obs'))
        self.assertIn('does 0 mean empty', notes('Viaturas', 'Ano'))
        self.assertIn('1 values do not parse', notes('Viaturas', 'Entrada'))  # month 13
        self.assertIn('empty strings in a Date', notes('Viaturas', 'Entrada'))
        self.assertIn('1 values do not parse as Boolean', notes('Viaturas', 'Ativo'))
        self.assertIn('one value in every row', notes('Viaturas', 'EstadoID'))
        composite = notes('Viaturas', 'ChaveComposta')
        self.assertIn('composite key exported as data', composite)
        self.assertNotIn('line breaks', composite)
        keys = {k['key']: k['duplicates'] for k in report['keys']}
        self.assertEqual(keys, {'Codigo': 1, 'Matricula': 0, 'MC': 0, 'EstadoID': 0})
        links = {l['from']: l for l in report['links']}
        self.assertEqual((links['Viaturas.Cliente']['to'], links['Viaturas.Cliente']['orphans']), ('Clientes.Codigo', 1))
        self.assertEqual(links['Viaturas.EstadoID']['zero'], 3)  # 0 = no link, not an orphan
        self.assertEqual(links['Viaturas.EstadoID']['orphans'], 0)
        page = module.markdown(report, 'copy.sqlite')
        self.assertIn('0 in every row — the link is not used', page)
        self.assertNotIn('Ana', page)  # no record values in the report

    def test_odbc_copy_with_bytes_and_iso_dates(self):
        db = Path(self.directory.name) / 'data.sqlite'
        con = sqlite3.connect(db)
        con.execute('CREATE TABLE Viaturas (Matricula, Cliente, Ano, Entrada, EstadoID, Ativo, Chave)')
        con.execute("INSERT INTO Viaturas VALUES ('AA', '1', '0', '2024-01-31', '0', '1', ?)", (b'CP\x00\x01',))
        con.execute('CREATE TABLE __export (key, value)')
        con.commit()
        con.close()
        connection = module.load(db)
        self.addCleanup(connection.close)
        report = module.profile(connection, SCHEMA)
        columns = report['tables']['Viaturas']['columns']
        self.assertEqual(columns['Entrada']['invalid'], 0)  # ISO 8601 from the exporter
        self.assertIn('composite key exported as data', ' '.join(columns['Chave']['findings']))
        self.assertNotIn('__export', report['tables'])

    def test_csv_folder_of_the_odbc_exporter(self):
        folder = Path(self.directory.name) / 'export'
        folder.mkdir()
        with (folder / 'Clientes.csv').open('w', newline='', encoding='utf-8') as handle:
            csv.writer(handle).writerows([['Codigo', 'Nome', 'Obs'], ['1', 'Ana', ''], ['x', 'Rui', '']])
        connection = module.load(folder)
        self.addCleanup(connection.close)
        report = module.profile(connection, SCHEMA)
        self.assertEqual(report['tables']['Clientes']['columns']['Codigo']['invalid'], 1)
        self.assertIn('Viaturas (whole table)', report['missing_columns'])


if __name__ == '__main__':
    unittest.main()
