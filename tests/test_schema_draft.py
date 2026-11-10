import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from helpers import load

module = load('scripts/schema_draft.py')


def field(name, code, key='0', size='8', default='', composite=None):
    if composite:
        parts = ''.join(f'<COMPOSANTE Nom="{c}">0</COMPOSANTE>' for c in composite)
        return {'attributes': {'Nom': name}, 'raw_metadata': f'<RUBRIQUE Nom="{name}"><TYPE_CLE>{key}</TYPE_CLE><COMPOSEE>0{parts}</COMPOSEE></RUBRIQUE>'}
    return {'attributes': {'Nom': name}, 'raw_metadata': (
        f'<RUBRIQUE Nom="{name}"><TYPE>{code}</TYPE><TYPE_CLE>{key}</TYPE_CLE><TAILLE>{size}</TAILLE>'
        f'<INDICERUBRIQUE Indice="0" Null="0" Valeur="{default}" RubNullSupporte="1">0</INDICERUBRIQUE></RUBRIQUE>')}


class SchemaDraftTests(unittest.TestCase):
    def test_type_legend_ddl_and_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inspect/schema').mkdir(parents=True)
            (root / 'dossier/analysis').mkdir(parents=True)
            (root / 'inspect/schema/App.xdd.json').write_text(json.dumps({'tables': [{'attributes': {'Nom': 'Clientes'}, 'fields': [
                field('ClientesID', '24', key='1'), field('Codigo', '27', key='1', default='0'),
                field('Nome', '2', key='2', size='100'), field('Saldo', '41'), field('Ativo', '37', size='1'),
                field('Nascimento', '99'),  # the dossier missed this item and no dossier ever named code 99
                field('Hora', '11'),        # not in this dossier either, but named by the built-in table
                field('CodigoNome', None, key='2', composite=['Codigo', 'Nome'])]}]}))
            (root / 'dossier/analysis/App.wda.json').write_text(json.dumps({'files': {'Clientes': {'items': [
                {'name': 'ClientesID', 'type': 'Automatic identifier (8 bytes)'},
                {'name': 'Codigo', 'type': 'Unsigned 8-byte integer', 'caption': 'Código'},
                {'name': 'Nome', 'type': 'String'}, {'name': 'Saldo', 'type': 'Decimal'},
                {'name': 'Ativo', 'type': 'Boolean'}]}}}))
            data = module.draft(root / 'inspect', root / 'dossier')
        self.assertEqual(data['type_legend']['27'], 'Unsigned 8-byte integer')
        columns = {c['name']: c for c in data['tables'][0]['columns']}
        self.assertIn('2^53', columns['Codigo']['decision'])
        self.assertIn('decimal', columns['Saldo']['decision'])
        self.assertIsNone(columns['Nascimento']['sqlite'])  # code 99 never paired with a name: unresolved, not guessed
        self.assertEqual((columns['Hora']['type'], data['built_in_codes'], data['unnamed_codes']), ('Time (hhmm)', ['11'], ['99']))
        self.assertEqual(data['tables'][0]['keys'][-1], {'name': 'CodigoNome', 'columns': ['Codigo', 'Nome'], 'key': 'duplicates'})
        sql = module.ddl(data)
        connection = sqlite3.connect(':memory:')
        connection.executescript(sql)
        connection.execute('INSERT INTO Clientes (Codigo, Nome, Ativo) VALUES (1, "a", 1)')
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute('INSERT INTO Clientes (Codigo, Nome, Ativo) VALUES (1, "b", 0)')  # unique key kept
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute('INSERT INTO Clientes (Codigo, Ativo) VALUES (2, 5)')  # Boolean check
        self.assertIn('unresolved', module.markdown(data))

    def test_without_an_xdd_the_structure_comes_from_the_analysis_file(self):
        item = lambda name, code, size, order, **more: {'name': name, 'caption': name.title(), 'type_code': code, 'size': size,
                                                         'key': None, 'position': order, 'order': order, **more}
        tables = [{'name': 'Clientes', 'items': [
            item('Saldo', 41, 7, 2, decimals=6, integer_digits=10, default='0'), item('Codigo', 27, 8, 0, key='unique'),
            item('Nome', 2, 100, 1, key='duplicates', key_options_code=7, key_compares='ignores case, accents, spaces and punctuation'),
            item('Velho', 2, 5, 3, deleted=True),
            item('CodigoNome', 28, 108, 4, key='unique', parts=['Codigo', 'Nome'])]},
            {'name': 'Apagada', 'deleted': True, 'items': [item('x', 2, 5, 0)]}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inspect').mkdir()
            (root / 'decoded').mkdir()
            (root / 'decoded/analysis.json').write_text(json.dumps({'tables': tables, 'records': []}))
            data = module.draft(root / 'inspect', None, root / 'decoded')
        self.assertEqual((data['source'], [t['table'] for t in data['tables']]), ('analysis file', ['Clientes']))
        columns = data['tables'][0]['columns']
        self.assertEqual([(c['name'], c['code'], c['size'], c['key'], c['caption'], c['nullable']) for c in columns],
                         [('Codigo', '27', '8', 'unique', 'Codigo', None), ('Nome', '2', '100', 'duplicates', 'Nome', None),
                          ('Saldo', '41', '7', None, 'Saldo', None)])
        self.assertEqual((columns[2]['scale'], columns[2]['integer_digits'], columns[2]['default']), (6, 10, '0'))
        self.assertIn('10 integer digits and 6 decimals', columns[2]['decision'])
        self.assertEqual(data['tables'][0]['keys'][-1], {'name': 'CodigoNome', 'columns': ['Codigo', 'Nome'], 'key': 'unique'})
        text, sql = module.markdown(data), module.ddl(data)
        self.assertIn('this project has no XDD', text)
        self.assertIn('Decimal (10+6 digits)', text)
        self.assertIn('Null support is not read from the analysis file (3 items)', text)
        self.assertNotIn('NOT NULL', sql)
        self.assertIn('1 of the 1 text keys ignore case and accents', text)
        self.assertIn('- Clientes.Nome: duplicates on (Nome): ignores case, accents, spaces and punctuation', text)
        self.assertIn('ON "Clientes" ("Nome");  -- HFSQL ignores case, accents, spaces and punctuation on this key', sql)
        sqlite3.connect(':memory:').executescript(sql)


if __name__ == '__main__':
    unittest.main()
