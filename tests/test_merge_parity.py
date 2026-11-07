import csv
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, load

module = load('scripts/merge_parity.py')
checker = load('scripts/parity_check.py')
COLUMNS = ['id', 'kind', 'element', 'context', 'event', 'evidence', 'confidence', 'legacy_behavior',
           'target_behavior', 'implemented_in', 'test', 'decision', 'status']


def write(path, rows, columns=COLUMNS):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, '') for c in columns})


def row(identifier, element='WIN_A', status='unmapped', **extra):
    return {'id': identifier, 'kind': 'event', 'element': element, 'evidence': 'P/A.wdw:3',
            'confidence': 'inferred', 'status': status, **extra}


def parse(text):
    return list(csv.DictReader(io.StringIO(text)))


class MergeParityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        write(self.root / 'parity-seed.csv', [row('SRC-003'), row('SRC-001', 'WIN_B'), row('SRC-002', 'WIN_C')])

    def tearDown(self):
        self.directory.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/merge_parity.py'), str(self.root), *args],
                              capture_output=True, text=True, encoding='utf-8')

    def test_unit_files_win_and_aggregate_only_rows_are_kept(self):
        write(self.root / 'parity.csv', [row('SRC-003'), row('SRC-001', 'WIN_B'), row('SRC-002', 'WIN_C'),
                                         row('RULE-900', 'Reports', 'specified', target_behavior='kept')])
        write(self.root / 'WIN_A.csv', [row('SRC-003', status='implemented', target_behavior='new', implemented_in='a.ts'),
                                        row('RULE-010', status='specified', target_behavior='rule')])
        write(self.root / 'WIN_B.csv', [row('SRC-001', 'WIN_B', 'specified', target_behavior='b')])
        text, rows, errors = module.merge(self.root)
        self.assertEqual(errors, [])
        merged = parse(text)
        # seed order first, then the other ids sorted
        self.assertEqual([r['id'] for r in merged], ['SRC-003', 'SRC-001', 'SRC-002', 'RULE-010', 'RULE-900'])
        by_id = {r['id']: r for r in merged}
        self.assertEqual(by_id['SRC-003']['status'], 'implemented')
        self.assertEqual(by_id['SRC-001']['target_behavior'], 'b')
        self.assertEqual(by_id['SRC-002']['status'], 'unmapped')  # only in the aggregate: unchanged
        self.assertEqual(by_id['RULE-900']['target_behavior'], 'kept')
        self.assertEqual(list(merged[0].keys()), COLUMNS)

    def test_duplicate_id_across_unit_files_is_an_error_and_nothing_is_written(self):
        write(self.root / 'parity.csv', [row('SRC-003')])
        before = (self.root / 'parity.csv').read_bytes()
        write(self.root / 'WIN_A.csv', [row('SRC-003', status='specified', target_behavior='a')])
        write(self.root / 'WIN_B.csv', [row('SRC-003', status='specified', target_behavior='b')])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn('id SRC-003 already in WIN_A.csv', result.stderr)
        self.assertEqual((self.root / 'parity.csv').read_bytes(), before)

    def test_unknown_column_and_missing_id_column_are_errors(self):
        write(self.root / 'parity.csv', [row('SRC-003')])
        write(self.root / 'WIN_A.csv', [{**row('SRC-003'), 'note': 'x'}], COLUMNS + ['note'])
        write(self.root / 'WIN_B.csv', [{'element': 'WIN_B'}], ['element', 'status'])
        _, _, errors = module.merge(self.root)
        self.assertTrue(any('WIN_A.csv: columns not in the aggregate: note' in e for e in errors), errors)
        self.assertTrue(any('WIN_B.csv: no id column' in e for e in errors), errors)

    def test_missing_unit_columns_are_blank_and_header_falls_back_to_seed(self):
        write(self.root / 'WIN_A.csv', [{'id': 'SRC-003', 'element': 'WIN_A', 'status': 'unmapped'}],
              ['id', 'element', 'status'])
        text, _, errors = module.merge(self.root)
        self.assertEqual(errors, [])
        merged = parse(text)
        self.assertEqual(list(merged[0].keys()), COLUMNS)
        self.assertEqual(merged[0]['evidence'], '')
        self.assertEqual([r['id'] for r in merged], ['SRC-003'])  # seed rows are not invented

    def test_exclusion_is_reapplied_after_the_merge(self):
        write(self.root / 'parity.csv', [row('SRC-001', 'WIN_B', 'excluded', decision='docs/decisions/002.md')])
        write(self.root / 'WIN_B.csv', [row('SRC-001', 'WIN_B', 'specified', target_behavior='revived')])
        result = self.run_cli('--exclude', 'WIN_B=docs/decisions/002.md')
        self.assertEqual(result.returncode, 0, result.stderr)
        merged = parse((self.root / 'parity.csv').read_text(encoding='utf-8'))
        self.assertEqual((merged[0]['status'], merged[0]['decision']), ('excluded', 'docs/decisions/002.md'))
        self.assertEqual(self.run_cli('--exclude', 'WIN_Z=docs/decisions/002.md').returncode, 1)

    def test_check_mode_writes_nothing_and_reports_change(self):
        write(self.root / 'parity.csv', [row('SRC-003')])
        write(self.root / 'WIN_A.csv', [row('SRC-003', status='specified', target_behavior='a')])
        before = (self.root / 'parity.csv').read_bytes()
        result = self.run_cli('--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('would change', result.stdout)
        self.assertEqual((self.root / 'parity.csv').read_bytes(), before)
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.run_cli('--check').returncode, 0)  # idempotent

    def test_merged_matrix_passes_the_parity_gate(self):
        write(self.root / 'parity.csv', [row('SRC-003'), row('SRC-001', 'WIN_B'), row('SRC-002', 'WIN_C')])
        write(self.root / 'WIN_A.csv', [row('SRC-003', status='implemented', target_behavior='t', implemented_in='a.ts')])
        self.assertEqual(self.run_cli().returncode, 0)
        errors, summary = checker.check(self.root / 'parity.csv', self.root / 'parity-seed.csv')
        self.assertEqual(errors, [])
        self.assertEqual(summary['statuses']['implemented'], 1)


if __name__ == '__main__':
    unittest.main()
