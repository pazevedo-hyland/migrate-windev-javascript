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
        self.assertEqual(latest['inspect'], paths['inspect'])
        self.assertNotIn('dossier', latest)
        self.assertIn('Encoded actions (1 distinct, 1 slots)', report)
        self.assertIn('WIN_A[WIN_A] --> WIN_B[WIN_B]', navigation)
        self.assertIn('| A-', sheet)

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
