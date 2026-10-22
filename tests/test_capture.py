import csv
import datetime
import decimal
import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

planner = load('scripts/plan_capture.py')
crawler = load('scripts/windows/capture_app.py')
exporter = load('scripts/windows/export_odbc.py')


def block(names, event, code, line=1):
    return {'context': {'names': names, 'siblings': {'type': event} if event else {}},
            'code': code, 'start_line': line, 'end_line': line + 1}


def write_inspection(root, files):
    for path, blocks in files.items():
        target = root / 'code' / (path + '.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'path': path, 'blocks': blocks}), encoding='utf-8')


class PlannerTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(planner.classify('SWITCH WinStatus(WIN_A)\nCASE Active\n Restore(WIN_A)\nOTHER CASE\n Open(WIN_A)\nEND'), 'navigation')
        self.assertEqual(planner.classify('// comment\nopenchild(WIN_F,"resumo")'), 'navigation')
        self.assertEqual(planner.classify('HReset(Clientes)\nOpen(WIN_Form)'), 'review')
        for code in ('HAdd(Clientes)', 'EndProgram()', 'HExecuteSQLQuery(q, "delete from x")', 'iPrintReport(RPT_A)'):
            self.assertEqual(planner.classify(code), 'writes', code)
        self.assertEqual(planner.classify('HExecuteQuery(QRY_insert_x)', ['QRY_insert_x']), 'writes')

    def test_plan_levels_and_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_inspection(root, {
                'WIN_MENU.wdw': [block(['WIN_MENU'], '34', 'HAdd(sistema)'),
                                 block(['WIN_MENU', 'MENU', 'OPT_Tabelas', 'OPT_Clientes'], '32', 'Open(WIN_Table)'),
                                 block(['WIN_MENU', 'BTN_Tempos'], '18', 'Open(WIN_Tempos)'),
                                 block(['WIN_MENU', 'OPT_Fix'], '32', 'HModify(x)\nOpen(WIN_Fix)')],
                'WIN_Table.wdw': [block(['WIN_Table'], None, 'PROCEDURE MyWindow()'),
                                  block(['WIN_Table', 'BTN_New'], '18', 'HReset(Clientes)\nOpen(WIN_Form)')],
                'WIN_Form.wdw': [block(['WIN_Form'], '34', 'FileToScreen()')],
                'WIN_Tempos.wdw': [block(['WIN_Tempos'], '34', 'HModify(sistema)')],
                'WIN_Fix.wdw': [block(['WIN_Fix'], None, 'x = 1')],
                'WIN_Orphan.wdw': [block(['WIN_Orphan'], None, 'x = 1')],
            })
            result = planner.plan(root)
        levels = {w['window']: w['capture'] for w in result['windows']}
        self.assertEqual(levels, {'WIN_Fix': 'manual', 'WIN_Form': 'auto-review', 'WIN_MENU': 'unreachable',
                                  'WIN_Orphan': 'unreachable', 'WIN_Table': 'auto', 'WIN_Tempos': 'manual'})
        self.assertIn('Totals:', planner.checklist(result))
        safe = crawler.routes(result, 'WIN_MENU')
        self.assertEqual(list(safe), ['WIN_Table'])
        self.assertEqual(crawler.menu_steps(safe['WIN_Table'][0]['path']), ['OPT_Tabelas', 'OPT_Clientes'])
        reviewed = crawler.routes(result, 'WIN_MENU', allow_review=True)
        self.assertEqual([e['control'] for e in reviewed['WIN_Form']], ['OPT_Clientes', 'BTN_New'])


class CrawlerLogicTests(unittest.TestCase):
    def test_matching_prefers_id_and_refuses_ambiguity(self):
        elements = [('A', 'Estados descritivos', ''), ('B', 'Estados de Reparação', ''), ('C', 'Novo', 'BTN_New')]
        self.assertEqual(crawler.best_match('OPT_Estados_de_Reparação', elements), 'B')
        self.assertEqual(crawler.best_match('Btn_New', elements), 'C')
        self.assertIsNone(crawler.best_match('OPT_Estados', elements[:2]))
        self.assertIsNone(crawler.best_match('BTN_Unknown', elements))

    def test_layout_matching_on_real_login_geometry(self):
        # Positions observed on a real WINDEV 28 login window (relative to the window) and its .wdw layout.
        elements = [(1, (192, 229, 350, 271)), (2, (28, 229, 186, 271)), (3, (290, 74, 350, 114)),
                    (6, (28, 167, 350, 207)), (7, (28, 75, 284, 115)), (12, (330, 0, 374, 19)), (9, (0, 0, 5, 5))]
        layout = [{'name': 'EDT_utilizador', 'x': 28, 'y': 75, 'width': 256, 'height': 40},
                  {'name': 'EDT_palavra_passe', 'x': 28, 'y': 167, 'width': 322, 'height': 40},
                  {'name': 'BTN_NoName1', 'x': 290, 'y': 74, 'width': 60, 'height': 40},
                  {'name': 'BTN_Confirmar', 'x': 28, 'y': 229, 'width': 158, 'height': 42},
                  {'name': 'BTN_Cancelar', 'x': 192, 'y': 229, 'width': 158, 'height': 42},
                  {'name': 'BTN_SYST_FERMER', 'x': 330, 'y': 0, 'width': 44, 'height': 19},
                  {'name': 'RADTitle', 'x': 9, 'y': 4, 'width': None, 'height': None}]
        self.assertEqual(crawler.match_layout(elements, layout),
                         {1: 'BTN_Cancelar', 2: 'BTN_Confirmar', 3: 'BTN_NoName1', 6: 'EDT_palavra_passe',
                          7: 'EDT_utilizador', 12: 'BTN_SYST_FERMER'})

    def test_best_layout_identifies_the_window(self):
        positions = [(0, (28, 75, 284, 115)), (1, (290, 74, 350, 114)), (2, (28, 229, 186, 271))]
        login = [{'name': 'EDT_u', 'x': 28, 'y': 75, 'width': 256, 'height': 40},
                 {'name': 'BTN_dots', 'x': 290, 'y': 74, 'width': 60, 'height': 40},
                 {'name': 'BTN_ok', 'x': 28, 'y': 229, 'width': 158, 'height': 42}]
        other = [{'name': 'BTN_ok', 'x': 28, 'y': 229, 'width': 158, 'height': 42}]
        self.assertEqual(crawler.best_layout(positions, {'win_acesso': login, 'win_other': other}), 'win_acesso')
        self.assertIsNone(crawler.best_layout(positions[:2], {'win_other': other}))

    def test_data_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Clientes.fic').write_bytes(b'a')
            (root / 'notes.txt').write_text('ignored')
            before = crawler.data_files(root)
            (root / 'Clientes.fic').write_bytes(b'b')
            (root / 'New.NDX').write_bytes(b'c')
            self.assertEqual(crawler.changed(before, crawler.data_files(root)), ['Clientes.fic', 'New.NDX'])


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
