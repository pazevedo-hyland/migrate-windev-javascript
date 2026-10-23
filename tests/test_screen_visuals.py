import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

layout_module = load('scripts/screen_layout.py')
skin = load('scripts/skin_assets.py')
visual = load('scripts/visual_compare.py')
try:
    import PIL  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def project(root):
    """A minimal evidence set: inspector layout + dossier controls for one window."""
    (root / 'inspect/code/code').mkdir(parents=True)
    (root / 'inspect/code/code/WIN_A.wdw.json').write_text(json.dumps({'name': 'WIN_A', 'layout': [
        {'name': 'BTN_Ok', 'kind': 'control', 'x': 10, 'y': 30, 'width': 90, 'height': 24},
        {'name': 'EDT_Obs', 'kind': 'control', 'x': 10, 'y': 60, 'width': 300, 'height': 40},
        {'name': 'TABLE_T', 'kind': 'control', 'x': 10, 'y': 110, 'width': 300, 'height': 100},
        {'name': 'COL_B', 'kind': 'column', 'x': 10, 'y': 110, 'width': None, 'height': None},
        {'name': 'COL_A', 'kind': 'column', 'x': 10, 'y': 110, 'width': None, 'height': None}]}))
    (root / 'dossier/windev-window').mkdir(parents=True)
    (root / 'dossier/windev-window/WIN_A.json').write_text(json.dumps({
        'title': {'PT': 'Janela A'}, 'size': {'width': 400, 'height': 300}, 'lines': ['Background image PT: C:\\P\\Bg.gif'],
        'controls': {
            'BTN_Ok': {'kind': 'Button', 'caption': {'PT': 'OK'}, 'image': {'PT': 'C:\\P\\Btn_OK.gif'},
                       'raw': ['Nb. image states 2', 'Background image PT: C:\\P\\Btn_anim.gif'],
                       'background_image': {'PT': 'C:\\P\\Btn_anim.gif'}, 'flags': {'Visible': True}},
            'EDT_Obs': {'kind': 'Edit control', 'caption': {'PT': 'Obs'}, 'raw': ['Inside width 240']},
            'TABLE_T': {'kind': 'Table'},
            'COL_A': {'kind': 'Table column', 'path': 'TABLE_T.COL_A', 'column_index': 1, 'title': {'PT': 'A'}, 'width': 120},
            'COL_B': {'kind': 'Table column', 'path': 'TABLE_T.COL_B', 'column_index': 2, 'title': {'PT': 'B'}, 'width': 80}}}))
    return {'inspect': str(root / 'inspect'), 'dossier': str(root / 'dossier')}


class ScreenVisualTests(unittest.TestCase):
    def test_layout_joins_geometry_captions_images_and_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            data = layout_module.layout('WIN_A', project(Path(directory)))
        controls = {c['name']: c for c in data['controls']}
        self.assertEqual((data['window']['title'], data['window']['background_image']), ('Janela A', 'Bg.gif'))
        self.assertEqual((controls['BTN_Ok']['caption'], controls['BTN_Ok']['image'], controls['BTN_Ok']['image_states']),
                         ('OK', 'Btn_OK.gif', '2'))
        self.assertEqual(controls['EDT_Obs']['caption_width'], 60)  # 300 wide, input box 240
        self.assertEqual([c['name'] for c in controls['TABLE_T']['columns']], ['COL_A', 'COL_B'])  # legacy order
        self.assertEqual(data['assets'], ['Bg.gif', 'Btn_OK.gif', 'Btn_anim.gif'])

    @unittest.skipUnless(HAS_PIL, 'Pillow not installed')
    def test_skin_states_magenta_and_visual_score(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = layout_module.layout('WIN_A', project(root))
            (root / 'wd').mkdir()
            strip = Image.new('RGB', (32, 16), (255, 0, 255))
            strip.paste((10, 120, 10), (2, 2, 14, 14))
            strip.save(root / 'wd/Btn_OK.gif')
            result = skin.export([data], root / 'wd', root / 'skin')
            self.assertEqual(result['missing'], ['Bg.gif', 'Btn_anim.gif'])
            self.assertIn('Btn_OK.1.png', result['written'])  # two states, 16 px each
            normal = Image.open(root / 'skin/Btn_OK.0.png')
            self.assertEqual((normal.size, normal.getpixel((0, 0))[3], normal.getpixel((5, 5))[3]), ((16, 16), 0, 255))
            legacy = Image.new('RGB', (200, 100), 'white')
            legacy.paste((0, 0, 0), (20, 20, 120, 22))
            legacy.save(root / 'legacy.png')
            legacy.save(root / 'same.png')
            moved = Image.new('RGB', (200, 100), 'white')
            moved.paste((0, 0, 0), (20, 60, 120, 62))
            moved.save(root / 'moved.png')
            same = visual.compare(root / 'legacy.png', root / 'same.png', root / 'side.png')
            other = visual.compare(root / 'legacy.png', root / 'moved.png')
            self.assertTrue((root / 'side.png').exists())
        self.assertEqual((same['pixel_similarity'], same['edge_overlap']), (100.0, 100.0))
        self.assertLess(other['edge_overlap'], 10)  # the line moved: layout does not match


if __name__ == '__main__':
    unittest.main()
