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
                field('Nascimento', '14'),  # the dossier missed this item: its type comes from the legend? no: no pair
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
        self.assertIsNone(columns['Nascimento']['sqlite'])  # code 14 never paired with a name: unresolved, not guessed
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


if __name__ == '__main__':
    unittest.main()
