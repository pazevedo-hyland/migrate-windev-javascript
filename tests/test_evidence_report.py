import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/evidence_report.py')


def block(names, code, line=1):
    return {'context': {'names': names, 'siblings': {}}, 'code': code, 'start_line': line, 'end_line': line}


DIALOG = {'label': {'en-GB': 'Delete?', 'pt-PT': 'Apagar?'}, 'cancel_button': 1,
          'buttons': [{'label': {'pt-PT': 'Sim'}, 'value': 1}, {'label': {'pt-PT': 'Não'}, 'value': 2}]}


class EvidenceReportTests(unittest.TestCase):
    def test_nested_call_arguments(self):
        code = 'x = INIRead("db", "server", "", CompleteDir(fExeDir())+"servidor.ini")'
        self.assertEqual(module.arguments(code, code.index('(') + 1),
                         ['"db"', '"server"', '""', 'CompleteDir(fExeDir())+"servidor.ini"'])

    def test_caller_index_is_case_insensitive(self):
        used = {'Open': [('WIN_MENU', 10, 'win_sistema', 'WIN_MENU.wdw'), ('WIN_A', 5, 'WIN_Sistema', 'WIN_WIN_A.wdw')],
                'iPrintReport': [('WIN_A', 7, 'RPT_X', 'WIN_WIN_A.wdw')]}
        index = module.callers(used)
        self.assertEqual(index.get('WIN_sistema'), ['WIN_MENU.wdw:10 (Open in WIN_MENU)', 'WIN_WIN_A.wdw:5 (Open in WIN_A)'])
        self.assertEqual(index.get('rpt_x'), ['WIN_WIN_A.wdw:7 (iPrintReport in WIN_A)'])

    def test_encoded_actions_grouped_by_action_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'code').mkdir()
            for name, action in (('WIN_A', 'A-1'), ('WIN_B', 'A-1'), ('WIN_C', 'A-2')):
                (root / f'code/{name}.wdw.json').write_text(json.dumps({
                    'path': f'{name}.wdw', 'name': name, 'blocks': [], 'encoded_slots': [
                        {'names': [name, 'BTN_Fechar'], 'event': '18', 'line': 9, 'has_code': False, 'action': action},
                        {'names': [name, 'BTN_Ok'], 'event': '18', 'line': 20, 'has_code': True, 'action': 'A-3'}]}))
            groups = module.encoded_actions(root, None)
        self.assertEqual([(g['action'], len(g['slots'])) for g in groups], [('A-1', 2), ('A-2', 1)])
        self.assertEqual(groups[0]['slots'][0]['evidence'], 'WIN_A.wdw:9')

    def test_coverage_usage_and_grouped_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inspect/code').mkdir(parents=True)
            for name in ('WIN_A', 'WIN_B'):
                (root / f'inspect/code/{name}.wdw.json').write_text(json.dumps({
                    'path': f'{name}.wdw', 'name': name, 'dialogs': [DIALOG],
                    'layout': [{'name': 'BTN_Ok', 'kind': 'control', 'x': 0, 'y': 0, 'width': 10, 'height': 10},
                               {'name': 'EDT_X', 'kind': 'control', 'x': 0, 'y': 20, 'width': 10, 'height': 10}],
                    'blocks': [block([name, 'BTN_Ok'], 'iPrintReport(RPT_List)\nExeRun("tool.exe")')]}))
            (root / 'dossier/windev-window').mkdir(parents=True)
            (root / 'dossier/windev-window/win_a.json').write_text(json.dumps({'image_file': 'images/WIN_A.jpg', 'controls': {
                'BTN_Ok': {'kind': 'Button', 'caption': {'PT': 'Validar'}, 'row': 'Active Validate', 'raw': []}}}))
            (root / 'dossier/query').mkdir()
            (root / 'dossier/query/QRY_A.json').write_text(json.dumps({'sql': '', 'parameters': []}))
            rows, gaps = module.coverage(root / 'inspect', root / 'dossier', {'Clientes'})
            used = module.calls(root / 'inspect')
            questions = module.runtime_questions(root / 'inspect', root / 'dossier')
        self.assertIn('WIN_A: 1 controls without dossier description: EDT_X', gaps)  # case-insensitive match
        self.assertIn('WIN_B: no dossier entry (captions, tab order, masks unknown)', gaps)
        self.assertIn('QRY_A: query without SQL in the dossier', gaps)
        self.assertIn('Clientes: table without typed items in the dossier analysis', gaps)
        self.assertEqual({s[2] for s in used['ExeRun']}, {'"tool.exe"'})
        self.assertEqual(len([q for q in questions if q.startswith('Dialog "Apagar?"')]), 1)  # merged, pt-PT
        self.assertTrue(any('Validate button "Validar"' in q for q in questions))


if __name__ == '__main__':
    unittest.main()
