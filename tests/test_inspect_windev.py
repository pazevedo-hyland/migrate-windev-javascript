import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('inspect_windev', Path(__file__).parents[1] / 'scripts/inspect_windev.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InspectionTests(unittest.TestCase):
    def test_literal_blocks_keep_lines_and_stop_at_sibling(self):
        text = 'name : Save\n  code : |1-\n   IF stock < 0 THEN\n   \tError("Stock")\n   END\n  type : 14\n'
        blocks = module.extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['start_line'], 3)
        self.assertEqual(blocks[0]['end_line'], 5)
        self.assertEqual(blocks[0]['code'], 'IF stock < 0 THEN\n\tError("Stock")\nEND')

    def test_encodings_and_binary(self):
        for codec in ('utf-8-sig', 'utf-16'):
            self.assertEqual(module.decode_text('Reparação'.encode(codec)), 'Reparação')
        self.assertIsNone(module.decode_text(b'PCS\x00\x14\x00'))
        self.assertIsNone(module.decode_text(b'\x01binary'))
        self.assertIsNone(module.decode_text(b'\xffbinary'))

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
            (source / 'query.WDR').write_bytes(b'PCS\x00binary')
            (source / 'orders.fic').write_bytes(b'PRIVATE DATA')
            (source / 'schema.xdd').write_text('<ANALYSE><FICHIER Nom="Orders"/></ANALYSE>')
            for folder in ('Backup', 'Bkp_20261022', 'project.cpl', 'Exe'):
                (source / folder).mkdir()
                (source / folder / 'copy.wdw').write_text('skip')
            (source / 'link.wdw').symlink_to(source / 'window.wdw')
            out = source / 'analysis-local'
            manifest = module.inspect(source, out)
            self.assertEqual(len(manifest['files']), 3)
            statuses = {f['path']: f['status'] for f in manifest['files']}
            self.assertEqual(statuses['query.WDR'], 'binary-or-unsupported')
            self.assertEqual(statuses['schema.xdd'], 'schema')
            saved = json.loads((out / 'code/window.wdw.json').read_text())
            self.assertEqual(saved['blocks'][0]['code'], 'DoSomething()')
            self.assertEqual((source / 'orders.fic').read_bytes(), b'PRIVATE DATA')
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
