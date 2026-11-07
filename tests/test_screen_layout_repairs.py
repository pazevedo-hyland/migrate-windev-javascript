"""Repairs the extractor makes from the dossier's control tables and text (synthetic evidence only)."""
import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

layout = load('scripts/screen_layout.py')
HEADERS = ['X position', 'Y position', 'Width', 'Height', 'Plane', 'Visible']
LONG_A = 'EDT_quantity_of_parts_at_start_of_run'   # cut to 32 characters by the dossier table
LONG_B = 'CBOX_load_secondary_file_by_default'
LONG_B1 = LONG_B + '1'


def dossier_lines():
    return [
        'Information on controls', 'Window : WIN_Synth',
        'Edit control', *HEADERS,
        f'{LONG_A[:32]} 10 40 300 24 0 Active Text',
        'EDT_Name 10 10 300 24 0 Active Text',
        'Check Box', *HEADERS,
        # two names cut to the same prefix: the table is sorted by full name
        f'{LONG_B[:32]} 12 200 280 24 0 Active 1',
        f'{LONG_B[:32]} 12 100 280 24 0 Active 1',
        *HEADERS,                                         # a page break repeats the headers, not the kind title
        'CBOX_Other 12 300 100 24 0 Active 1',
        'Supercontrol', *HEADERS,
        'SC_Panel 6 6 380 116 0 Active',
        'Radio Button', *HEADERS,
        'RADIO_Mode 10 70 180 62 0 Active',
        'Table : TABLE_Items',
        'Table column', 'Type', 'Width', 'Visible',
        'COL_Code', ' 80 Active Left Center Text',
        'COL_Description_of_the_item_in_', ' 240 Read-onl Left Center Text',
        'Edit control : EDT_Name',
        'Caption PT: Name',
    ]


def project(root, lines=None, code=''):
    items = [
        {'name': 'EDT_Name', 'kind': 'control', 'x': 10, 'y': 10, 'width': 300, 'height': 24},
        {'name': LONG_A, 'kind': 'control', 'x': 0, 'y': 0, 'width': None, 'height': None},
        {'name': LONG_B, 'kind': 'control', 'x': 0, 'y': 0, 'width': None, 'height': None},
        {'name': LONG_B1, 'kind': 'control', 'x': 0, 'y': 0, 'width': None, 'height': None},
        {'name': 'EDT_Lost', 'kind': 'control', 'x': 0, 'y': 0, 'width': None, 'height': None},
        {'name': 'SC_Panel', 'kind': 'control', 'x': 6, 'y': 6, 'width': 380, 'height': 116},
        {'name': 'RADIO_Mode', 'kind': 'control', 'x': 10, 'y': 70, 'width': 180, 'height': 62},
        {'name': 'STC_Note', 'kind': 'control', 'x': 10, 'y': 140, 'width': 300, 'height': 20},
        {'name': 'TABLE_Items', 'kind': 'control', 'x': 10, 'y': 170, 'width': 400, 'height': 120},
        {'name': 'COL_Code', 'kind': 'column', 'x': 10, 'y': 170, 'width': None, 'height': None},
        {'name': 'COL_Description_of_the_item_in_full', 'kind': 'column', 'x': 10, 'y': 170, 'width': None, 'height': None},
        {'name': 'COL_Unlisted', 'kind': 'column', 'x': 10, 'y': 170, 'width': None, 'height': None},
    ]
    (root / 'inspect/code').mkdir(parents=True)
    (root / 'inspect/code/synth.json').write_text(json.dumps({'name': 'WIN_Synth', 'layout': items, 'blocks': [
        {'code': code}]}), encoding='utf-8')
    controls = {
        'EDT_Name': {'kind': 'Edit control', 'caption': {'PT': 'Name'}},
        LONG_A: {'kind': 'Edit control', 'caption': {'PT': 'Parts at the start of the run'}, 'raw': ['Inside width 200']},
        LONG_B: {'kind': 'Check Box'},
        LONG_B1: {'kind': 'Check Box'},
        'RADIO_Mode': {'kind': 'Radio Button', 'caption': {'PT': 'Mode'}},
        'STC_Note': {'kind': 'Static', 'caption': {'PT': 'Print the reg istration form'}},
        'TABLE_Items': {'kind': 'Table'},
        'COL_Code': {'kind': 'Table column', 'path': 'TABLE_Items.COL_Code', 'column_index': 1, 'title': {'PT': 'Code'}},
        'COL_Description_of_the_item_in_full': {'kind': 'Table column', 'path': 'TABLE_Items.COL_Description_of_the_item_in_full',
                                                 'column_index': 2, 'title': {'PT': 'Description'}},
        'COL_Unlisted': {'kind': 'Table column', 'path': 'TABLE_Items.COL_Unlisted', 'column_index': 3},
    }
    (root / 'dossier/windev-window').mkdir(parents=True)
    (root / 'dossier/windev-window/WIN_Synth.json').write_text(json.dumps({
        'title': {'PT': 'Synthetic win dow'}, 'lines': dossier_lines() if lines is None else lines,
        'controls': controls}), encoding='utf-8')
    layout.VOCABULARIES.clear()
    return {'inspect': str(root / 'inspect'), 'dossier': str(root / 'dossier')}


class DossierTableTests(unittest.TestCase):
    def test_control_and_column_rows_keep_their_section_and_context(self):
        rows, columns = layout.dossier_tables(dossier_lines())
        named = {(row['name'], row['y']): row for row in rows}
        self.assertEqual(named[('EDT_Name', 10)]['kind'], 'Edit control')
        self.assertEqual(named[('SC_Panel', 6)]['kind'], 'Supercontrol')
        self.assertEqual(len([row for row in rows if row['name'] == LONG_B[:32]]), 2)
        self.assertEqual(named[('CBOX_Other', 300)]['kind'], 'Check Box')  # the section continues past a page break
        self.assertEqual([(c['name'], c['width'], c['context']) for c in columns],
                         [('COL_Code', 80, 'TABLE_Items'), ('COL_Description_of_the_item_in_', 240, 'TABLE_Items')])

    def test_truncated_names_match_only_long_prefixes_of_the_same_kind(self):
        rows = [{'name': 'EDT_quantity_of_parts_at_start_', 'kind': 'Edit control', 'x': 1, 'y': 2, 'width': 3, 'height': 4},
                {'name': 'EDT_q', 'kind': 'Edit control', 'x': 5, 'y': 6, 'width': 7, 'height': 8}]
        found, _ = layout.assign_rows({'a': (LONG_A, 'editcontrol'), 'b': ('EDT_quick', 'editcontrol'),
                                       'c': (LONG_A + 'X', 'checkbox')}, rows, set())
        self.assertEqual(found, {'a': 0})  # 'EDT_q' is too short to be a cut name; a Check Box is another table


class LayoutRepairTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()
        layout.VOCABULARIES.clear()

    def extract(self, **options):
        result = layout.layout('WIN_Synth', project(self.root, **options))
        return result, {control['name']: control for control in result['controls']}

    def test_geometry_of_cut_names_comes_from_the_control_tables(self):
        result, controls = self.extract()
        edit = controls[LONG_A]
        self.assertEqual({k: edit[k] for k in ('x', 'y', 'width', 'height')}, {'x': 10, 'y': 40, 'width': 300, 'height': 24})
        self.assertEqual(edit['geometry_source'], 'dossier')
        self.assertEqual(edit['caption_width'], 100)  # 300 wide, input box 200
        # same cut prefix twice: n-th row (table sorted by full name) is the n-th name
        self.assertEqual((controls[LONG_B]['y'], controls[LONG_B1]['y']), (200, 100))
        self.assertEqual(controls[LONG_B]['geometry_source'], 'dossier (row order)')
        # not in any table: stays without geometry and is listed, never invented
        self.assertNotIn('width', controls['EDT_Lost'])
        self.assertIn('EDT_Lost: geometry not in the dossier control tables', result['unknown'])
        self.assertNotIn('geometry_source', controls['EDT_Name'])  # already complete: untouched

    def test_without_the_tables_nothing_is_filled(self):
        result, controls = self.extract(lines=[])
        self.assertNotIn('width', controls[LONG_A])
        self.assertIn(f'{LONG_A}: geometry not in the dossier control tables', result['unknown'])
        self.assertEqual(controls['SC_Panel']['kind'], 'control')

    def test_kinds_from_the_dossier_and_rad_kit_names(self):
        _, controls = self.extract()
        self.assertEqual((controls['SC_Panel']['kind'], controls['SC_Panel']['source_kind']), ('Supercontrol', 'control'))
        self.assertEqual((controls['RADIO_Mode']['kind'], controls['RADIO_Mode']['source_kind']), ('RadioButton', 'Radio Button'))
        self.assertEqual((controls['STC_Note']['kind'], controls['STC_Note']['source_kind']), ('Caption', 'Static'))
        self.assertNotIn('source_kind', controls['EDT_Name'])

    def test_column_widths_from_the_column_tables(self):
        result, controls = self.extract()
        columns = {c['name']: c for c in controls['TABLE_Items']['columns']}
        self.assertEqual((columns['COL_Code']['width'], columns['COL_Code']['width_source']), (80, 'dossier'))
        self.assertEqual(columns['COL_Description_of_the_item_in_full']['width'], 240)  # cut name, matched by prefix
        self.assertIsNone(columns['COL_Unlisted']['width'])
        self.assertIn('TABLE_Items.COL_Unlisted: column width not in the dossier column tables', result['unknown'])

    def test_pdf_wrapped_words_are_joined_when_the_evidence_attests_them(self):
        code = 'Info("registration done", "window closed")\nBTN_Caps_Lock..Caption = "Caps"'
        lines = dossier_lines() + ['Caption PT: The registration form', 'Caption PT: Main window']
        result, controls = self.extract(lines=lines, code=code)
        self.assertEqual(controls['STC_Note']['caption'], 'Print the registration form')
        self.assertEqual(result['window']['title'], 'Synthetic window')
        self.assertIn("STC_Note.caption: PDF-wrapped word joined (dossier text 'Print the reg istration form')",
                      result['diagnostics'])

    def test_join_rules(self):
        words = {'production': 2, 'pro': 1, 'capslock': 4, 'caps': 1, 'lock': 1, 'the': 9, 'order': 9, 'theorder': 1}
        self.assertEqual(layout.join_wrapped('of pro duction', words), 'of production')
        self.assertEqual(layout.join_wrapped('Caps Lock', words), 'Caps Lock')       # a wrap continues in lower case
        self.assertEqual(layout.join_wrapped('the order', words), 'the order')       # both fragments are words
        self.assertEqual(layout.join_wrapped('of pro ductions', words), 'of pro ductions')  # joined word not attested
        self.assertIsNone(layout.join_wrapped(None, words))

    def test_vocabulary_reads_dossier_text_and_code_without_identifiers(self):
        project(self.root, lines=['Caption PT: Word one'], code='x = "Second phrase"\nBTN_Hidden_Name = 1')
        latest = {'inspect': str(self.root / 'inspect'), 'dossier': str(self.root / 'dossier')}
        words = layout.vocabulary(latest)
        self.assertEqual((words['word'], words['second'], words['phrase']), (1, 1, 1))
        self.assertNotIn('hidden', words)  # BTN_Hidden_Name is an identifier, not text


if __name__ == '__main__':
    unittest.main()
