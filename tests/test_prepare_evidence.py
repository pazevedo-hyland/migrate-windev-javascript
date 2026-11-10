import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/prepare_evidence.py')

WINDOW = '''window :
 name : WIN_A
 controls :
  -
    name : BTN_Ok
    properties :
     x : 10
     y : 10
     width : 80
     height : 24
    code_elements :
     p_codes :
      -
        code : |1-
         Open(WIN_B)
        type : 18
      -
        internal_properties : QQQQ
        type : 16
'''


class PrepareEvidenceTests(unittest.TestCase):
    def test_pipeline_without_dossier_or_compile_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'legacy/code').mkdir(parents=True)
            (root / 'legacy/code/WIN_A.wdw').write_text(WINDOW, encoding='utf-8')
            paths = module.prepare(root / 'legacy', root / 'analysis-local', root / 'docs')
            latest = json.loads((root / 'analysis-local/latest.json').read_text(encoding='utf-8'))
            report = (root / 'docs/evidence-report.md').read_text(encoding='utf-8')
            navigation = (root / 'docs/navigation.md').read_text(encoding='utf-8')
            sheet = (root / 'docs/evidence/encoded-actions.md').read_text(encoding='utf-8')
            images = [p.name for p in (root / 'docs/evidence/images').iterdir()]
        self.assertEqual(latest['inspect'], paths['inspect'])
        self.assertNotIn('dossier', latest)
        self.assertEqual(latest['decoded'], paths['decoded'])
        self.assertIn('properties_failed', latest['decoded_coverage'])
        self.assertNotIn('decoded_calibration', latest)
        self.assertIn('Encoded actions (1 distinct, 1 slots)', report)
        self.assertIn('WIN_A[WIN_A] --> WIN_B[WIN_B]', navigation)
        self.assertIn('| A-', sheet)
        self.assertTrue(images)  # the layout drawing is published to docs/evidence/images/
        self.assertEqual(latest['readiness'], paths['readiness'])

    def test_readiness_and_briefs_come_with_the_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'legacy/code').mkdir(parents=True)
            (root / 'legacy/code/WIN_A.wdw').write_text(WINDOW, encoding='utf-8')
            (root / 'legacy/code/WIN_B.wdw').write_text(WINDOW.replace('WIN_A', 'WIN_B').replace('Open(WIN_B)', 'Close()'),
                                                         encoding='utf-8')
            module.prepare(root / 'legacy', root / 'analysis-local', root / 'docs', data=root / 'legacy/code')
            readiness = (root / 'docs/readiness.md').read_text(encoding='utf-8')
            records = {r['unit']: r for r in json.loads((root / 'docs/readiness.json').read_text(encoding='utf-8'))}
            brief = (root / 'docs/briefs/WIN_B.md').read_text(encoding='utf-8')
            latest = json.loads((root / 'analysis-local/latest.json').read_text(encoding='utf-8'))
        self.assertIn('2 units', readiness)
        self.assertEqual((records['WIN_A']['opens'], records['WIN_A']['controls'], records['WIN_A']['controls_positioned']),
                         (['WIN_B'], 1, 1))
        self.assertTrue(any('WIN_A' in site for site in records['WIN_B']['opened_by']))
        self.assertIn('# WIN_B (window)', brief)
        self.assertIn('Opened or printed by: ', brief)
        self.assertIn('| BTN_Ok |', brief)
        self.assertIn('unit_evidence.py WIN_B', brief)
        self.assertNotIn('Close()', brief)       # no code in a brief: lines and names only
        self.assertNotIn('data', latest)         # --data without an analysis file: reported, nothing read

    def test_answer_sheet_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'legacy/code').mkdir(parents=True)
            (root / 'legacy/code/WIN_A.wdw').write_text(WINDOW, encoding='utf-8')
            (root / 'docs/evidence').mkdir(parents=True)
            (root / 'docs/evidence/encoded-actions.md').write_text('my answers', encoding='utf-8')
            module.prepare(root / 'legacy', root / 'analysis-local', root / 'docs')
            self.assertEqual((root / 'docs/evidence/encoded-actions.md').read_text(encoding='utf-8'), 'my answers')

    def test_unit_evidence_pack(self):
        unit_evidence = load('scripts/unit_evidence.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'legacy/code').mkdir(parents=True)
            (root / 'legacy/code/WIN_A.wdw').write_text(WINDOW, encoding='utf-8')
            (root / 'legacy/code/WIN_C.wdw').write_text(WINDOW.replace('WIN_A', 'WIN_C'), encoding='utf-8')
            module.prepare(root / 'legacy', root / 'analysis-local', root / 'docs')
            latest = json.loads((root / 'analysis-local/latest.json').read_text(encoding='utf-8'))
            data = unit_evidence.pack('win_a', latest)
        self.assertEqual(len(data['seed_rows']), 2)  # the code block and the encoded action
        self.assertEqual(data['blocks'][0]['control'], 'WIN_A/BTN_Ok')
        action = data['encoded_actions'][0]
        self.assertEqual([s['element'] for s in action['same_action_elsewhere']], ['WIN_C'])  # same value elsewhere
        self.assertEqual(data['calls']['Open'], [{'line': 15, 'argument': 'WIN_B'}])


if __name__ == '__main__':
    unittest.main()
