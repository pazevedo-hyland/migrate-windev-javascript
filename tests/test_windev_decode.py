import json
from pathlib import Path
import random
import struct
import tempfile
import unittest

from helpers import load

module = load('scripts/windev_decode.py')

# Two values WINDEV wrote for elements left at their defaults (no application content).
CODE_ELEMENTS = 'BQAAAAUAAAD2Rkbx+OjeaV6cz3eLdX7jB0Jgs6WDDXWz15HdSBZm9oeZQ2BKnjRAOa1wH4EQ9d5x'
RAD = 'BQAAAAUAAABoAN7PLpwJW3EiA7WVZdCA5EwrCA1rvutcDHooMWKe'


def framed(text):
    data = text.encode('cp1252')
    return b'\xff\xce\x88\xf1' + struct.pack('<I', len(data) + 13) + data + b'\0\xfe\xed\x98\xe1' if data else b'\0'


def control_chunk(x, y, width, height, caption='', state=0, anchor=0, tab=0, tab_stop=1, link='', group='',
                  tooltip='', value='', menu='', double_click='', visible=1, rates=(1000, 1000, 1000, 1000),
                  button_type=None, tab_style=0):
    """A control's chunk 0 as the format lays it out: type-specific part, common block, type-specific tail."""
    data = b'\x70\x02\0\0' + b'\x11' * 40
    data += struct.pack('<I4i', 0x25f, x, y, width, height) + b'\0' * 8 + b'\xff\xff\xff\x07' * 2
    data += struct.pack('<I', visible) + b'\0' + framed(double_click) + framed(menu)
    data += struct.pack('<I', state) + framed(tooltip) + b'\0' * 12 + struct.pack('<I', 4) + b'\0' * 8
    data += framed(caption) + b'\0' * 4 + framed(value) + struct.pack('<H', anchor) + framed(link)
    data += struct.pack('<IIhHIi', tab_stop, 1, -1, 0, 0, tab - 1) + framed(group) + b'\x01\0' + b'\0' * 10
    data += struct.pack('<4I', *rates)
    tail = bytearray(b'\0' * 60)
    if button_type is not None:
        tail[-50] = button_type
    tail[-58:-54] = struct.pack('<I', tab_style)
    return data + bytes(tail)


def value_of(chunk, identifier=0, version=14):
    return module.encode_properties([{'id': 1, 'version': 0, 'data': b'\x0d\x01' + b'\0' * 20},
                                     {'id': identifier, 'version': version, 'data': chunk}])


class CipherAndPacking(unittest.TestCase):
    def test_values_written_by_windev_decode_and_re_encode_byte_for_byte(self):
        chunks = module.decode_properties(CODE_ELEMENTS)
        self.assertEqual([(c['id'], c['version'], len(c['data'])) for c in chunks], [(5, 65535, 144)])
        self.assertEqual(chunks[0]['data'][:12].hex(), '000000008c00000044000000')
        self.assertEqual(module.encode_properties(chunks), CODE_ELEMENTS)
        chunks = module.decode_properties(RAD)
        self.assertEqual((chunks[0]['id'], chunks[0]['data'].hex()), (3, '23000000030000' + '00' * 28))
        self.assertEqual(module.encode_properties(chunks), RAD)

    def test_cipher_round_trips_every_length(self):
        rng = random.Random(7)
        for length in list(range(0, 70)) + [255, 256, 257, 1000, 1001]:
            data = bytes(rng.randrange(256) for _ in range(length))
            self.assertEqual(module.decrypt(module.encrypt(data)), data, length)
            if length > 1:
                self.assertNotEqual(module.encrypt(data), data)

    def test_packing_round_trips_and_widens_codes(self):
        rng = random.Random(3)
        samples = [b'', b'a', b'abababababababab' * 40, bytes(rng.randrange(256) for _ in range(5000)),
                   bytes(rng.randrange(4) for _ in range(300000))]   # the last fills the 16-bit table
        for data in samples:
            self.assertEqual(module.unpack(module.pack(data)), data)
            self.assertEqual(module.unpack(module.pack(data, stored=True)), data)

    def test_damaged_blocks_are_refused(self):
        packed = module.pack(b'hello hello hello hello')
        with self.assertRaises(ValueError):
            module.unpack(b'\x09' + packed[1:])
        with self.assertRaises(ValueError):
            module.unpack(packed[:14])


class Fields(unittest.TestCase):
    def test_control_fields(self):
        chunk = control_chunk(262, 146, 80, 24, caption='Descrição', state=1, anchor=5, tab=3, link='Customer.Name',
                              group='GR_Edit', tooltip='Help', value='42', menu='<NO CONTEXT MENU>',
                              double_click='BTN_Modify', rates=(666, 333, 1000, 500), button_type=3)
        fields = module.describe('controls', '4', module.decode_properties(value_of(chunk)))
        self.assertEqual((fields['x'], fields['y'], fields['width'], fields['height']), (262, 146, 80, 24))
        self.assertEqual(fields['caption'], 'Descrição')
        self.assertEqual(fields['state'], 'read-only')
        self.assertEqual(fields['anchor'], ['bottom', 'right'])
        self.assertEqual((fields['tab_stop'], fields['tab_order']), (True, 3))
        self.assertEqual(fields['linked_item'], 'Customer.Name')
        self.assertEqual(fields['group'], 'GR_Edit')
        self.assertEqual((fields['tooltip'], fields['initial_value']), ('Help', '42'))
        self.assertEqual((fields['popup_menu'], fields['double_click_button']), ('<NO CONTEXT MENU>', 'BTN_Modify'))
        self.assertEqual(fields['anchor_rates'], {'right': 666, 'width': 333, 'bottom': 1000, 'height': 500})
        self.assertEqual(fields['button_type'], 'abort')
        self.assertNotIn('partial', fields)

    def test_unknown_layout_keeps_geometry_and_says_partial(self):
        chunk = control_chunk(1, 2, 3, 4)
        cut = chunk[:chunk.index(b'\xff\xff\xff\x07') + 8] + b'\xff\xce\x88\xf1garbage'
        fields = module.control_fields(cut)
        self.assertEqual((fields['x'], fields['width']), (1, 3))
        self.assertIn('partial', fields)
        self.assertIsNone(module.control_fields(b'\0' * 64))

    def test_strings_lists_framed_and_utf16_texts_in_order(self):
        data = b'\x01\x02' + framed('First') + b'\0\0' + 'Número'.encode('utf-16le') + b'\0\0' + framed('<DIR>\\a.png')
        self.assertEqual([s['text'] for s in module.strings(data)], ['First', '<DIR>\\a.png', 'Número'])


SOURCE = '''info :
 name : WIN_A
window :
 name : WIN_A
 internal_properties : {window}
 controls :
  -
    name : TAB_Main
    internal_properties : {tab}
    type : 16
    controls :
     -
       name : EDT_Inside
       internal_properties : {inside}
       type : 2
  -
    name : SC_Box
    internal_properties : {box}
    type : 40
    controls :
     -
       name : BTN_Ok
       internal_properties : {button}
       type : 4
       code_elements :
        type_code : 4
        p_codes :
         -
           code : |1+
            name : not a control
            Close()
           type : 18
  -
    name : TABLE_A
    internal_properties : {table}
    columns :
     -
       name : COL_Name
       internal_properties : {column}
       type : 2
    type : 9
'''


def window_chunk(width, height, title='Customers'):
    return (b'\x02\0\0\0\x07\0\x06\0' + b'\0' * 8 + struct.pack('<I4i', 0x25f, 0, 0, width, height) + b'\0' * 20
            + framed('MS Shell Dlg') + b'\0' * 9 + framed(title) + framed('<DIR>\\bg.png') + framed('.\\WIN_A.wdw'))


class Project(unittest.TestCase):
    def source(self, tab_style=0):
        return SOURCE.format(window=value_of(window_chunk(350, 240)),
                             tab=value_of(control_chunk(6, 6, 300, 200, tab_style=tab_style)),
                             inside=value_of(control_chunk(10, 20, 100, 24, caption='Name')),
                             box=value_of(control_chunk(50, 60, 200, 100)),
                             button=value_of(control_chunk(5, 7, 80, 24, button_type=1)),
                             table=value_of(control_chunk(0, 0, 10, 10)),
                             column=value_of(struct.pack('<II', 0x26a, 220) + framed('Descrição') + b'\0' * 30))

    def test_elements_owner_type_parents_and_window_coordinates(self):
        elements = {e['name']: e for e in module.decode_source(self.source())}
        self.assertEqual(elements['WIN_A']['owner'], 'window')
        self.assertEqual((elements['WIN_A']['fields']['width'], elements['WIN_A']['fields']['height']), (350, 240))
        button = elements['BTN_Ok']
        self.assertEqual((button['owner'], button['type'], button['parents']), ('controls', '4', ['WIN_A', 'SC_Box']))
        self.assertEqual((button['fields']['window_x'], button['fields']['window_y']), (55, 67))
        self.assertEqual(button['fields']['button_type'], 'validate')
        inside = elements['EDT_Inside']
        self.assertEqual(inside['parents'], ['WIN_A', 'TAB_Main'])
        # A tab adds where its panes start, known per tab style: 26 px for style 0, 2 px for style 2.
        self.assertEqual((inside['fields']['window_x'], inside['fields']['window_y']), (16, 52))
        self.assertEqual((inside['kind'], elements['TAB_Main']['fields']['pane_top']), ('Edit control', 26))
        flat = {e['name']: e for e in module.decode_source(self.source(tab_style=2))}
        self.assertEqual(flat['EDT_Inside']['fields']['window_y'], 28)
        unknown = {e['name']: e for e in module.decode_source(self.source(tab_style=7))}
        self.assertNotIn('window_x', unknown['EDT_Inside']['fields'])   # an unmeasured style: no position is invented
        self.assertEqual(elements['WIN_A']['fields']['title'], 'Customers')
        self.assertEqual(elements['TABLE_A']['type'], '9')
        self.assertEqual(elements['COL_Name']['fields'], {'width': 220, 'caption': 'Descrição'})
        self.assertEqual(elements['COL_Name']['parents'], ['WIN_A', 'TABLE_A'])

    def test_project_run_writes_properties_queries_images_and_calibration(self):
        with tempfile.TemporaryDirectory() as folder:
            project, out, dossier = Path(folder, 'project'), Path(folder, 'out'), Path(folder, 'dossier')
            project.mkdir()
            (project / 'WIN_A.wdw').write_text(self.source(), encoding='utf-8')
            line = lambda sql: b'\x03' + framed(sql) + framed('AUTHOR') + b'\0' * 12
            query = b'\x10\0\0\0' + line('SELECT ') + line('\tCustomer.Name AS Name') + line('FROM ') + line('\tCustomer')
            image = b'BM' + b'\0' * 200
            (project / 'QRY_Customers.WDR').write_bytes(b'PCS\0' + b'\x14\0\0\0' + b'\x04\x09junk' * 9 + module.pack(query)
                                                        + b'\0\x04\0' + module.pack(image))
            (project / 'notes.txt').write_text('internal_properties : none', encoding='utf-8')
            (dossier / 'windev-window').mkdir(parents=True)
            (dossier / 'windev-window' / 'WIN_A.json').write_text(json.dumps({'controls': {
                'BTN_Ok': {'x': 55, 'y': 67, 'width': 80, 'height': 24, 'tab_order': 0, 'state': 'Active',
                           'button_type': 'Validate',
                           'raw': ['Anchor rate to right 1000 Anchor rate bottom 1000 Anc. rate width 1000 Anchor rate height 1000']},
                'EDT_Inside': {'x': 16, 'y': 52, 'width': 100, 'height': 25, 'tab_order': 5}}}), encoding='utf-8')
            index = module.decode_project(project, out, dossier)
            coverage = index['coverage']
            self.assertEqual((coverage['properties'], coverage['properties_failed']), (7, 0))
            self.assertEqual((coverage['controls'], coverage['controls_with_fields'], coverage['controls_with_caption']), (5, 5, 1))
            self.assertEqual((coverage['containers'], coverage['queries_with_sql'], coverage['images']), (1, 1, 1))
            queries = json.loads((out / 'queries.json').read_text(encoding='utf-8'))
            self.assertEqual(queries, {'QRY_Customers': 'SELECT\n Customer.Name AS Name\nFROM\n Customer'})
            self.assertTrue((out / 'images' / 'QRY_Customers.WDR.1.bmp').read_bytes().startswith(b'BM'))
            self.assertEqual(index['calibration']['size'], {'same': 1, 'different': 1})
            self.assertEqual(index['calibration']['window_position'], {'same': 2, 'different': 0})
            self.assertEqual(index['calibration']['button_type'], {'same': 1, 'different': 0})
            self.assertEqual(index['calibration']['tab_order'], {'same': 1, 'different': 1})
            self.assertEqual(index['calibration']['anchor_rates'], {'same': 1, 'different': 0})
            saved = json.loads((out / 'properties' / 'WIN_A.wdw.json').read_text(encoding='utf-8'))
            self.assertEqual(len(saved['elements']), 7)
            with self.assertRaises(ValueError):
                module.decode_project(project, project / 'inside')
            with self.assertRaises(FileExistsError):
                module.decode_project(project, out)

    def test_evidence_folder_alone_and_over_a_dossier(self):
        with tempfile.TemporaryDirectory() as folder:
            project, dossier = Path(folder, 'project'), Path(folder, 'dossier')
            project.mkdir()
            (project / 'WIN_A.wdw').write_text(self.source() + 'languages :\n - pt-PT\n', encoding='utf-8')
            line = lambda sql: b'\x03' + framed(sql) + framed('AUTHOR') + b'\0' * 12
            (project / 'QRY_Customers.WDR').write_bytes(b'PCS\0' + module.pack(b'\x10\0\0\0' + line('SELECT ') + line('\t1')))
            # Without a dossier: every control gets an entry in the dossier's shape.
            alone = module.decode_project(project, Path(folder, 'alone'), evidence=True)
            self.assertEqual(alone['evidence'], {'elements': 1, 'controls': 6, 'new_elements': 1, 'new_controls': 6,
                                                 'queries': 1})
            window = json.loads(Path(folder, 'alone/evidence/windev-window/WIN_A.json').read_text(encoding='utf-8'))
            self.assertEqual(window['title'], {'pt-PT': 'Customers'})
            self.assertEqual(window['size'], {'x': 0, 'y': 0, 'width': 350, 'height': 240})
            inside = window['controls']['EDT_Inside']
            self.assertEqual((inside['kind'], inside['x'], inside['y'], inside['width'], inside['caption']),
                             ('Edit control', 16, 52, 100, {'pt-PT': 'Name'}))
            self.assertEqual((inside['tab_order'], inside['state']), (-1, 'Active'))
            self.assertIn('Anchor <None>', inside['raw'])
            self.assertEqual(window['controls']['BTN_Ok']['button_type'], 'Validate')
            self.assertEqual(window['controls']['COL_Name'], {'raw': [], 'kind': 'Table column', 'width': 220,
                                                              'caption': {'pt-PT': 'Descrição'}, 'decoded': ['width', 'caption']})
            query = json.loads(Path(folder, 'alone/evidence/query/QRY_Customers.json').read_text(encoding='utf-8'))
            self.assertEqual(query['sql'], 'SELECT\n 1')
            # Over a dossier: decoded values replace the PDF's, what only the PDF has stays, its spelling of names too.
            (dossier / 'windev-window').mkdir(parents=True)
            (dossier / 'query').mkdir()
            (dossier / 'index.json').write_text(json.dumps({'images': True, 'coverage': {}}), encoding='utf-8')
            (dossier / 'windev-window' / 'win_a.json').write_text(json.dumps({'title': {'PT': 'Cust omers'}, 'controls': {
                'edt_inside': {'kind': 'Edit control', 'caption': {'PT': 'Nam e'}, 'input_mask': '999', 'x': 1, 'y': 1,
                               'raw': ['Anchor Width', 'Input mask PT: 999']}}}), encoding='utf-8')
            (dossier / 'query' / 'QRY_Customers.json').write_text(json.dumps({'sql': 'SELECT\n1', 'parameters': []}),
                                                                  encoding='utf-8')
            module.decode_project(project, Path(folder, 'merged'), dossier, evidence=True)
            merged = json.loads(Path(folder, 'merged/evidence/windev-window/win_a.json').read_text(encoding='utf-8'))
            control = merged['controls']['edt_inside']
            self.assertEqual((control['caption'], control['input_mask'], control['x'], control['y']), ({'PT': 'Name'}, '999', 16, 52))
            self.assertEqual(control['raw'][0], 'Anchor Width')            # the dossier's own anchor line is kept
            self.assertEqual(merged['title'], {'PT': 'Customers'})
            self.assertIn('BTN_Ok', merged['controls'])                    # a control the dossier lacked
            query = json.loads(Path(folder, 'merged/evidence/query/QRY_Customers.json').read_text(encoding='utf-8'))
            self.assertEqual((query['sql'], query['sql_pdf'], query['parameters']), ('SELECT\n 1', 'SELECT\n1', []))
            self.assertTrue(json.loads(Path(folder, 'merged/evidence/index.json').read_text(encoding='utf-8'))['decoded']['dossier'])
            self.assertEqual(json.loads((dossier / 'windev-window' / 'win_a.json').read_text(encoding='utf-8'))['title'],
                             {'PT': 'Cust omers'})                          # the extract itself is not touched

    def test_inspector_layout_gets_decoded_geometry(self):
        inspector = load('scripts/inspect_windev.py')
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            project.mkdir()
            (project / 'WIN_A.wdw').write_text(self.source(), encoding='utf-8')
            inspector.inspect(project, Path(folder, 'out'))
            code = json.loads(Path(folder, 'out/code/WIN_A.wdw.json').read_text(encoding='utf-8'))
        layout = {item['name']: item for item in code['layout']}
        self.assertEqual(code['layout_source'], 'internal_properties')
        self.assertEqual([layout['BTN_Ok'][key] for key in ('x', 'y', 'width', 'height')], [55, 67, 80, 24])
        self.assertEqual((layout['EDT_Inside']['x'], layout['EDT_Inside']['y']), (16, 52))
        self.assertEqual(layout['COL_Name']['width'], 220)
        self.assertEqual(code['controls'], ['TAB_Main', 'EDT_Inside', 'SC_Box', 'BTN_Ok', 'TABLE_A', 'COL_Name'])

    def test_a_value_that_does_not_decode_is_reported_not_guessed(self):
        elements = module.decode_source('window :\n name : W\n internal_properties : BQAAAAUAAAAAAAAAAAAAAAAA\n')
        self.assertIn('error', elements[0])
        self.assertNotIn('fields', elements[0])


if __name__ == '__main__':
    unittest.main()
