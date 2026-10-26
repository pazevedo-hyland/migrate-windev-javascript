import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from functional_acceptance import assess, assess_data, compatible_commit


class FunctionalAcceptanceChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'flow.spec.ts').write_text('test("save and reopen", realSave)\n')
        self.commit = 'a' * 40
        self.witness = {'file': 'flow.spec.ts', 'title': 'save and reopen'}
        self.data = {'version': 1, 'runs': {'mac': {
            'os': 'macOS arm64', 'commit': self.commit, 'commands': ['playwright test'],
            'checks': ['flow.spec.ts::save and reopen']}}, 'cases': [{
                'id': 'save', 'units': ['WIN_Example'], 'requirement': 'Save and reopen exact stored values.',
                'checks': [self.witness], 'status': 'verified',
                'evidence': [{'run': 'mac', 'os': 'macOS arm64', 'commit': self.commit}]}]}

    def evaluate(self, names=('WIN_Example',), compatible=True):
        return assess_data(self.data, names, self.root, compatible=lambda *_: compatible)

    def test_complete_executed_contract_passes_without_altering_its_input(self):
        before = copy.deepcopy(self.data)
        result = self.evaluate()
        self.assertEqual((result['passed'], result['total'], result['percent']), (1, 1, 100.0))
        self.assertEqual(result['units']['WIN_Example']['status'], 'verified')
        self.assertEqual(result['environments'], ['macOS arm64'])
        self.assertEqual(self.data, before)

    def test_omitting_a_screen_keeps_its_missing_scope_in_the_denominator(self):
        result = self.evaluate(('WIN_Example', 'WIN_Forgotten'))
        self.assertEqual((result['passed'], result['total'], result['percent']), (1, 2, 50.0))
        self.assertEqual(result['units']['WIN_Forgotten']['status'], 'pending')
        self.assertIn('not been scoped', result['cases'][1]['gap'])

    def test_pending_critical_workflow_keeps_all_its_units_open(self):
        self.data['cases'].append({'id': 'rollback', 'units': ['WIN_Example', 'WIN_Other'],
                                  'requirement': 'A refused save retains both original records.',
                                  'checks': [], 'status': 'pending', 'gap': 'Real failed-save proof is outstanding.'})
        result = self.evaluate(('WIN_Example', 'WIN_Other'))
        self.assertEqual((result['passed'], result['total']), (1, 2))
        self.assertTrue(all(u['status'] == 'pending' for u in result['units'].values()))

    def test_verified_without_executed_witness_or_with_a_different_test_title_is_rejected(self):
        for change in ('missing-evidence', 'missing-check', 'wrong-title', 'wrong-commit', 'wrong-os'):
            with self.subTest(change=change):
                before = copy.deepcopy(self.data)
                case = self.data['cases'][0]
                if change == 'missing-evidence':
                    case['evidence'] = []
                elif change == 'missing-check':
                    case['checks'] = []
                elif change == 'wrong-title':
                    case['checks'] = [{'file': 'flow.spec.ts', 'title': 'test was not executed'}]
                else:
                    case['evidence'][0]['commit' if change == 'wrong-commit' else 'os'] = 'other'
                with self.assertRaises(ValueError):
                    self.evaluate()
                self.data = before

    def test_modified_application_cannot_reuse_old_passes(self):
        result = self.evaluate(compatible=False)
        self.assertEqual((result['passed'], result['total']), (0, 1))
        self.assertIn('changed since', result['cases'][0]['gap'])
        self.assertEqual(self.data['cases'][0]['status'], 'verified')

    def test_platform_does_not_borrow_another_host_or_change_the_functional_denominator(self):
        self.data['platform'] = [{'id': 'mac-print', 'os': 'macOS arm64', 'units': ['WIN_Example'],
                                 'requirement': 'Actual native printing completes.', 'status': 'pending',
                                 'checks': [], 'gap': 'Printer check is not executed.'}]
        result = self.evaluate()
        self.assertEqual((result['passed'], result['total']), (1, 1))
        self.assertEqual(result['platform'][0]['status'], 'pending')
        self.data['platform'][0].update(os='Windows x64', status='verified', checks=[self.witness],
                                       evidence=self.data['cases'][0]['evidence'])
        with self.assertRaisesRegex(ValueError, 'another host'):
            self.evaluate()

    def test_unknown_units_duplicate_cases_and_external_test_files_are_rejected(self):
        before = copy.deepcopy(self.data)
        self.data['cases'][0]['units'] = ['WIN_NotInInventory']
        with self.assertRaises(ValueError):
            self.evaluate()
        self.data = copy.deepcopy(before)
        self.data['cases'].append(copy.deepcopy(self.data['cases'][0]))
        with self.assertRaises(ValueError):
            self.evaluate()
        self.data = before
        self.data['cases'][0]['checks'] = [{'file': '../outside.ts', 'title': 'save and reopen'}]
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_absent_ledger_reports_unassessed_instead_of_built_as_verified(self):
        result = assess(self.root, [{'name': 'WIN_Example', 'kind': 'screen', 'built': 99}], self.root)
        self.assertFalse(result['assessed'])
        self.assertEqual((result['passed'], result['total']), (0, 1))


class ApplicationCommitChecks(unittest.TestCase):
    def test_real_git_proof_survives_docs_changes_but_not_changed_or_untracked_application_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git('init')
            git('config', 'user.name', 'Synthetic test')
            git('config', 'user.email', 'synthetic@example.invalid')
            git('config', 'commit.gpgsign', 'false')
            (root / 'src').mkdir()
            app = root / 'src/app.ts'
            app.write_text('original application')
            git('add', 'src/app.ts')
            git('commit', '-m', 'synthetic baseline')
            commit = git('rev-parse', 'HEAD')
            self.assertTrue(compatible_commit(root, commit))
            (root / 'README.md').write_text('documentation only')
            git('add', 'README.md')
            git('commit', '-m', 'synthetic documentation')
            self.assertTrue(compatible_commit(root, commit))
            app.write_text('changed application')
            self.assertFalse(compatible_commit(root, commit))
            app.write_text('original application')
            new = root / 'src/new.ts'
            new.write_text('new application input')
            self.assertFalse(compatible_commit(root, commit))
            new.unlink()
            self.assertTrue(compatible_commit(root, commit))
            for path in ['docs/evidence/message-proposals.json', 'docs/evidence/ui-inputs.json',
                         'docs/golden/scenario.json', 'scripts/native-startup-probe.mjs', 'tests/flow.py']:
                file = root / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('initial test/runtime input')
                git('add', path)
                git('commit', '-m', 'synthetic input baseline')
                tested = git('rev-parse', 'HEAD')
                file.write_text('changed test/runtime input')
                self.assertFalse(compatible_commit(root, tested, ['tests/flow.py']))
                file.write_text('initial test/runtime input')
                self.assertTrue(compatible_commit(root, tested, ['tests/flow.py']))


if __name__ == '__main__':
    unittest.main()
