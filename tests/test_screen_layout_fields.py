import tempfile
import unittest
from pathlib import Path

from helpers import load

layout = load('scripts/screen_layout.py')


class ScreenLayoutFieldTests(unittest.TestCase):
    def test_anchor_lines_become_the_ui_kit_anchoring_in_percent(self):
        raw = ['Anchor to content <None>', 'Anchor Right and bottom',
               'Anchor rate to right 500 Anchor rate bottom 250 Anc. rate width 1000 Anchor rate height 1000']
        self.assertEqual(layout.anchor(raw), {'anchoring': 'Right and bottom',
                                              'anchorRates': {'right': 50.0, 'bottom': 25.0, 'width': 100.0, 'height': 100.0}})
        self.assertEqual(layout.anchor(['Opacity 100']), {})  # not stated: unknown, not "none"

    def test_image_names_keep_real_spaces_and_lose_pdf_wraps(self):
        layout.PROJECT_FILES.clear()
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'SIXTIES TV0101.png').write_bytes(b'')
            layout.PROJECT_FILES.update({'sixtiestv0101.png': 'SIXTIES TV0101.png'})
            self.assertEqual(layout.basename('.\SIXTIES TV0101.png'), 'SIXTIES TV0101.png')
            self.assertEqual(layout.basename('<REPGABARIT>\WD\170 AquaBlue\AquaBlue_Btn_Std.pn g'), 'AquaBlue_Btn_Std.png')
        layout.PROJECT_FILES.clear()


if __name__ == '__main__':
    unittest.main()
