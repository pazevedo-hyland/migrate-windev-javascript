import collections
import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/field_use.py')


class FieldUse(unittest.TestCase):
    def test_field_paths_skip_the_names_inside_a_map_of_names(self):
        counts = collections.Counter()
        module.keys_of({'kind': 'window', 'tables': {'Customers': {'read': ['a:1']}, 'Orders': {'read': [], 'write': ['a:2']}},
                        'font': [{'face': 'Arial'}, {'face': 'Tahoma', 'italic': True}]}, 'unit', counts, open_maps=('unit.tables',))
        self.assertEqual(dict(counts), {'unit.kind': 1, 'unit.tables': 1, 'unit.tables.*.read': 2, 'unit.tables.*.write': 1,
                                        'unit.font': 1, 'unit.font.face': 2, 'unit.font.italic': 1})

    def test_readers_are_found_by_name_and_the_writer_does_not_count(self):
        texts = {'scripts/schema_draft.py': "column['scale'] = 6", 'templates/tools/pg_schema.py': "if 'scale' in column:",
                 'templates/kit/layout.ts': 'const s = control.frames;', 'docs/notes.md': 'the `key_compares` text',
                 'scripts/other.py': 'upscale = rescale(1)'}
        self.assertEqual(module.readers('scale', texts, {'schema_draft.py'}), ['templates/tools/pg_schema.py'])
        self.assertEqual(module.readers('frames', texts, set()), ['templates/kit/layout.ts'])
        self.assertEqual(module.readers('key_compares', texts, set()), ['docs/notes.md'])
        self.assertEqual(module.readers('integer_digits', texts, set()), [])

    def test_audit_separates_code_from_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'schema-draft.json').write_text(json.dumps({'tables': [{
                'columns': [{'name': 'Total', 'scale': 6, 'caption_source': 'analysis file'}],
                'keys': [{'name': 'Code', 'key_compares': 'ignores case and accents'}]}]}), encoding='utf-8')
            latest = {'schema_draft': str(root / 'schema-draft.md')}
            texts = {'tools/pg_schema.py': "column['scale'] column['name'] key['name']", 'guide.md': '`key_compares` says how'}
            rows = {row['field']: row for row in module.audit(latest, texts)}
            text = module.markdown(list(rows.values()))
        self.assertEqual((rows['column.scale']['code_readers'], rows['column.caption_source']['code_readers'],
                          rows['key.key_compares']['code_readers'], rows['key.key_compares']['mentioned_in_docs']), (1, 0, 0, 1))
        self.assertIn('5 fields in 1 outputs; 2 with no reader in code, 1 of them not mentioned in any document either.', text)
        self.assertIn('| schema draft | `column.caption_source` | 1 | no |', text)
        self.assertIn('| schema draft | `column.scale` | 1 | pg_schema.py |', text)


if __name__ == '__main__':
    unittest.main()
