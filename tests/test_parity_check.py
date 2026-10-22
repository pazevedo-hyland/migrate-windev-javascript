import csv
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/parity_check.py')
COLUMNS = ['id', 'kind', 'element', 'context', 'event', 'evidence', 'confidence', 'legacy_behavior',
           'target_behavior', 'implemented_in', 'test', 'decision', 'status']


def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, '') for c in COLUMNS})


def row(identifier, status, **extra):
    base = {'id': identifier, 'kind': 'window', 'element': 'WIN_Order', 'evidence': 'a.wdw:3-9',
            'confidence': 'verified', 'status': status}
    base.update(extra)
    return base


class ParityCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def run_check(self, rows, seed=None, complete=False):
        write(self.root / 'parity.csv', rows)
        seed_path = None
        if seed is not None:
            seed_path = self.root / 'seed.csv'
            write(seed_path, seed)
        return module.check(self.root / 'parity.csv', seed_path, complete)

    def test_valid_matrix_and_summary(self):
        errors, summary = self.run_check([
            row('R1', 'verified', target_behavior='same', implemented_in='src/a.ts', test='a.test.ts'),
            row('R2', 'excluded', decision='ADR-004'),
            row('R3', 'unmapped', confidence='unresolved')])
        self.assertEqual(errors, [])
        self.assertEqual(summary['complete_percent'], 66.7)

    def test_evidence_rules(self):
        errors, _ = self.run_check([
            row('R1', 'verified', target_behavior='same', implemented_in='src/a.ts'),
            row('R1', 'excluded'),
            row('R3', 'done', evidence='', confidence='maybe'),
            row('R4', 'verified', confidence='unresolved', target_behavior='x', implemented_in='y', test='z')])
        text = '\n'.join(errors)
        for expected in ('executed test', 'duplicate id', 'decision (ADR)', 'status must be',
                         'confidence must be', 'evidence is required', 'cannot keep unresolved'):
            self.assertIn(expected, text)

    def test_seed_rows_cannot_disappear_and_completion_gate(self):
        errors, _ = self.run_check([row('R1', 'specified', target_behavior='x')],
                                   seed=[row('R1', 'unmapped'), row('R2', 'unmapped')], complete=True)
        self.assertIn('seed row missing from matrix: R2', errors)
        self.assertTrue(any('not complete (specified)' in e for e in errors))

    def test_missing_columns(self):
        (self.root / 'parity.csv').write_text('id,status\nR1,verified\n', encoding='utf-8')
        errors, _ = module.check(self.root / 'parity.csv')
        self.assertIn('missing column: evidence', errors)


if __name__ == '__main__':
    unittest.main()
