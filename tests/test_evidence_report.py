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

    def test_navigation_map_from_call_sites(self):
        index = {'WIN_Form': ['WIN_List.wdw:30 (Open in WIN_List)'], 'RPT_List': ['WIN_List.wdw:41 (iPrintReport in WIN_List)'],
                 'WIN_List': ['WIN_MENU.wdw:9 (Open in WIN_MENU)']}
        rows = [{'element': n, 'kind': k} for n, k in (('WIN_MENU', 'window'), ('WIN_List', 'window'), ('WIN_Form', 'window'),
                                                       ('RPT_List', 'report'), ('RPT_Orphan', 'report'))]
        text = module.navigation(index, rows, 'WIN_MENU')
        self.assertIn('START(( )) --> WIN_MENU', text)
        self.assertIn('WIN_List[WIN_List] -->|iPrintReport| RPT_List[/RPT_List/]', text)
        self.assertIn('- RPT_Orphan (report)', text)
        compiled = module.navigation({'RPT_X': ['WIN_List (named in its compiled code: predefined action or dynamic call)']},
                                     rows + [{'element': 'RPT_X', 'kind': 'report'}], 'WIN_MENU')
        self.assertIn('WIN_List[WIN_List] -.->|compiled| RPT_X[/RPT_X/]', compiled)
        self.assertNotIn('- WIN_MENU', text)  # the first window is reached at startup

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
        # Largest first; slots next to code are grouped too, and marked.
        self.assertEqual([(g['action'], len(g['slots'])) for g in groups], [('A-3', 3), ('A-1', 2), ('A-2', 1)])
        self.assertTrue(all(s['has_code'] for s in groups[0]['slots']))
        self.assertEqual(groups[1]['slots'][0]['evidence'], 'WIN_A.wdw:9')

    def test_coverage_usage_and_grouped_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inspect/code').mkdir(parents=True)
            for name in ('WIN_A', 'WIN_B'):
                (root / f'inspect/code/{name}.wdw.json').write_text(json.dumps({
                    'path': f'{name}.wdw', 'name': name, 'dialogs': [DIALOG],
                    'layout': [{'name': 'BTN_Ok', 'kind': 'control', 'x': 0, 'y': 0, 'width': 10, 'height': 10},
                               {'name': 'EDT_X', 'kind': 'control', 'x': 0, 'y': 20, 'width': 10, 'height': 10}],
                    'blocks': [block([name, 'BTN_Ok'], 'iPrintReport(RPT_List)\nExeRun("tool.exe")\nInfo("Feito")')]}))
            (root / 'dossier/windev-window').mkdir(parents=True)
            (root / 'dossier/windev-window/win_a.json').write_text(json.dumps({'image_file': 'images/WIN_A.jpg', 'controls': {
                'BTN_Ok': {'kind': 'Button', 'caption': {'PT': 'Validar'}, 'row': 'Active Validate', 'raw': []}}}))
            (root / 'dossier/query').mkdir()
            (root / 'dossier/query/QRY_A.json').write_text(json.dumps({'sql': '', 'parameters': []}))
            rows, gaps = module.coverage(root / 'inspect', root / 'dossier', {'Clientes'})
            used = module.calls(root / 'inspect')
            questions = module.runtime_questions(root / 'inspect', root / 'dossier', 'pt-PT')
        self.assertIn('WIN_A: 1 controls without dossier description: EDT_X', gaps)  # case-insensitive match
        self.assertIn('WIN_B: no dossier entry (captions, tab order, masks unknown)', gaps)
        self.assertIn('QRY_A: query without SQL in the dossier', gaps)
        self.assertIn('Clientes: table without typed items in the dossier analysis', gaps)
        self.assertEqual({s[2] for s in used['ExeRun']}, {'"tool.exe"'})
        asked = dict(questions)
        dialog = [q for q in asked if q.startswith('Dialog "Apagar?"')]
        self.assertEqual(len(dialog), 1)  # merged, pt-PT
        self.assertEqual(asked[dialog[0]]['answer'], '"Não"')  # every question carries a proposal
        self.assertIn('Message boxes (Info ×2)', ' '.join(asked))  # one question for every box
        validate = next(q for q in asked if 'Validate button "Validar"' in q)
        self.assertEqual(asked[validate]['answer'], 'stays open')

    def test_proposals_from_names_code_and_compiled_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'code').mkdir()
            (root / 'code/WIN_T.wdw.json').write_text(json.dumps({'path': 'WIN_T.wdw', 'name': 'WIN_T', 'blocks': [
                block(['WIN_T', 'BTN_Pick'], 'MyWindow..ReturnedValue = 1'),
                block(['WIN_T', 'BTN_Done'], 'close(WIN_T)')], 'encoded_slots': [
                {'names': ['WIN_T', 'SC', 'BTN_SYST_FERMER'], 'event': '18', 'line': 1, 'has_code': False, 'action': 'A-1'},
                {'names': ['WIN_T', 'BTN_Sair'], 'event': '18', 'line': 2, 'has_code': False, 'action': 'A-1'},
                {'names': ['WIN_T', 'BTN_Pick'], 'event': '18', 'line': 3, 'has_code': True, 'action': 'A-2'},
                {'names': ['WIN_T', 'BTN_Print'], 'event': '18', 'line': 4, 'has_code': False, 'action': 'A-3'},
                {'names': ['WIN_T', 'BTN_Other'], 'event': '18', 'line': 5, 'has_code': False, 'action': 'A-4'}]}))
            actions = module.propose_actions(module.encoded_actions(root, None), root, module.CaseInsensitive({'WIN_T': ['RPT_T']}), True)
            proposed = {a['action']: a['proposal']['answer'] for a in actions}
            data = json.loads((root / 'code/WIN_T.wdw.json').read_text())
            data['encoded_slots'].pop()
            (root / 'code/WIN_T.wdw.json').write_text(json.dumps(data))
            alone = module.propose_actions(module.encoded_actions(root, None), root, module.CaseInsensitive({'WIN_T': ['RPT_T']}), True)
        self.assertTrue(next(a for a in alone if a['action'] == 'A-3')['proposal']['answer'].startswith('Print RPT_T'))
        self.assertEqual(proposed['A-1'], 'Close the window')  # BTN_Sair shares the template close button's action
        self.assertTrue(proposed['A-2'].startswith('Close the window after the code'))
        # Two unexplained controls and one uncalled report: which one prints it is not known.
        self.assertTrue(proposed['A-3'].startswith('Nothing') and proposed['A-4'].startswith('Nothing'))
        self.assertEqual(module.control_code({'blocks': [block(['WIN_T', 'btn_done'], 'close(WIN_T)')]}, 'BTN_Done'),
                         'close(WIN_T)')


if __name__ == '__main__':
    unittest.main()
