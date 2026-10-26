import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from helpers import load

layout = load('scripts/screen_layout.py')
inspector = load('scripts/inspect_windev.py')
generator = load('scripts/generate_screens.py')


SOURCE = '''info :
 name : WIN_Nested
window :
 properties :
  width : 640
  height : 480
 controls :
  -
   name : GROUP
   properties :
    x : 10
    y : 20
   controls :
    -
     name : TABLE_A
     properties :
      width : 100
      height : 80
     columns :
      -
       name : COL_Code
    -
     name : TABLE_B
     properties :
      y : 100
      width : 100
      height : 80
     columns :
      -
       name : COL_Code
  -
   name : EDT_Password
   properties :
    x : 10
    y : 240
    width : 160
    height : 24
'''


class ScreenDefinitionTests(unittest.TestCase):
    def test_source_scopes_duplicate_columns_without_borrowing_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'legacy').mkdir()
            (root / 'legacy/nested.wdw').write_text(SOURCE)
            inspector.inspect(root / 'legacy', root / 'inspect')
            (root / 'dossier/windev-window').mkdir(parents=True)
            dossier = {'title': {'en': 'Nested', 'fr': 'Imbriqué'}, 'controls': {
                'GROUP': {'kind': 'Supercontrol'},
                'TABLE_A': {'kind': 'Table'}, 'TABLE_B': {'kind': 'Table'},
                'COL_Code': {'path': 'GROUP.TABLE_B.COL_Code', 'caption': {'en': 'Merged unsafe metadata'}},
                'EDT_Password': {'kind': 'Edit control', 'caption': {'fr': 'Secret'},
                                 'flags': {'Visible': False, 'Password': True, 'NULL if empty': True},
                                 'input_type': 'Text', 'input_size': 32}}}
            (root / 'dossier/windev-window/WIN_Nested.json').write_text(json.dumps(dossier))
            before = (root / 'legacy/nested.wdw').read_bytes()
            result = layout.layout('WIN_Nested', {key: str(root / key) for key in ('legacy', 'inspect', 'dossier')}, 'en')
            by_name = {control['name']: control for control in result['controls']}
            self.assertEqual(result['window']['size'], {'width': 640, 'height': 480})
            self.assertEqual(by_name['TABLE_A']['columns'][0]['path'], 'GROUP.TABLE_A.COL_Code')
            self.assertEqual(by_name['TABLE_B']['columns'][0]['path'], 'GROUP.TABLE_B.COL_Code')
            for table in ('TABLE_A', 'TABLE_B'):
                self.assertIsNone(by_name[table]['columns'][0]['title'])
                self.assertTrue(by_name[table]['columns'][0]['metadata_unresolved'])
            self.assertNotIn('visible', by_name['TABLE_A'])
            self.assertFalse(by_name['EDT_Password']['visible'])
            self.assertEqual(by_name['EDT_Password']['input_size'], 32)
            self.assertTrue(by_name['EDT_Password']['flags']['NULL if empty'])
            self.assertEqual(result['source'], 'nested.wdw')
            self.assertIn('language en unavailable', '\n'.join(result['diagnostics']))
            self.assertEqual((root / 'legacy/nested.wdw').read_bytes(), before)

    def test_qualified_evidence_and_absent_dossier_keep_unknowns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inspect/code').mkdir(parents=True)
            (root / 'inspect/code/one.json').write_text(json.dumps({'name': 'WIN_A', 'path': 'code/a.wdw', 'layout': [
                {'name': 'Odd', 'kind': 'control', 'path': 'GROUP.Odd', 'x': 0, 'y': 0}]}))
            result = layout.layout('WIN_A', {'inspect': str(root / 'inspect')})
            self.assertEqual(result['controls'][0]['path'], 'GROUP.Odd')
            self.assertEqual(result['controls'][0]['kind'], 'control')
            self.assertNotIn('visible', result['controls'][0])
            self.assertIn('no dossier entry', '\n'.join(result['unknown']))

    def test_dossier_literals_reach_runtime_and_named_metadata_is_retained(self):
        details = {
            'COMBO_Filter': {'kind': 'Combo box', 'caption': {'en': 'Filter'}},
            'CHECK_Active': {'kind': 'Check box', 'caption': {'en': 'Active'}},
            'RADIO_Mode': {'kind': 'Radio button', 'caption': {'en': 'Mode'}},
            'EDT_Date': {'kind': 'Edit control', 'input_type': 'Date', 'input_mask': {'en': 'DD/MM/YYYY'},
                         'raw': ['Return format YYYYMMDD', 'Calendar button Yes', 'Calculator button No',
                                 'Blocking validation No']},
            'EDT_PartialDate': {'kind': 'Edit control', 'input_type': 'Date', 'raw': ['Calendar button No']},
            'EDT_Text': {'kind': 'Edit control', 'input_type': 'Text', 'raw': ['Return format do-not-infer']},
            'TABLE_Items': {'kind': 'Table', 'raw': ['Magnifier mode Selection', 'Horz. scrollbar Automatic',
                'Vert. scrollbar Always visible', 'Tooltip when truncated Yes', 'Per-pixel scrolling No',
                'Touch scrolling No', 'Column context menu Yes', 'Context menu mode. Internal',
                'Remember filters Yes', 'Row height (without margin) 19', 'Selection mode Single',
                'Select. columns No', 'Select. cells Yes']},
            'STC_Aligned': {'kind': 'Caption', 'row': 'Active Center Bottom'},
            'STC_Explicit': {'kind': 'Caption', 'row': 'Active Center Bottom', 'h_align': 'Right',
                             'raw': ['Vert. alignment Top']},
            'STC_Partial': {'kind': 'Caption', 'row': 'Active Center'},
            'IMG_Fallback': {'kind': 'Image', 'initial_value': {'en': 'C:\\Synthetic\\poster.gif'}},
            'IMG_Explicit': {'kind': 'Image', 'image': {'en': 'C:\\Synthetic\\explicit.gif'},
                             'initial_value': {'en': 'C:\\Synthetic\\ignored.gif'}},
            'ODD_Custom': {'kind': 'Unknown custom'},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inspect/code').mkdir(parents=True)
            (root / 'inspect/code/one.json').write_text(json.dumps({'name': 'WIN_Literals', 'path': 'literals.wdw',
                'layout': [{'name': name, 'kind': 'control', 'x': 10, 'y': index * 25,
                            'width': 200, 'height': 24} for index, name in enumerate(details)]}))
            (root / 'dossier/windev-window').mkdir(parents=True)
            (root / 'dossier/windev-window/WIN_Literals.json').write_text(json.dumps({'controls': details}))
            extracted = layout.layout('WIN_Literals', {key: str(root / key) for key in ('inspect', 'dossier')}, 'en')
            input_file = root / 'literals.layout.json'
            input_file.write_text(json.dumps(extracted))
            manifest = generator.generate(input_file, root / 'generated', 'en')
            normalized = json.loads((root / 'generated' / manifest['inputs'][0]['layout']).read_text())
        controls = {item['name']: item for item in normalized['controls']}
        for name, literal, canonical in [('COMBO_Filter', 'Combo box', 'Combo Box'),
                                          ('CHECK_Active', 'Check box', 'Check Box'),
                                          ('RADIO_Mode', 'Radio button', 'RadioButton')]:
            self.assertEqual(controls[name]['kind'], canonical)
            self.assertEqual(controls[name]['source_kind'], literal)
        self.assertEqual(controls['EDT_Date']['input_mask'], 'DD/MM/YYYY')
        self.assertEqual(controls['EDT_Date']['return_format'], 'YYYYMMDD')
        self.assertEqual({key: controls['EDT_Date'][key] for key in ('calendar_button', 'calculator_button', 'blocking_validation')},
                         {'calendar_button': 'Yes', 'calculator_button': 'No', 'blocking_validation': 'No'})
        self.assertEqual(controls['EDT_PartialDate']['calendar_button'], 'No')
        self.assertNotIn('return_format', controls['EDT_PartialDate'])
        self.assertNotIn('return_format', controls['EDT_Text'])
        self.assertEqual(controls['TABLE_Items']['table_options']['row_height'], '19')
        self.assertEqual(controls['TABLE_Items']['table_options']['context_menu'], 'Internal')
        self.assertEqual(controls['TABLE_Items']['table_options']['touch_scrolling'], 'No')
        self.assertNotIn('remember_sorts', controls['TABLE_Items']['table_options'])
        self.assertEqual((controls['STC_Aligned']['h_align'], controls['STC_Aligned']['v_align']), ('Center', 'Bottom'))
        self.assertEqual((controls['STC_Explicit']['h_align'], controls['STC_Explicit']['v_align']), ('Right', 'Top'))
        self.assertNotIn('h_align', controls['STC_Partial'])
        self.assertNotIn('v_align', controls['STC_Partial'])
        self.assertEqual(controls['IMG_Fallback']['image'], 'poster.gif')
        self.assertEqual(controls['IMG_Explicit']['image'], 'explicit.gif')
        self.assertEqual(normalized['assets'], ['explicit.gif', 'poster.gif'])
        self.assertEqual(controls['ODD_Custom']['kind'], 'Unknown custom')
        self.assertIn('Unknown custom', '\n'.join(normalized['diagnostics']))

    def test_window_source_path_cannot_escape_private_root_or_read_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'legacy'
            legacy.mkdir()
            outside = root / 'outside.wdw'
            outside.write_text(SOURCE)
            (legacy / 'linked.wdw').symlink_to(outside)
            (legacy / 'linked-directory').symlink_to(root, target_is_directory=True)
            paths = ['../outside.wdw', '..\\outside.wdw', str(outside), 'C:\\outside.wdw',
                     'linked.wdw', 'linked-directory/outside.wdw', 'report.wde', 'query.wdr']
            for path in paths:
                with self.subTest(path=path), mock.patch.object(Path, 'read_bytes') as read_source:
                    with self.assertRaises(ValueError):
                        layout.source_context({'path': path, 'layout': []}, {'legacy': str(legacy)})
                    read_source.assert_not_called()


if __name__ == '__main__':
    unittest.main()
