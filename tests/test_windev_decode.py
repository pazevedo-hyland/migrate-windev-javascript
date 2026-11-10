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
            self.assertEqual(window['controls']['COL_Name'], {'raw': [], 'kind': 'Table column', 'width': 220, 'column_index': 1,
                                                              'caption': {'pt-PT': 'Descrição'},
                                                              'decoded': ['width', 'column_index', 'caption']})
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


def font_record(face, height=-11, h_align=0, v_align=0, colour=(0x2d, 0x2d, 0x2d)):
    """A font as a control keeps it: tag, alignment, LOGFONT, face, text colour."""
    return (struct.pack('<I', 0x25b) + b'\0\0\0\xff' + b'\0' * 4 + struct.pack('<II', h_align, v_align)
            + struct.pack('<iiiiIBBBB4B', height, 0, 0, 0, 400, 0, 0, 0, 0, 3, 2, 1, 0x22) + framed(face) + bytes(colour) + b'\0')


def edit_chunk(caption_width=64, size=30, kind=1, value_type=13, align=2, mask='999,99', returned='', shift=0, **common):
    """An edit control's chunk 0: style, a frame, the caption's font and width, the common block, the edit record."""
    head = (b'\x70\x02\0\0' + b'\x13\x07\0\0' + b'\x60\x1b\0\0' + framed('170 AquaBlue.SAI_Simple')
            + struct.pack('<II', 0x262, 0x18) + bytes([0xfd, 0xfd, 0xfd, 0, 0x0c, 0x3c, 0x60, 0])
            + font_record('Trebuchet MS', v_align=1) + b'\0' * 20 + struct.pack('<II', 4, caption_width) + b'\0' * 40)
    block = control_chunk(6, 6, 400, 24, **common)[44:-60]
    tail = (b'\0' * (26 + shift) + b'\xff\xff\xff\x7f' + b'\0' * 21 + struct.pack('<III', 1, 0x286, size) + b'\0' * 8
            + struct.pack('<IHB', kind, value_type, align) + b'\0' * 43 + framed(mask) + framed(returned) + b'\0' * 40)
    return head + block + tail


def column_chunk(width, caption, align=2, sortable=1, moveable=0, link='Order.total', adjustable=1, multiline=0, search=1):
    return (struct.pack('<II', 0x26a, width) + framed(caption) + struct.pack('<5I', align, 1, 0xe, sortable, moveable)
            + b'\0' * 12 + framed(link) + struct.pack('<6I', 2, adjustable, 1, 1, multiline, search) + b'\0' * 40)


def report_element(name, top, bottom, left, right, code):
    return framed(name) + b'\x11' * 8 + struct.pack('<4d', top, bottom, left, right) + bytes([code]) + b'\0' * 40


class KindRecords(unittest.TestCase):
    def test_edit_record_style_caption_width_and_frames(self):
        for shift in (0, 4):       # some windows keep four more bytes per control before the record
            source = '\n'.join(['window :', ' name : WIN_A', ' controls :', '  -', '    name : EDT_Total',
                                '    internal_properties : ' + value_of(edit_chunk(shift=shift, caption='Total')),
                                '    type : 2']) + '\n'
            edit = module.decode_source(source)[0]
            fields = edit['fields']
            self.assertEqual((fields['style'], fields['caption'], fields['caption_width']), ('170 AquaBlue.SAI_Simple', 'Total', 64))
            self.assertEqual((fields['input_size'], fields['input_type'], fields['value_type'], fields['h_align']),
                             (30, 'numeric', 13, 'right'))
            self.assertEqual((fields['input_mask'], fields['return_format']), ('999,99', ''))
            self.assertEqual(edit['frames'], [{'type': 0x18, 'border_colour': '#0c3c60', 'background': '#fdfdfd'}])
            self.assertEqual((edit['fonts'][0]['h_align'], edit['fonts'][0]['v_align'], edit['fonts'][0]['colour']),
                             ('left', 'center', '#2d2d2d'))
        # Another layout after the common block: nothing of the record is read.
        other = edit_chunk()
        self.assertIsNone(module.edit_record(other.replace(struct.pack('<II', 1, 0x286), struct.pack('<II', 0, 0x286)),
                                             module.control_fields(other)['_end']))

    def test_static_alignment_comes_from_its_font(self):
        chunk = control_chunk(1, 2, 90, 20, caption='Late')
        chunk = chunk[:4] + font_record('Tahoma', h_align=3, v_align=1, colour=(0xfe, 0, 0)) + chunk[4:]
        fields = module.describe('controls', '3', [{'id': 0, 'version': 14, 'data': chunk}])
        self.assertEqual((fields['h_align'], fields['v_align'], fields['caption']), ('justified', 'center', 'Late'))
        self.assertNotIn('h_align', module.describe('controls', '4', [{'id': 0, 'version': 14, 'data': chunk}]))

    def test_column_options_and_its_cell(self):
        source = '\n'.join([
            'window :', ' name : WIN_A', ' controls :', '  -', '    name : TABLE_A', '    columns :', '     -',
            '       name : COL_Total', '       internal_properties : ' + value_of(column_chunk(80, 'Total')),
            '       content :', '        internal_properties : ' + value_of(edit_chunk(mask='', returned='')),
            '        type : 2', '       type : 2', '    type : 9']) + '\n'
        elements = module.decode_source(source)
        column = next(e for e in elements if e['owner'] == 'columns')
        self.assertEqual(column['fields'], {'width': 80, 'caption': 'Total', 'h_align': 'right', 'sortable': True,
                                            'moveable': False, 'linked_item': 'Order.total', 'adjustable_width': True,
                                            'multiline': False, 'with_search': True})
        cell = next(e for e in elements if e['owner'] == 'content')
        self.assertEqual((cell['kind'], cell['fields']['input_type'], cell['parents'][-1]), ('Edit control', 'numeric', 'COL_Total'))
        self.assertNotIn('caption_width', cell['fields'])
        # Options that are not yes/no: only width and caption are kept.
        odd = module.column_fields(column_chunk(80, 'Total', sortable=7))
        self.assertEqual(odd, {'width': 80, 'caption': 'Total'})

    def test_report_page_bands_and_control_kinds(self):
        page = (b'\x59\0' + framed('RPT_A') + b'\x22' * 8 + b'\0' + struct.pack('<4I', 4, 6, 0, 0) + b'\0' * 7
                + framed('No data.') + framed('Wait.') + b'\0' * 21
                + struct.pack('<10d', 38, 62, 1, 2, 3, 4, 1, 1, 1, 2) + b'\0' * 30)
        source = '\n'.join([
            'report :', ' name : RPT_A', ' internal_properties : ' + value_of(page, 15), ' blocks :', '  -',
            '    name : BODY', '    internal_properties : ' + value_of(report_element('BODY', 0, 32, 0, 60, 4), 15),
            '    controls :', '     -', '       name : STC_Code',
            '       internal_properties : ' + value_of(report_element('STC_Code', 1, 6, 2, 30, 39), 15),
            '     -', '       name : ITEM_New',
            '       internal_properties : ' + value_of(report_element('ITEM_New', 1, 6, 32, 50, 99), 15)]) + '\n'
        elements = {e['name']: e for e in module.decode_source(source, suffix='.wde')}
        self.assertEqual(elements['RPT_A']['fields'], {
            'report_type': 'label', 'data_source': 'text file', 'page_format_code': 0, 'page_height_mm': 38.0,
            'page_width_mm': 62.0, 'margins_mm': {'top': 1.0, 'bottom': 2.0, 'left': 3.0, 'right': 4.0}})
        self.assertEqual((elements['BODY']['fields']['band'], elements['BODY']['fields']['height_mm']), ('body', 32.0))
        self.assertEqual((elements['STC_Code']['kind'], elements['STC_Code']['fields']['x_mm']), ('Static', 2.0))
        # A type this table does not name keeps its code and gets no kind.
        self.assertEqual((elements['ITEM_New'].get('kind'), elements['ITEM_New']['fields']['type_code']), (None, 99))

    def test_evidence_carries_the_new_fields_in_the_dossier_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            project, dossier = Path(folder, 'project'), Path(folder, 'dossier')
            project.mkdir()
            (project / 'WIN_A.wdw').write_text('\n'.join([
                'window :', ' name : WIN_A', ' controls :', '  -', '    name : EDT_Total',
                '    internal_properties : ' + value_of(edit_chunk(caption='Total', returned='AAAAMMJJ')), '    type : 2',
                '  -', '    name : TABLE_A', '    internal_properties : ' + value_of(control_chunk(0, 40, 300, 90)),
                '    columns :', '     -', '       name : COL_Total',
                '       internal_properties : ' + value_of(column_chunk(80, 'Total')), '       content :',
                '        internal_properties : ' + value_of(edit_chunk(mask='99', kind=1, value_type=8)),
                '        type : 2', '       type : 2', '    type : 9', 'languages :', ' - pt-PT']) + '\n', encoding='utf-8')
            (dossier / 'windev-window').mkdir(parents=True)
            (dossier / 'windev-window' / 'WIN_A.json').write_text(json.dumps({'controls': {
                'EDT_Total': {'kind': 'Edit control', 'x': 6, 'y': 6, 'width': 400, 'height': 24, 'input_type': 'High-pre',
                              'input_size': 30, 'input_mask': {'PT': '999,99'},
                              'raw': ['Horz. alignment Right', 'Inside X position 70', 'Inside width 336', 'Input size 30',
                                      'Return format AAAAMMJJ']},
                'COL_Total': {'kind': 'Table column', 'h_align': 'Right', 'input_type': 'Numeric', 'input_mask': {'PT': '9'},
                              'flags': {'Sortable column': True, 'Moveable': False, 'Adjustable width': True,
                                        'Multiline': False, 'With search': False}}}}), encoding='utf-8')
            index = module.decode_project(project, Path(folder, 'out'), dossier)
            alone = module.decode_project(project, Path(folder, 'alone'), evidence=True)
            window = json.loads(Path(folder, 'alone/evidence/windev-window/WIN_A.json').read_text(encoding='utf-8'))
        calibration = index['calibration']
        for field in ('input_type', 'input_size', 'input_mask', 'return_format', 'edit_alignment', 'input_area',
                      'column_alignment', 'column_input_type', 'column_input_mask'):
            self.assertEqual(calibration[field], {'same': 1, 'different': 0}, field)
        self.assertEqual(calibration['column_options'], {'same': 4, 'different': 1})        # With search differs
        self.assertEqual(alone['evidence']['controls'], 3)
        edit = window['controls']['EDT_Total']
        self.assertEqual((edit['input_type'], edit['input_size'], edit['input_mask'], edit['h_align'], edit['style']),
                         ('Numeric', 30, {'pt-PT': '999,99'}, 'Right', '170 AquaBlue.SAI_Simple'))
        for line in ('Return format AAAAMMJJ', 'Horz. alignment Right', 'Inside X position 70', 'Inside width 336'):
            self.assertIn(line, edit['raw'])
        column = window['controls']['COL_Total']
        self.assertEqual((column['h_align'], column['linked_item'], column['input_type'], column['input_mask']),
                         ('Right', 'Order.total', 'Numeric', {'pt-PT': '99'}))
        self.assertEqual(column['flags'], {'Sortable column': True, 'Moveable': False, 'Adjustable width': True,
                                           'Multiline': False, 'With search': True})
        self.assertEqual((column['column_index'], calibration.get('column_index')), (1, None))     # the dossier gave no index


class Buttons(unittest.TestCase):
    def test_image_states_and_background_stretch(self):
        def button(stretch, background='<DIR>\\Btn.png'):
            fonts = b''.join(font_record('Tahoma', h_align=1, v_align=1) + b'\0' * 12 for _ in range(4))
            head = b'\x70\x02\0\0' + b'\x31\x04\0\0' + fonts[:-12] + b'\0' * 48 + struct.pack('<I', stretch) + b'\0' * 30
            tail = (b'\0' * 26 + b'\xff\xff\xff\x7f' + b'\0' * 77 + framed('Save') + framed(background) + struct.pack('<I', 5)
                    + framed('ok.png') + struct.pack('<I', 3) + b'\0' * 60)
            return head + control_chunk(1, 2, 80, 24)[44:-60] + tail
        read = lambda chunk: module.describe('controls', '4', [{'id': 0, 'version': 14, 'data': chunk}])
        fields = read(button(2))
        self.assertEqual((fields['caption'], fields['background_states'], fields['image'], fields['image_states']),
                         ('Save', 5, 'ok.png', 3))
        self.assertEqual(fields['background_stretch'], 'width and height')
        self.assertEqual(read(button(0))['background_stretch'], 'custom 9-slice scaling')
        self.assertNotIn('background_stretch', read(button(7)))                 # a value not measured: not named
        self.assertNotIn('background_stretch', read(button(0, background='')))   # nothing to stretch


def list_chunk(memory, content='', file='', item='', shown='', stored=''):
    tail = (b'\0' * 26 + b'\xff\xff\xff\x7f' + b'\0' * 21 + struct.pack('<IIII', 1, 0x270, 0, memory) + b'\0' * 4
            + framed(content) + framed(file) + framed(item) + struct.pack('<I', 1) + framed(shown) + framed(stored)
            + b'\0' * 64)
    return control_chunk(4, 5, 200, 22, caption='Station')[:-60] + tail


class Lists(unittest.TestCase):
    def test_a_string_is_utf8_when_it_can_be_and_the_code_page_otherwise(self):
        self.assertEqual(module.text('Início'.encode('utf-8')), 'Início')
        self.assertEqual(module.text('Início'.encode('cp1252')), 'Início')
        self.assertEqual(module.text('JOÃO'.encode('cp1252')), 'JOÃO')
        self.assertEqual(module.text(b'plain'), 'plain')

    def test_combo_binding_and_typed_content_reach_the_combo_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            project, dossier = Path(folder, 'project'), Path(folder, 'dossier')
            project.mkdir()
            (project / 'WIN_A.wdw').write_text('\n'.join([
                'window :', ' name : WIN_A', ' controls :', '  -', '    name : COMBO_Station',
                '    internal_properties : ' + value_of(control_chunk(4, 5, 200, 22, caption='Station')), '    type : 14',
                '    dropdown :', '     internal_properties : ' + value_of(list_chunk(0, '', 'Station', 'code', 'label', 'code')),
                '     type : 7',
                '  -', '    name : COMBO_Month',
                '    internal_properties : ' + value_of(control_chunk(4, 35, 200, 22)), '    type : 14',
                '    dropdown :', '     internal_properties : ' + value_of(list_chunk(1, 'January\r\nFebruary')),
                '     type : 7', 'languages :', ' - en-GB']) + '\n', encoding='utf-8')
            (dossier / 'windev-window').mkdir(parents=True)
            (dossier / 'windev-window' / 'WIN_A.json').write_text(json.dumps({'controls': {
                'COMBO_Station': {'kind': 'Combo Box', 'row': 'Active File wit', 'caption': {'GB': 'Station'},
                                  'raw': ['Browsed file Station', 'Browsed item code', 'Displayed item label',
                                          'Stored item id']},
                'COMBO_Month': {'kind': 'Combo Box', 'row': 'Active Memory', 'caption': {'GB': ''},
                                'raw': ['Initial content GB: January']}}}), encoding='utf-8')
            index = module.decode_project(project, Path(folder, 'out'), dossier)
            module.decode_project(project, Path(folder, 'alone'), evidence=True)
            window = json.loads(Path(folder, 'alone/evidence/windev-window/WIN_A.json').read_text(encoding='utf-8'))
        self.assertEqual(index['calibration']['list_source'], {'same': 2, 'different': 0})
        self.assertEqual(index['calibration']['list_binding'], {'same': 3, 'different': 1})      # the stored item differs
        self.assertEqual(index['calibration']['list_initial_content'], {'same': 1, 'different': 0})
        station, month = window['controls']['COMBO_Station'], window['controls']['COMBO_Month']
        self.assertEqual((station['list_source'], station['browsed_file'], station['browsed_item'], station['displayed_item'],
                          station['stored_item']), ('file', 'Station', 'code', 'label', 'code'))
        self.assertEqual((month['list_source'], month['initial_content']), ('memory', ['January', 'February']))
        self.assertIsNone(module.list_record(list_chunk(5), module.control_fields(list_chunk(5))['_end']))


class WindowsAndSkins(unittest.TestCase):
    def test_window_options(self):
        def window(bar, menu, minimize, maximize, context, opening=3, image='<DIR>\\bg.png'):
            return (b'\x02\0\0\0\x07\0\x06\0' + b'\0' * 8 + struct.pack('<I4i', 0x25f, 0, 0, 640, 480) + b'\0' * 8
                    + font_record('MS Shell Dlg') + b'\0' * 308 + bytes([opening]) + b'\0' * 3 + framed('Orders') + framed(image)
                    + b'\0' * 5 + struct.pack('<4I', bar, menu, minimize, maximize) + b'\0' * 25 + struct.pack('<I', context)
                    + b'\0' * 30)
        fields = module.describe('window', '', [{'id': 0, 'version': 14, 'data': window(1, 1, 0, 1, 1, opening=2)}])
        self.assertEqual((fields['width'], fields['title'], fields['background_image'], fields['opening_mode']),
                         (640, 'Orders', '<DIR>\\bg.png', 'Centered in the screen'))
        self.assertEqual((fields['title_bar'], fields['system_menu'], fields['minimize_icon'], fields['maximize_icon'],
                          fields['independent_hfsql_context']), (True, True, False, True, True))
        # Something else where the yes/no values should be: the options are not read, size and title still are.
        odd = module.describe('window', '', [{'id': 0, 'version': 14, 'data': window(9, 1, 0, 1, 1)}])
        self.assertEqual((odd['width'], 'title_bar' in odd), (640, False))

    def test_skin_styles_and_what_a_control_changed(self):
        style = lambda name, colour: (framed('25.0.225.3') + b'\0' * 30 + font_record('Tahoma', colour=colour) + b'\0' * 20
                                      + struct.pack('<II', 0x262, 1) + b'\0\0\0\xff' + bytes([0x0c, 0x3c, 0x60, 0])
                                      + framed('D:\\Skins\\Std.png') + b'\0' * 12 + framed(name) + b'\0' * 9)
        sty = b'PCS\0' + b'\0' * 40 + style('LIB_Simple', (0x2d, 0x2d, 0x2d)) + style('LIB_Title', (0, 0, 0x80))
        styles = module.skin_styles(sty)
        self.assertEqual(list(styles), ['LIB_Simple', 'LIB_Title'])
        self.assertEqual((styles['LIB_Title']['fonts'][0]['colour'], styles['LIB_Simple']['images'],
                          styles['LIB_Simple']['frames']), ('#000080', ['Std.png'], [{'type': 1, 'border_colour': '#0c3c60'}]))
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            (project / 'Templates' / '170 Blue').mkdir(parents=True)
            (project / 'Templates' / '170 Blue' / 'Blue.sty').write_bytes(sty)
            chunk = control_chunk(1, 2, 90, 20, caption='Late')
            head = (b'\x70\x02\0\0' + b'\0' * 8 + b'\x60\x1b\0\0' + framed('170 Blue.LIB_Simple')
                    + font_record('Tahoma', colour=(0xfe, 0, 0)) + b'\0' * 20
                    + struct.pack('<II', 0x262, 1) + b'\0\0\0\xff' + bytes([0x0c, 0x3c, 0x60, 0]) + b'\0' * 20)
            (project / 'WIN_A.wdw').write_text('\n'.join(['window :', ' name : WIN_A', ' controls :', '  -', '    name : STC_Late',
                                                          '    internal_properties : ' + value_of(head + chunk[44:]),
                                                          '    type : 3']) + '\n', encoding='utf-8')
            index = module.decode_project(project, Path(folder, 'out'))
            saved = json.loads(Path(folder, 'out/properties/WIN_A.wdw.json').read_text(encoding='utf-8'))
            skin = json.loads(Path(folder, 'out/skin/170 Blue.json').read_text(encoding='utf-8'))
        self.assertEqual((index['coverage']['skin_styles'], index['coverage']['controls_with_skin_style'],
                          index['coverage']['controls_changed_from_skin_style']), (2, 1, 1))
        self.assertEqual(saved['elements'][0]['differs_from_style'], ['fonts[0].colour: #fe0000 (style #2d2d2d)'])
        self.assertEqual(sorted(skin['styles']), ['LIB_Simple', 'LIB_Title'])


class PredefinedActions(unittest.TestCase):
    def test_an_action_naming_an_element_reaches_the_evidence(self):
        usual = b'\x01\0\0\0' + b'\0' * 40 + framed('*') * 3 + framed('23') + framed('0') + b'\0' * 60
        named = usual + struct.pack('<4I', 1100, 61, 1, 31) + framed('RPT_List_Items') + b'\0' * 20
        self.assertIsNone(module.action_fields(usual))
        self.assertEqual(module.action_fields(named), {'action_code': 1100, 'action_target': 'RPT_List_Items'})
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            project.mkdir()
            (project / 'WIN_A.wdw').write_text('\n'.join([
                'window :', ' name : WIN_A', ' controls :', '  -', '    name : BTN_Print',
                '    internal_properties : ' + value_of(control_chunk(1, 2, 80, 24)), '    type : 4',
                '    code_elements :', '     type_code : 4', '     p_codes :', '      -',
                '        internal_properties : ' + value_of(named, 9, 65535), '        type : 18']) + '\n', encoding='utf-8')
            module.decode_project(project, Path(folder, 'out'), evidence=True)
            window = json.loads(Path(folder, 'out/evidence/windev-window/WIN_A.json').read_text(encoding='utf-8'))
        self.assertEqual(window['predefined_actions'], [{'control': 'BTN_Print', 'target': 'RPT_List_Items', 'code': 1100}])


class BinaryWindows(unittest.TestCase):
    """A window saved in binary format: the same records, each with its name inside and its length and type before."""

    def element(self, name, kind, chunk, children=b''):
        tag = chunk.index(struct.pack('<I', 0x25f))
        body = chunk[:tag + 4] + framed(name) + b'\x99' * 8 + chunk[tag + 4:] + children
        return struct.pack('<II', len(body) + 8, kind) + body

    def block(self):
        edit = edit_chunk(caption='Total')
        button = control_chunk(5, 6, 80, 24, caption='', button_type=1)
        button = b'\x70\x02\0\0' + b'\0' * 4 + b'\x10\x01\0\0' + button[12:]
        box = control_chunk(10, 20, 300, 200)
        box = b'\x70\x02\0\0' + b'\0' * 4 + b'\x60\x1b\0\0' + box[12:]
        window = struct.pack('<I', 0x25f) + framed('WIN_A') + b'\x77' * 8 + struct.pack('<4i', 0, 0, 640, 480) + b'\0' * 40
        return (window + self.element('SC_Box', 40, box, self.element('BTN_Ok', 4, button))
                + self.element('EDT_Total', 2, edit))

    def test_controls_types_parents_and_fields(self):
        elements = module.binary_window(self.block())
        self.assertEqual([(e['owner'], e['name'], e['type'], e['parents']) for e in elements], [
            ('window', 'WIN_A', '', []), ('controls', 'SC_Box', '40', ['WIN_A']),
            ('controls', 'BTN_Ok', '4', ['WIN_A', 'SC_Box']), ('controls', 'EDT_Total', '2', ['WIN_A'])])
        self.assertEqual(elements[0]['fields'], {'x': 0, 'y': 0, 'width': 640, 'height': 480})
        button, edit = elements[2], elements[3]
        self.assertEqual((button['kind'], button['fields']['button_type'], button['fields']['window_x'], button['fields']['window_y']),
                         ('Button', 'validate', 15, 26))
        self.assertEqual((edit['fields']['caption'], edit['fields']['input_type'], edit['fields']['input_mask'],
                          edit['fields']['style'], edit['fields']['caption_width']),
                         ('Total', 'numeric', '999,99', '170 AquaBlue.SAI_Simple', 64))
        # A length that runs past the block: that element is left out, the others stay.
        broken = self.block().replace(struct.pack('<I', 2) + b'\x70\x02', struct.pack('<I', 2) + b'\x70\x02', 1)
        self.assertEqual(len(module.binary_window(broken[:-200])), 3)

    def test_a_binary_window_without_a_text_source_is_decoded_by_the_project_run(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            project.mkdir()
            (project / 'WIN_A.wdw').write_bytes(b'PCS\0' + b'\x14\0\0\0' + module.pack(self.block()))
            index = module.decode_project(project, Path(folder, 'out'), evidence=True)
            saved = json.loads(Path(folder, 'out/properties/WIN_A.wdw.json').read_text(encoding='utf-8'))
            window = json.loads(Path(folder, 'out/evidence/windev-window/WIN_A.json').read_text(encoding='utf-8'))
        self.assertEqual((index['coverage']['binary_windows'], index['coverage']['binary_window_controls']), (1, 3))
        self.assertEqual(saved['format'], 'binary')
        self.assertEqual((window['size']['width'], window['controls']['EDT_Total']['input_type'],
                          window['controls']['BTN_Ok']['button_type'], window['controls']['BTN_Ok']['x']),
                         (640, 'Numeric', 'Validate', 15))


class BinaryParts(unittest.TestCase):
    """What sits inside a control's record in a binary window, and the code block."""

    def test_columns_cells_panes_and_options(self):
        helper = BinaryWindows()
        table = control_chunk(0, 40, 300, 90)
        table = b'\x70\x02\0\0' + b'\0' * 4 + b'\x6f\x02\0\0' + table[12:]
        cell = edit_chunk(mask='99', kind=1, value_type=8)
        tag = cell.index(struct.pack('<I', 0x25f))
        cell = cell[:tag + 4] + b'\0' + b'\x55' * 8 + cell[tag + 4:]          # no name: one zero byte
        text_column = column_chunk(80, 'Total')
        linked = text_column.index(b'Order.total') + len(b'Order.total') + 5
        column = (struct.pack('<I', 2) + framed('COL_Total') + text_column[:4] + framed('COL_Total') + b'\x33' * 8
                  + text_column[4:linked + 4] + struct.pack('<I', 2) + cell[:-20]
                  + text_column[linked + 4:linked + 24] + b'\0' * 50 + b'\xba\xab\xba\xab')
        tab = control_chunk(0, 0, 400, 300)
        tab = b'\x70\x02\0\0' + b'\0' * 4 + b'\x60\x1b\0\0' + tab[12:]
        pane = lambda caption: b'\x5a\x02\0\0' + framed(caption) + b'\0' * 12
        radio = control_chunk(5, 5, 100, 40)
        radio = b'\x70\x02\0\0' + b'\0' * 4 + b'\x60\x1b\0\0' + radio[12:-60] + b'\0' * 30 \
            + framed('Monthly') + b'\x0e\0\0\0' + b'\0' * 8 + framed('Yearly') + b'\x0e\0\0\0' + b'\0' * 30
        window = struct.pack('<I', 0x25f) + framed('WIN_A') + b'\x77' * 8 + struct.pack('<4i', 0, 0, 640, 480) + b'\0' * 40
        block = window + helper.element('TAB_Main', 16, tab, pane('First') + helper.element('TABLE_A', 9, table, column)
                                        + pane('Second') + helper.element('RADIO_Period', 6, radio) + b'\0' * 58)
        elements = module.binary_window(block)
        shape = [(e['owner'], e['name'] or e['fields'].get('caption'), e.get('pane')) for e in elements]
        self.assertEqual(shape, [('window', 'WIN_A', None), ('controls', 'TAB_Main', None), ('tabs', 'First', 1),
                                 ('controls', 'TABLE_A', 1), ('columns', 'COL_Total', None), ('content', '', None),
                                 ('tabs', 'Second', 2), ('controls', 'RADIO_Period', 2), ('options', 'Monthly', None),
                                 ('options', 'Yearly', None)])
        column = next(e for e in elements if e['owner'] == 'columns')
        self.assertEqual((column['fields']['width'], column['fields']['caption'], column['fields']['linked_item'],
                          column['fields']['h_align'], column['index'], column['parents']),
                         (80, 'Total', 'Order.total', 'right', 1, ['WIN_A', 'TAB_Main', 'TABLE_A']))
        content = next(e for e in elements if e['owner'] == 'content')
        self.assertEqual((content['kind'], content['fields']['input_mask'], content['parents'][-1]), ('Edit control', '99', 'COL_Total'))

    def test_code_blocks_with_their_control_and_event(self):
        line = lambda text, author='': b'\x03' + framed(text) + framed(author) + b'\0' * 12
        header = lambda event, lines, tag=0x14: (bytes([tag]) + struct.pack('<III', 99, len(lines), event) + b'\0' * 4
                                                 + struct.pack('<I', 1) + b''.join(lines))
        block = (b'\x01\0\0\0' + b'\0' * 20 + header(34, [line('Init()')]) + b'\0' * 30
                 + struct.pack('<I', 4) + framed('BTN_Save') + b'\0' * 40
                 + header(18, [line('IF Check() THEN', 'ANA'), line(''), line('\tSave()', 'ANA'), line('END')], tag=0x15)
                 + b'\0' * 20 + header(458752, [line('PROCEDURE Check()'), line('RESULT True')]))
        self.assertEqual(module.binary_code(block), [
            {'control': None, 'event': 34, 'lines': ['Init()']},
            {'control': 'BTN_Save', 'event': 18, 'lines': ['IF Check() THEN', '', '\tSave()', 'END']},
            {'control': 'BTN_Save', 'event': 458752, 'lines': ['PROCEDURE Check()', 'RESULT True']}])
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            project.mkdir()
            (project / 'WIN_A.wdw').write_bytes(b'PCS\0' + b'\x14\0\0\0' + module.pack(BinaryWindows().block()) + b'\0\0'
                                                + module.pack(block))
            index = module.decode_project(project, Path(folder, 'out'))
            listing = Path(folder, 'out/code/WIN_A.wdw.wl').read_text(encoding='utf-8').splitlines()
            data = json.loads(Path(folder, 'out/code/WIN_A.wdw.json').read_text(encoding='utf-8'))
        self.assertEqual((index['coverage']['binary_elements_with_code'], index['coverage']['binary_code_blocks']), (1, 3))
        self.assertEqual(listing[:2], ['// ---- WIN_A : event 34', 'Init()'])
        self.assertEqual((data['blocks'][1]['control'], data['blocks'][1]['line'], listing[data['blocks'][1]['line'] - 1]),
                         ('BTN_Save', 5, 'IF Check() THEN'))


if __name__ == '__main__':
    unittest.main()
