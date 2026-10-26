import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from progress_dashboard import chart, history, matrix_rows, render, summarize


class PlatformVisualProgressChecks(unittest.TestCase):
    def summary_and_page(self, docs):
        rows = [{'element': 'WIN_Form_Example', 'kind': 'window', 'status': 'implemented'}]
        units = summarize(rows, docs)
        page = render(units, {'decisions_pending': [], 'answer_sheet_open': 0,
                              'answer_sheet_done': 0, 'unresolved_items': 0}, [], [], 'Example', 'fixed')
        return units[0], page

    def record(self, docs, platform, pixel, layout, date):
        directory = docs / 'evidence' / 'visual'
        if platform == 'darwin':
            directory /= 'darwin'
        directory.mkdir(parents=True, exist_ok=True)
        filename = directory / 'WIN_Form_Example.json'
        filename.write_text(json.dumps({'pixel_similarity': pixel, 'edge_overlap': layout, 'date': date}), encoding='utf-8')
        return filename

    def test_darwin_only_measurement_is_visible_and_labelled_without_inventing_windows_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            docs = Path(temporary)
            filename = self.record(docs, 'darwin', 98.9, 96.7, '2026-10-25')
            before = filename.read_bytes()
            unit, page = self.summary_and_page(docs)
            self.assertIsNone(unit['looks'])
            self.assertEqual(unit['visuals'], {'darwin': {'pixel': 98.9, 'layout': 96.7}})
            self.assertIn('macOS 96.7 %', page)
            self.assertIn('pixel similarity 98.9 %', page)
            self.assertNotIn('Windows 96.7', page)
            self.assertEqual(filename.read_bytes(), before)
            self.assertEqual(unit['statuses']['implemented'], 1)
            self.assertEqual(unit['done'], 0)

    def test_both_histories_remain_separate_in_fixed_order_and_legacy_looks_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            docs = Path(temporary)
            # Create the newer/higher-scoring Mac record first: neither date, score nor file order wins.
            mac = self.record(docs, 'darwin', 99.1, 97.2, '2026-10-25')
            windows = self.record(docs, 'windows', 94.5, 88.4, '2026-10-24')
            before = {filename: filename.read_bytes() for filename in (mac, windows)}
            unit, page = self.summary_and_page(docs)
            self.assertEqual(unit['looks'], {'pixel': 94.5, 'layout': 88.4})
            self.assertEqual(list(unit['visuals']), ['windows', 'darwin'])
            self.assertEqual(unit['visuals'], {'windows': {'pixel': 94.5, 'layout': 88.4},
                                             'darwin': {'pixel': 99.1, 'layout': 97.2}})
            self.assertIn('Windows 88.4 %', page)
            self.assertIn('macOS 97.2 %', page)
            self.assertLess(page.index('Windows 88.4 %'), page.index('macOS 97.2 %'))
            self.assertEqual({filename: filename.read_bytes() for filename in before}, before)

    def test_missing_histories_stay_unmeasured_without_altering_behavior_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            unit, page = self.summary_and_page(Path(temporary))
            self.assertIsNone(unit['looks'])
            self.assertEqual(unit['visuals'], {})
            self.assertIn('<td class="visual">–</td>', page)
            self.assertEqual(unit['stage'], 'built')
            self.assertEqual((unit['done'], unit['total']), (0, 1))


class BuiltAndProvenProgressChecks(unittest.TestCase):
    def summary(self, statuses):
        with tempfile.TemporaryDirectory() as temporary:
            return summarize([{'element': 'WIN_Example', 'kind': 'window', 'status': status}
                              for status in statuses], Path(temporary))[0]

    def test_built_excludes_decisions_while_strict_completion_keeps_them(self):
        unit = self.summary(['implemented', 'implemented', 'verified', 'excluded', 'specified', 'unmapped'])
        self.assertEqual((unit['built'], unit['built_percent'], unit['proven'], unit['excluded']), (3, 50.0, 1, 1))
        self.assertEqual((unit['done'], unit['total'], unit['stage']), (2, 6, 'building'))
        page = render([unit], {'decisions_pending': ['pending-choice'], 'answer_sheet_open': 8,
                              'answer_sheet_done': 2, 'unresolved_items': 4},
                      [('2026-10-24', 20.0, 6), ('2026-10-25', 30.0, 6)], [], 'Example', 'fixed')
        self.assertIn('<div class="hero"><div class="pct">—</div>', page)
        self.assertIn('<div class="big">50.0%</div><div>implementation coverage</div>', page)
        self.assertIn('3 of 6 behaviors · 2 built, awaiting proof · 1 approved exclusions outside the built count', page)
        self.assertIn('<div class="big">16.7%</div><div>strict behavior verification</div>', page)
        self.assertIn('<div class="big">33.3%</div><div>strict completion</div>', page)
        self.assertIn('2/6 verified + approved exclusions (1 excluded)', page)
        self.assertIn('3/6 built', page)
        self.assertIn('1/6 proven', page)
        self.assertIn('1 excluded</div>', page)
        self.assertIn('pending-choice', page)
        self.assertIn('2 answered · 4 open points', page)
        self.assertNotIn('rebuilt <b>and proven</b>', page)

    def test_fully_built_is_a_separate_stage_and_unknown_rows_do_not_close_it(self):
        cases = [(['implemented'], 'built'),
                 (['implemented', 'verified', 'excluded'], 'built'),
                 (['implemented', 'specified'], 'building'),
                 (['verified', 'unmapped'], 'building'),
                 (['implemented', 'excluded', 'unmapped'], 'building'),
                 (['verified', 'excluded'], 'done'),
                 (['excluded'], 'done')]
        for statuses, expected in cases:
            with self.subTest(statuses=statuses):
                unit = self.summary(statuses)
                self.assertEqual(unit['stage'], expected)
                self.assertEqual(unit['built'], statuses.count('implemented') + statuses.count('verified'))
                self.assertEqual(unit['done'], statuses.count('verified') + statuses.count('excluded'))
        unit = self.summary(['implemented', 'excluded'])
        self.assertEqual(unit['built_percent'], 50.0)

    def test_excluded_only_and_empty_matrices_never_report_built_work(self):
        unit = self.summary(['excluded'])
        self.assertEqual((unit['built'], unit['built_percent'], unit['proven']), (0, 0.0, 0))
        questions = {'decisions_pending': [], 'answer_sheet_open': 0,
                     'answer_sheet_done': 0, 'unresolved_items': 0}
        page = render([unit], questions, [], [], 'Example', 'fixed')
        self.assertIn('<div class="hero"><div class="pct">—</div>', page)
        self.assertIn('<div class="big">0.0%</div><div>implementation coverage</div>', page)
        self.assertIn('<div class="big">100.0%</div><div>strict completion</div>', page)
        empty = render([], questions, [], [], 'Example', 'fixed')
        self.assertIn('<div class="hero"><div class="pct">—</div>', empty)
        self.assertIn('0 of 0 behaviors', empty)

    def test_history_retains_original_strict_values_and_correctly_labels_exclusions(self):
        original_points = [('2026-10-24', 20.0, 10), ('2026-10-25', 30.0, 10)]
        graphic = chart(original_points)
        self.assertIn('points="10.0,106.0 630.0,94.0"', graphic)
        self.assertIn('strict completion over time: verified plus approved exclusions', graphic)
        self.assertIn('2026-10-25 · 30.0%', graphic)
        self.assertNotIn('verified share over time', graphic)
        self.assertEqual(original_points, [('2026-10-24', 20.0, 10), ('2026-10-25', 30.0, 10)])

    def test_aggregate_and_seed_behavior_identity_rules_are_unchanged(self):
        header = 'id,element,context,event,status\n'
        rows = matrix_rows({
            'parity.csv': header + 'current,WIN_Example,WIN_Example/button,18,implemented\n',
            'WIN_Example.csv': header + 'current,WIN_Example,WIN_Example/button,18,verified\n',
            'parity-seed.csv': header + 'old,WIN_Example,WIN_Example/button,18,specified\n'
                                      'missing,WIN_Example,WIN_Example/other,18,unmapped\n',
        })
        self.assertEqual([(row['id'], row['status']) for row in rows],
                         [('current', 'implemented'), ('missing', 'unmapped')])

    def test_history_reads_only_the_authoritative_aggregate_when_it_exists(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            header = 'id,element,context,event,status\n'
            files = {'docs/parity/parity.csv': header + 'one,WIN_A,WIN_A/a,18,verified\n',
                     'docs/parity/parity-seed.csv': header + 'two,WIN_A,WIN_A/b,18,unmapped\n',
                     'docs/parity/WIN_A.csv': header + 'one,WIN_A,WIN_A/a,18,implemented\n'}
            def git_result(_root, *args):
                if args[0] == 'rev-parse':
                    return str(root)
                if args[0] == 'log':
                    return 'abc 2026-10-26T10:00:00+00:00'
                if args[0] == 'ls-tree':
                    return '\n'.join(files)
                return files[args[1].partition(':')[2]]
            with patch('progress_dashboard.git', side_effect=git_result) as calls:
                self.assertEqual(history(root, root / 'docs/parity'), [('2026-10-26', 50.0, 2)])
            shown = [c.args[2] for c in calls.call_args_list if c.args[1] == 'show']
            self.assertEqual(shown, ['abc:docs/parity/parity.csv', 'abc:docs/parity/parity-seed.csv'])

    def test_target_defaults_do_not_hide_unconfirmed_source_behavior(self):
        with tempfile.TemporaryDirectory() as temporary:
            rows = [{'element': 'WIN_Example', 'kind': 'window', 'status': status, 'confidence': confidence}
                    for status, confidence in [('implemented', 'unresolved'), ('unmapped', 'unresolved'),
                                               ('verified', 'verified'), ('excluded', 'unresolved')]]
            unit = summarize(rows, Path(temporary))[0]
        self.assertEqual((unit['built'], unit['proven'], unit['source_unresolved'], unit['built_on_defaults']),
                         (2, 1, 3, 1))
        page = render([unit], {'decisions_pending': [], 'answer_sheet_open': 0,
                              'answer_sheet_done': 0, 'unresolved_items': 0}, [], [], 'Example', 'fixed')
        self.assertIn('<div class="big">1</div><div>built using target defaults</div>', page)
        self.assertIn('3 source behaviors still unconfirmed', page)
        self.assertIn('1/4 proven', page)


class FunctionalReadinessProgressChecks(unittest.TestCase):
    def test_functional_proof_is_primary_without_promoting_unknown_source_or_native_hosts(self):
        from functional_acceptance import assess_data
        with tempfile.TemporaryDirectory() as temporary:
            docs = Path(temporary)
            (docs / 'flow.ts').write_text('actual test fixture')
            rows = [{'element': 'WIN_Example', 'kind': 'window', 'status': 'implemented',
                     'confidence': 'unresolved'}]
            units = summarize(rows, docs)
            commit = 'a' * 40
            data = {'version': 1, 'runs': {'actual': {'os': 'macOS arm64', 'commit': commit,
                     'commands': ['actual fixture command'], 'checks': ['flow.ts::save and reopen']}},
                    'cases': [{'id': 'save', 'units': ['WIN_Example'], 'requirement': 'Save and reopen.',
                               'status': 'verified', 'checks': [{'file': 'flow.ts', 'title': 'save and reopen'}],
                               'evidence': [{'run': 'actual', 'os': 'macOS arm64', 'commit': commit}]}],
                    'platform': [{'id': 'windows-print', 'os': 'Windows x64', 'units': ['WIN_Example'],
                                  'requirement': 'Native print.', 'status': 'pending', 'checks': [],
                                  'gap': 'Windows printer check not run.'}]}
            functional = assess_data(data, ['WIN_Example'], docs, compatible=lambda *_: True)
            page = render(units, {'decisions_pending': [], 'answer_sheet_open': 0,
                                 'answer_sheet_done': 0, 'unresolved_items': 1}, [], [], 'Example', 'fixed', functional)
        self.assertIn('<div class="hero"><div class="pct">100.0%</div>', page)
        self.assertIn('1/1 required checks', page)
        self.assertIn('1<small>/1</small></div><div>screens functionally verified', page)
        self.assertIn('Windows x64 · pending', page)
        self.assertIn('Windows printer check not run.', page)
        self.assertIn('<div class="big">0.0%</div><div>strict completion</div>', page)
        self.assertEqual((units[0]['stage'], units[0]['proven'], units[0]['source_unresolved']), ('built', 0, 1))
        self.assertEqual(rows[0]['confidence'], 'unresolved')
        self.assertIn('data-f="functional-verified"', page)
        self.assertIn('class="built functional-verified"', page)
        self.assertIn('flow.ts :: save and reopen', page)


if __name__ == '__main__':
    unittest.main()
