import csv
import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/inspect_windev.py')

NESTED = '''- name : WIN_Order
  type : 65538
  code : |1-
   // window init
  controls :
    - name : BTN_Save
      type : 65537
      code_elements :
        p_codes :
          - code : |1-
             PROCEDURE Fake()
             name : not structure
             pwd = "hunter22"
            type : 851977
          - code : |1-
             Save()
            type : 851978
'''

# Shape observed in real WINDEV 27 text exports: list items are a bare `-` line.
REAL_SHAPE = '''window :
 name : WIN_Order
 controls :
  -
    name : BTN_Cancel
    type : 4
    code_elements :
     type_code : 3
     p_codes :
      -
        code : |1-
         Close()
        type : 18
  -
    name : BTN_Save
    code_elements :
     p_codes :
      -
        code : |1-
         
        type : 14
      -
        code : |1-
         IF sPassword = INIRead("x", "password", "") THEN
        type : 18
      -
        code : |1-
         Save()
        type : 33
 code_elements :
  p_codes :
   -
     code : |1-
      PROCEDURE MyWindow(gMode is string)
   -
     code : |1-
      cnx..Password = "s3cret"
     type : 34
'''


class InspectionTests(unittest.TestCase):
    def test_control_names_include_nested_controls_and_columns(self):
        text = '''window :
 name : WIN_List
 controls :
  -
    name : TABLE_X
    columns :
     -
       name : COL_Code
    code_elements :
     p_codes :
      -
        code : |1-
         name : not_a_control
  - name : BTN_Ok
    controls :
     -
       name : EDT_Inner
'''
        self.assertEqual(module.control_names(text), ['TABLE_X', 'COL_Code', 'BTN_Ok', 'EDT_Inner'])

    def test_real_shape_bare_list_items(self):
        blocks = module.extract_blocks(REAL_SHAPE)
        got = [('/'.join(b['context']['names']), b['context']['siblings'].get('type')) for b in blocks]
        self.assertEqual(got, [('WIN_Order/BTN_Cancel', '18'), ('WIN_Order/BTN_Save', '18'),
                               ('WIN_Order/BTN_Save', '33'), ('WIN_Order', None), ('WIN_Order', '34')])
        self.assertEqual(blocks[3]['procedures'], ['MyWindow'])
        hints = module.secret_hints('w.wdw', blocks)
        self.assertEqual([h['line'] for h in hints], [blocks[4]['start_line']])

    def test_literal_blocks_keep_lines_and_stop_at_sibling(self):
        text = 'name : Save\n  code : |1-\n   IF stock < 0 THEN\n   \tError("Stock")\n   END\n  type : 14\n'
        blocks = module.extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['start_line'], 3)
        self.assertEqual(blocks[0]['end_line'], 5)
        self.assertEqual(blocks[0]['code'], 'IF stock < 0 THEN\n\tError("Stock")\nEND')

    def test_context_names_events_and_procedures(self):
        blocks = module.extract_blocks(NESTED)
        self.assertEqual([b['start_line'] for b in blocks], [4, 11, 16])
        self.assertEqual(blocks[0]['context'], {'names': [], 'siblings': {'name': 'WIN_Order', 'type': '65538'}})
        self.assertEqual(blocks[1]['context']['names'], ['WIN_Order', 'BTN_Save'])
        self.assertEqual(blocks[1]['context']['siblings'], {'type': '851977'})
        self.assertEqual(blocks[1]['procedures'], ['Fake'])
        self.assertEqual(blocks[2]['context']['siblings'], {'type': '851978'})
        self.assertEqual(module.literal_keys(NESTED), {'code': 3})

    def test_secret_hints_report_location_not_value(self):
        hints = module.secret_hints('w.wdw', module.extract_blocks(NESTED))
        self.assertEqual(hints, [{'path': 'w.wdw', 'line': 13, 'hint': 'credential-assignment'}])
        self.assertNotIn('hunter22', json.dumps(hints))

    def test_encodings_and_binary(self):
        for codec in ('utf-8-sig', 'utf-16'):
            self.assertEqual(module.decode_text('Reparação'.encode(codec)), 'Reparação')
        self.assertIsNone(module.decode_text(b'PCS\x00\x14\x00'))
        self.assertIsNone(module.decode_text(b'\x01binary'))
        self.assertIsNone(module.decode_text(b'\xffbinary'))
        self.assertEqual(module.decode_text('Réparation'.encode('cp1252'), 'cp1252'), 'Réparation')

    def test_schema_preserves_metadata_and_relationships(self):
        data = b'<ANALYSE><FICHIER Nom="Orders"><RUBRIQUE Nom="ID"><TYPE>24</TYPE><TYPE_CLE>1</TYPE_CLE></RUBRIQUE></FICHIER><LIAISON Nom="CustomerOrder"/></ANALYSE>'
        schema = module.raw_schema(data)
        self.assertEqual(schema['tables'][0]['attributes']['Nom'], 'Orders')
        self.assertIn('<TYPE>24</TYPE>', schema['tables'][0]['fields'][0]['raw_metadata'])
        self.assertIn('CustomerOrder', schema['raw_relationships'][0])
        with self.assertRaises(ValueError):
            module.raw_schema(b'<!DOCTYPE x [<!ENTITY x "text">]><ANALYSE/>')

    def test_inventory_skips_backups_data_symlinks_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'window.wdw').write_text('code : |1-\n DoSomething()\n', encoding='utf-8')
            (source / 'nested.wdw').write_text(NESTED, encoding='utf-8')
            (source / 'page.wwh').write_text('code : |1-\n Page()\n', encoding='utf-8')
            (source / 'query.WDR').write_bytes(b'PCS\x00binary')
            (source / 'orders.fic').write_bytes(b'PRIVATE DATA')
            (source / 'schema.xdd').write_text('<ANALYSE><FICHIER Nom="Orders"/></ANALYSE>')
            (source / 'Project.ana').mkdir()
            (source / 'Project.ana' / 'schema.xdd').write_text('<ANALYSE><FICHIER Nom="Orders"/></ANALYSE>')
            for folder in ('Backup', 'Bkp_20261022', 'project.cpl', 'Exe'):
                (source / folder).mkdir()
                (source / folder / 'copy.wdw').write_text('skip')
            try:
                (source / 'link.wdw').symlink_to(source / 'window.wdw')
            except OSError:
                pass  # Windows without symlink privilege: nothing to skip
            out = source / 'analysis-local'
            manifest = module.inspect(source, out, extra_extensions=['wwh'])
            self.assertEqual(len(manifest['files']), 6)
            duplicate = next(f for f in manifest['files'] if f['status'] == 'duplicate')
            self.assertEqual(duplicate['duplicate_of'], 'schema.xdd')
            statuses = {f['path']: f['status'] for f in manifest['files']}
            self.assertEqual(statuses['query.WDR'], 'binary-or-unsupported')
            self.assertEqual(statuses['schema.xdd'], 'schema')
            saved = json.loads((out / 'code/window.wdw.json').read_text())
            self.assertEqual(saved['blocks'][0]['code'], 'DoSomething()')
            self.assertEqual((source / 'orders.fic').read_bytes(), b'PRIVATE DATA')
            with (out / 'parity-seed.csv').open(encoding='utf-8') as handle:
                seeds = list(csv.DictReader(handle))
            kinds = sorted(r['kind'] for r in seeds)
            self.assertEqual(kinds, ['export-needed', 'table', 'window', 'window', 'window', 'window', 'wwh'])
            self.assertTrue(all(r['status'] == 'unmapped' for r in seeds))
            self.assertEqual(len({r['id'] for r in seeds}), len(seeds))
            again = module.inspect(source, root / 'again', extra_extensions=['wwh'])
            with (root / 'again' / 'parity-seed.csv').open(encoding='utf-8') as handle:
                self.assertEqual({r['id'] for r in csv.DictReader(handle)}, {r['id'] for r in seeds})
            self.assertEqual(again['secret_hints'], 1)
            with self.assertRaises(FileExistsError):
                module.inspect(source, out)

    def test_bad_schema_is_visible_and_source_output_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            (source / 'invalid.xdd').write_text('<broken')
            manifest = module.inspect(source, root / 'out')
            self.assertEqual(manifest['files'][0]['status'], 'unresolved-schema')
            with self.assertRaises(ValueError):
                module.inspect(source, source)
            with self.assertRaises(ValueError):
                module.inspect(source, root)


if __name__ == '__main__':
    unittest.main()
