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
        self.assertEqual(latest['inspect'], paths['inspect'])
        self.assertNotIn('dossier', latest)
        self.assertIn('Encoded actions (1 distinct, 1 slots)', report)
        self.assertIn('WIN_A[WIN_A] --> WIN_B[WIN_B]', navigation)


if __name__ == '__main__':
    unittest.main()
