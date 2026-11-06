import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from functional_acceptance import assess_data  # noqa: E402
from functional_cases import build, playwright_results, vitest_results  # noqa: E402

COMMIT = 'b' * 40
RUN = {'os': 'Windows 11 x64', 'commit': COMMIT, 'date': '2026-11-06', 'commands': ['npx vitest run', 'npx playwright test']}
ROWS = [
    # id, element, kind, status, test
    ('A-1', 'WIN_Orders', 'window', 'verified', 'src/orders.test.ts::orders > saves a line; ui-check/orders.flows.spec.ts::order form > saves'),
    ('A-2', 'WIN_Orders', 'window', 'implemented', 'src/orders.test.ts::not counted, implemented only'),
    ('B-1', 'WIN_Stock', 'window', 'verified', 'src/stock.test.ts::refuses negative stock'),
    ('C-1', 'RPT_Totals', 'report', 'verified', 'src/totals.test.ts::renamed since'),
    ('D-1', 'WIN_Empty', 'window', 'implemented', ''),
    ('E-1', 'TBL_Orders', 'table', 'verified', 'src/orders.test.ts::orders > saves a line'),
]


class FunctionalCasesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'docs/parity').mkdir(parents=True)
        with (self.root / 'docs/parity/parity.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(['id', 'element', 'kind', 'status', 'confidence', 'test'])
            writer.writerows([(i, e, k, s, 'verified', t) for i, e, k, s, t in ROWS])
        for name in ('src/orders.test.ts', 'src/stock.test.ts', 'src/totals.test.ts', 'ui-check/orders.flows.spec.ts'):
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text('// test\n', encoding='utf-8')
        vitest = {'testResults': [
            {'name': str(self.root / 'src/orders.test.ts'), 'assertionResults': [
                {'title': 'saves a line', 'ancestorTitles': ['orders'], 'status': 'passed'}]},
            {'name': str(self.root / 'src/stock.test.ts'), 'assertionResults': [
                {'title': 'refuses negative stock', 'ancestorTitles': [], 'status': 'failed'}]}]}
        playwright = {'config': {'rootDir': str(self.root / 'ui-check')}, 'suites': [
            {'title': 'orders.flows.spec.ts', 'file': 'orders.flows.spec.ts', 'specs': [], 'suites': [
                {'title': 'order form', 'specs': [{'title': 'saves', 'file': 'orders.flows.spec.ts',
                                                   'tests': [{'results': [{'status': 'failed'}, {'status': 'passed'}]}]}]}]}]}
        (self.root / 'vitest.json').write_text(json.dumps(vitest), encoding='utf-8')
        (self.root / 'playwright.json').write_text(json.dumps(playwright), encoding='utf-8')
        self.results = {**vitest_results(self.root / 'vitest.json', self.root),
                        **playwright_results(self.root / 'playwright.json', self.root)}

    def test_reports_are_read_with_describe_titles_and_last_retry(self):
        self.assertTrue(self.results['src/orders.test.ts::orders > saves a line'])
        self.assertTrue(self.results['src/orders.test.ts::saves a line'])
        self.assertFalse(self.results['src/stock.test.ts::refuses negative stock'])
        self.assertTrue(self.results['ui-check/orders.flows.spec.ts::order form > saves'])

    def test_one_case_per_screen_or_report_verified_only_when_all_cited_tests_passed(self):
        document = build(self.root, self.results, RUN)
        cases = {c['id']: c for c in document['cases']}
        self.assertEqual(sorted(cases), ['FC-RPT_Totals', 'FC-WIN_Empty', 'FC-WIN_Orders', 'FC-WIN_Stock'])  # no table case
        orders = cases['FC-WIN_Orders']
        self.assertEqual(orders['status'], 'verified')
        self.assertEqual(orders['evidence'], [{'run': 'full-suite', 'os': RUN['os'], 'commit': COMMIT}])
        self.assertEqual({(c['file'], c['title']) for c in orders['checks']},
                         {('src/orders.test.ts', 'orders > saves a line'), ('ui-check/orders.flows.spec.ts', 'order form > saves')})
        self.assertIn('failed', cases['FC-WIN_Stock']['gap'])
        self.assertEqual(cases['FC-WIN_Stock']['status'], 'pending')
        self.assertIn('absent from the run', cases['FC-RPT_Totals']['gap'])
        self.assertIn('cites a test', cases['FC-WIN_Empty']['gap'])
        # The validator accepts the generated file as is.
        result = assess_data(document, ['WIN_Orders', 'WIN_Stock', 'RPT_Totals', 'WIN_Empty'], self.root,
                             compatible=lambda *_: True)
        self.assertEqual((result['passed'], result['total']), (1, 4))

    def test_absent_cited_test_keeps_an_otherwise_passing_unit_pending(self):
        del self.results['ui-check/orders.flows.spec.ts::order form > saves']
        case = next(c for c in build(self.root, self.results, RUN)['cases'] if c['id'] == 'FC-WIN_Orders')
        self.assertEqual(case['status'], 'pending')

    def test_manual_cases_platform_and_their_runs_are_kept_others_replaced(self):
        previous = {'version': 1, 'decision': 'docs/decisions/010-acceptance.md',
                    'runs': {'manual': {**RUN, 'checks': ['src/orders.test.ts::orders > saves a line']},
                             'old': {**RUN, 'checks': []}},
                    'cases': [{'id': 'FC-WIN_Orders', 'status': 'pending'},
                              {'id': 'FA-print', 'units': ['WIN_Orders'], 'requirement': 'Prints.', 'status': 'verified',
                               'checks': [{'file': 'src/orders.test.ts', 'title': 'orders > saves a line'}],
                               'evidence': [{'run': 'manual', 'os': RUN['os'], 'commit': COMMIT}]}],
                    'platform': [{'id': 'win-print', 'os': RUN['os'], 'units': ['WIN_Orders'], 'requirement': 'Native print.',
                                  'status': 'pending', 'checks': [], 'gap': 'Printer check not executed.'}]}
        document = build(self.root, self.results, RUN, previous)
        self.assertEqual(sorted(document['runs']), ['full-suite', 'manual'])
        self.assertEqual([c['id'] for c in document['cases']].count('FC-WIN_Orders'), 1)
        self.assertIn('FA-print', [c['id'] for c in document['cases']])
        self.assertEqual(document['platform'], previous['platform'])
        self.assertEqual(document['decision'], previous['decision'])
        assess_data(document, ['WIN_Orders', 'WIN_Stock', 'RPT_Totals', 'WIN_Empty'], self.root, compatible=lambda *_: True)


if __name__ == '__main__':
    unittest.main()
