import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/render_layouts.py')


class RenderLayoutsTests(unittest.TestCase):
    def test_renders_every_window_and_uses_captured_captions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inspect/code').mkdir(parents=True)
            (root / 'inspect/code/WIN_A.wdw.json').write_text(json.dumps({'path': 'WIN_A.wdw', 'layout': [
                {'name': 'BTN_Ok', 'kind': 'control', 'x': 10, 'y': 20, 'width': 80, 'height': 24},
                {'name': 'COL_X', 'kind': 'column', 'x': 0, 'y': 0, 'width': None, 'height': None}]}))
            (root / 'inspect/code/WIN_Empty.wdw.json').write_text(json.dumps({'path': 'WIN_Empty.wdw', 'layout': []}))
            (root / 'captures/WIN_A').mkdir(parents=True)
            (root / 'captures/WIN_A/tree.json').write_text(json.dumps([{'legacy_name': 'BTN_Ok', 'name': 'Confirmar'}]))
            rendered = module.render(root / 'inspect', root / 'out', root / 'captures')
            self.assertEqual(rendered, [('WIN_A', True)])
            drawing = (root / 'out/WIN_A.svg').read_text(encoding='utf-8')
            self.assertIn('Confirmar', drawing)
            self.assertIn('x="10" y="20" width="80" height="24"', drawing)
            self.assertIn('WIN_A.svg', (root / 'out/index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
