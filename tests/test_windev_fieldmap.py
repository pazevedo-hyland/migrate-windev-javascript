import json
from pathlib import Path
import struct
import tempfile
import unittest

from helpers import load

module = load('scripts/windev_fieldmap.py')
decoder = module.decoder
shapes = load('tests/test_windev_decode.py')

TYPES = {0: 'Text', 1: 'Numeric', 2: 'Date'}


def edit_chunk(index, input_type, row_height, mask, calendar, secret=0, caption=''):
    """An edit control: the shared block, then a tail with an enumeration, a number, a string and a yes/no."""
    tail = struct.pack('<II', input_type, row_height) + shapes.framed(mask) + struct.pack('<I', calendar) + bytes([secret, 0, 0])
    return shapes.control_chunk(10 + index, 20 + 3 * index, 100 + index % 7, 24, caption=caption, tab=index + 1)[:-60] + tail


def project(folder, windows=12, controls=4, unusual=None):
    """Synthetic sources and the dossier extract describing them. Returns (project dir, dossier dir)."""
    root, dossier = Path(folder, 'project'), Path(folder, 'dossier', 'windev-window')
    root.mkdir()
    dossier.mkdir(parents=True)
    for w in range(windows):
        lines, described = ['window :', f' name : WIN_{w}', ' controls :'], {}
        for c in range(controls):
            n = w * controls + c
            kind, height, calendar = n % 3, 16 + 2 * (n % 5), n % 2
            mask = ['', '999', 'AAAA', '99/99'][n % 4]
            secret = 7 if unusual == (w, c) else 0
            lines += ['  -', f'    name : EDT_{c}',
                      f'    internal_properties : {shapes.value_of(edit_chunk(n, kind, height, mask, calendar, secret, "Cap " + str(n % 3)))}',
                      '    type : 2']
            described[f'EDT_{c}'] = {
                'kind': 'Edit control', 'input_type': TYPES[kind], 'input_mask': {'PT': mask} if mask else None,
                # "Almost always" is No except once: fits a position by chance, proves nothing.
                'raw': [f'Row height {height}', f'Calendar button {"Yes" if calendar else "No"}',
                        f'Horz. scrollbar {"Never" if n % 3 else "Automatic"}', f'Almost always {"Yes" if n == 5 else "No"}']}
            described[f'EDT_{c}'] = {k: v for k, v in described[f'EDT_{c}'].items() if v is not None}
        (root / f'WIN_{w}.wdw').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        (dossier / f'WIN_{w}.json').write_text(json.dumps({'controls': described}), encoding='utf-8')
    return root, dossier.parent


class FieldMap(unittest.TestCase):
    def test_strings_are_normalised_to_one_byte(self):
        data = b'\x01\x02' + shapes.framed('abc') + b'\x03' + shapes.framed('') + b'\x04' + shapes.framed('zz') + b'\x05'
        normal, slots, moved = module.normalise(data)
        self.assertEqual(normal, b'\x01\x02\x00\x03\x00\x04\x00\x05')
        self.assertEqual(slots, {2: b'abc', 6: b'zz'})
        self.assertEqual(moved(len(data) - 1), 7)

    def test_dossier_lines_split_at_the_longest_varying_key(self):
        groups = [['Horz. scrollbar Never', 'Horz. alignment Left', 'Row height 18'],
                  ['Horz. scrollbar Automatic', 'Horz. alignment Right', 'Row height 20']]
        split = module.split_lines(groups, module.continuations(groups))
        self.assertEqual(split[0], {'Horz. scrollbar': 'Never', 'Horz. alignment': 'Left', 'Row height': '18'})

    def test_learned_positions_predict_windows_they_were_not_learned_from(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dossier = project(folder)
            samples = module.collect(root)
            fieldmap = module.learn_validated(samples, module.dossier_truth(dossier))
        entries = {prop: entry for frames in fieldmap.values() for learned in frames.values() for prop, entry in learned.items()}
        self.assertEqual((entries['input_type']['kind'], entries['input_type']['confidence']), ('enum', 'strong'))
        self.assertEqual(sorted(entries['input_type']['values'].values()), ['Date', 'Numeric', 'Text'])
        self.assertEqual((entries['line:Row height']['kind'], entries['line:Row height']['confidence']), ('number', 'strong'))
        self.assertEqual((entries['input_mask']['kind'], entries['input_mask']['confidence']), ('string', 'strong'))
        self.assertEqual(entries['line:Calendar button']['confidence'], 'strong')
        # A yes/no seen "yes" once fits somewhere by chance: kept apart as weak, never applied by default.
        self.assertEqual(entries.get('line:Almost always', {'confidence': 'weak'})['confidence'], 'weak')
        # A property that only follows from another (scrollbar = "input type is Text") has no position of its own.
        self.assertNotIn('line:Horz. scrollbar', entries)
        self.assertEqual(entries['input_type']['held_out'], '48/48')
        # Applying: an unseen enumeration value is reported, not guessed.
        chunk = {'id': 0, 'version': 14, 'data': edit_chunk(99, 9, 33, '99.99', 1)}
        slot = {'owner': 'controls', 'type': '2', 'name': 'EDT_new', 'line': 1}
        fields = decoder.describe('controls', '2', [chunk], keep_end=True)
        named = module.apply(fieldmap, module.sample_of('WIN_X', '.wdw', slot, chunk, fields))
        self.assertEqual(named['input_type'], 'unknown:09000000')
        self.assertEqual((named['line:Row height'], named['input_mask'], named['line:Calendar button']), (33, '99.99', 'Yes'))
        self.assertNotIn('line:Almost always', named)
        # What may be shared holds no weak entry and no value of the decoder's own fields.
        shared = module.shareable(fieldmap)
        kept = {prop: entry for frames in shared.values() for learned in frames.values() for prop, entry in learned.items()}
        self.assertNotIn('line:Almost always', kept)
        self.assertTrue(all('values' not in entry for prop, entry in kept.items() if prop.startswith('field:')))

    def test_audit_lists_only_what_nothing_explains(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dossier = project(folder, unusual=(3, 1))
            samples = module.collect(root)
            fieldmap = module.learn_validated(samples, module.dossier_truth(dossier))
            summary, findings = module.audit(samples, fieldmap)
        controls = [f for f in findings if f['variant'] == 'wdw/controls/2/0.14']
        self.assertEqual([(f['unit'], f['name']) for f in controls], [('WIN_3', 'EDT_1')])
        self.assertEqual([(d['value'], d['usual']) for d in controls[0]['differences']], [('07', '00')])
        group = next(v for k, v in summary.items() if k.startswith('wdw/controls/2/0.14'))
        self.assertEqual((group['elements'], group['without_unexplained_difference']), (48, 47))

    def test_a_project_map_completes_a_base_map(self):
        base = {'v': {'end': {'a': {'confidence': 'strong', 'position': -4}, 'b': {'confidence': 'strong', 'position': -8}}}}
        learned = {'v': {'start': {'a': {'confidence': 'weak', 'position': 9}, 'c': {'confidence': 'weak', 'position': 3},
                                   'b': {'confidence': 'strong', 'position': 12}}}}
        merged = module.merge_maps(base, learned)
        self.assertEqual(merged['v']['end'], {'a': {'confidence': 'strong', 'position': -4}})
        self.assertEqual(set(merged['v']['start']), {'b', 'c'})

    def test_decoder_applies_a_field_map_and_writes_the_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            root, dossier = project(folder, unusual=(2, 0))
            fieldmap = Path(folder, 'map.json')
            fieldmap.write_text(json.dumps({'variants': module.learn_validated(module.collect(root), module.dossier_truth(dossier))}),
                                encoding='utf-8')
            index = decoder.decode_project(root, Path(folder, 'out'), evidence=True, fieldmap=fieldmap)
            window = json.loads(Path(folder, 'out/properties/WIN_0.wdw.json').read_text(encoding='utf-8'))
            evidence = json.loads(Path(folder, 'out/evidence/windev-window/WIN_0.json').read_text(encoding='utf-8'))
            audit = json.loads(Path(folder, 'out/audit.json').read_text(encoding='utf-8'))
        self.assertEqual(window['elements'][1]['properties'], {'input_type': 'Numeric', 'line:Row height': 18,
                                                                'input_mask': '999', 'line:Calendar button': 'Yes'})
        control = evidence['controls']['EDT_1']
        self.assertEqual((control['input_type'], control['input_mask']), ('Numeric', '999'))
        self.assertIn('Row height 18', control['raw'])
        self.assertEqual(index['coverage']['elements_with_learned_properties'], 48)
        self.assertEqual([(e['unit'], e['name']) for e in audit['elements'] if '/controls/' in e['variant'] and e['variant'].endswith('0.14')],
                         [('WIN_2', 'EDT_0')])


class ProjectLevel(unittest.TestCase):
    def test_project_code_folders_and_used_files(self):
        texts = ['CONSTANT', 'ANA', '\tMAX = 3', 'ANA', 'END', 'ANA', 'gnRate is int', 'RUI', 'IF gnRate = 0 THEN', 'ANA',
                 '\tOpen(WIN_Login)', 'ANA', 'END', 'ANA']
        self.assertEqual(decoder.code_lines(texts), ['CONSTANT', '\tMAX = 3', 'END', 'gnRate is int', 'IF gnRate = 0 THEN',
                                                     '\tOpen(WIN_Login)', 'END'])
        self.assertIsNone(decoder.code_lines(['WIN_A', 'Arial', 'WIN_B', 'Tahoma', 'x', 'y', 'z', 'w']))     # not code
        elements = {'win_a': 'WIN_A', 'win_b': 'WIN_B', 'rpt_a': 'RPT_A'}
        self.assertEqual(decoder.project_folders(['Project', 'Windows', 'Back office', 'WIN_A', 'WIN_B', 'Empty', 'Reports', 'RPT_A'],
                                                 elements),
                         {'Back office': ['WIN_A', 'WIN_B'], 'Reports': ['RPT_A']})
        self.assertIsNone(decoder.project_folders(['WIN_A', 'x'], elements))
        listing = 'App.wdp\r\nlogo.png\r\nWIN_A.wdw\r\nOK.PNG\r\nSKIN\\BTN.PNG\r\nWIN_B.wdw\r\nRPT_A.wde\r\nfont.ttf\r\n'
        self.assertEqual(decoder.used_files(listing, elements),
                         {'App': ['logo.png'], 'WIN_A': ['OK.PNG', 'SKIN\\BTN.PNG'], 'RPT_A': ['font.ttf']})

    def test_binary_project_file_gives_its_code_to_the_decoder_and_the_code_map(self):
        code_map = load('scripts/code_map.py')
        inspector = load('scripts/inspect_windev.py')
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            project.mkdir()
            records = b''.join(shapes.framed(line) + shapes.framed('ANA') for line in
                               ['gnMode is int', 'CONSTANT', '\tLIMIT = 5', 'END', 'HReadFirst(Settings)', 'Open(WIN_A)'])
            (project / 'App.wdp').write_bytes(b'PCS\0' + b'\x14\0\0\0' + decoder.pack(b'\x01\0\0\0' + records))
            (project / 'WIN_A.wdw').write_text('info :\n name : WIN_A\nwindow :\n name : WIN_A\n code_elements :\n  p_codes :\n'
                                               '   -\n     code : |1+\n      IF gnMode = LIMIT THEN Close()\n', encoding='utf-8')
            (project / 'S.xdd').write_text('<?xml version="1.0" encoding="UTF-8"?><ANALYSE><FICHIER Nom="Settings">'
                                           '<RUBRIQUE Nom="a"/></FICHIER></ANALYSE>', encoding='utf-8')
            index = decoder.decode_project(project, Path(folder, 'decoded'))
            inspector.inspect(project, Path(folder, 'inspect'))
            data = code_map.build(Path(folder, 'inspect'), Path(folder, 'decoded'))
            code = Path(folder, 'decoded/project/App.code.wl').read_text(encoding='utf-8')
        self.assertEqual(index['coverage']['project_code_lines'], 6)
        self.assertIn('HReadFirst(Settings)', code)
        unit = data['units']['App (project code)']
        self.assertEqual((unit['kind'], list(unit['tables']), list(unit['opens'])), ('project', ['Settings'], ['WIN_A']))
        self.assertEqual(data['units']['WIN_A']['globals'], {'LIMIT': 1, 'gnMode': 1})


class DecoderAdditions(unittest.TestCase):
    def test_fonts(self):
        logfont = struct.pack('<iiiiIBBBB4B', -13, 0, 0, 0, 700, 1, 0, 0, 0, 3, 2, 1, 0x22)
        data = b'\x00' * 9 + logfont + shapes.framed('Tahoma') + bytes([0x0f, 0x3d, 0x5f, 0]) + shapes.framed('.\\icon.png')
        found, spans = decoder.fonts(data)
        self.assertEqual(found, [{'face': 'Tahoma', 'height': -13, 'weight': 700, 'points': 9.8, 'italic': True,
                                  'colour': '#0f3d5f'}])
        self.assertEqual(spans[0], (9, 28))

    def test_embedded_query_plane_and_option_captions(self):
        line = lambda sql: b'\x03' + shapes.framed(sql) + shapes.framed('AUTHOR') + b'\0' * 12
        container = b'PCS\0' + b'\x14\0\0\0' + decoder.pack(b'\x10\0\0\0' + line('SELECT ') + line('\tA.b') + line('FROM A'))
        chunk = shapes.control_chunk(1, 2, 3, 4, caption='Name')
        source = '\n'.join([
            'report :', ' name : RPT_A', ' embedded_elements :', '  elements :', '   -', '     name : RPT_A$Query',
            '     internal_properties : ' + decoder.encode_properties([{'id': 4, 'version': 0, 'data': container}]),
            'window :', ' name : WIN_A', ' controls :', '  -', '    name : RADIO_A',
            '    internal_properties : ' + shapes.value_of(chunk[:chunk.index(b'Name') + 9] + struct.pack('<I', 3)
                                                           + chunk[chunk.index(b'Name') + 13:]),
            '    type : 6', '    options :', '     -',
            '       internal_properties : ' + shapes.value_of(shapes.framed('Monthly') + b'\x0e' + b'\0' * 20)]) + '\n'
        elements = decoder.decode_source(source)
        query = next(e for e in elements if e['name'] == 'RPT_A$Query')
        self.assertEqual(query['sql'], 'SELECT\n A.b\nFROM A')
        radio = next(e for e in elements if e['name'] == 'RADIO_A')
        self.assertEqual((radio['fields']['plane'], radio['fields']['caption'], radio['kind']), (3, 'Name', 'Radio Button'))
        option = next(e for e in elements if e['owner'] == 'options')
        self.assertEqual(option['fields'], {'caption': 'Monthly'})


if __name__ == '__main__':
    unittest.main()
