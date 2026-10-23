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

    def test_evidence_forms_and_unresolved_citation(self):
        errors, _ = self.run_check([
            row('R1', 'specified', target_behavior='same',
                evidence='code/WIN_A.wdw:3; dossier: WIN_A/BTN_Ok; dossier/windev-window/WIN_A.json (flags.Resizable)'),
            row('R2', 'unmapped', confidence='unresolved', legacy_behavior='Closes? See U-02'),
            row('R3', 'unmapped', confidence='inferred', legacy_behavior='Probably closes the window'),
            row('R4', 'specified', target_behavior='same', evidence='see docs/notes.md')])
        self.assertEqual(len(errors), 2)
        self.assertIn('R3', errors[0])
        self.assertIn('U-nn', errors[0])
        self.assertIn('see docs/notes.md', errors[1])  # prose ending in a file name is not a reference

    def test_check_files(self):
        (self.root / 'a.wdw').write_text('x', encoding='utf-8')
        write(self.root / 'parity.csv', [row('R1', 'specified', target_behavior='same', evidence=f'{self.root}/a.wdw:3; {self.root}/gone.wdw:1')])
        errors, _ = module.check(self.root / 'parity.csv', check_files=True)
        self.assertEqual(errors, [f'line 2 (R1): evidence file not found: {self.root}/gone.wdw'])

    def test_stale_seed_rows_are_reported(self):
        errors, _ = self.run_check([row('SRC-old', 'specified', target_behavior='same'),
                                    row('SRC-new', 'specified', target_behavior='same'),
                                    row('RULE-X-001', 'specified', target_behavior='same')],
                                   seed=[row('SRC-new', 'unmapped', confidence='unresolved')])
        self.assertEqual(errors, ['matrix row not in the current seed (stale evidence): SRC-old'])

    def test_note_lint(self):
        note = self.root / 'WIN_A.md'
        note.write_text('Font read from the image (U-WA-03).\nMax length not extracted.\nCaption: Cancelar\n', encoding='utf-8')
        self.assertEqual(module.lint_note(note), ['WIN_A.md:2: open point without a U- id: Max length not extracted.'])

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

    def test_seed_can_be_limited_to_one_element(self):
        write(self.root / 'parity.csv', [row('R1', 'unmapped', confidence='unresolved')])
        write(self.root / 'seed.csv', [row('R1', 'unmapped'), {**row('R2', 'unmapped'), 'element': 'WIN_Other'}])
        errors, _ = module.check(self.root / 'parity.csv', self.root / 'seed.csv', element='WIN_Order')
        self.assertEqual(errors, [])

    def test_missing_columns(self):
        (self.root / 'parity.csv').write_text('id,status\nR1,verified\n', encoding='utf-8')
        errors, _ = module.check(self.root / 'parity.csv')
        self.assertIn('missing column: evidence', errors)


if __name__ == '__main__':
    unittest.main()
