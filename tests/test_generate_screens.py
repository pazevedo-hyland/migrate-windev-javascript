import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from helpers import load, ROOT

generator = load('scripts/generate_screens.py')


def sample(name='WIN_Contacts'):
    return {'window': {'name': name, 'title': {'en': 'Contacts', 'fr': 'Contacts français'},
                       'size': {'width': 600, 'height': 400}},
            'controls': [
                {'name': 'EDT_Name', 'path': 'GROUP.EDT_Name', 'kind': 'Edit control', 'x': 10, 'y': 20,
                 'caption': {'en': 'Name', 'fr': 'Nom'}, 'flags': {'Required input': True, 'Visible': False},
                 'visible': False, 'input_type': 'Text', 'input_size': 80},
                {'name': 'TABLE_A', 'kind': 'Table', 'x': 10, 'y': 50, 'columns': [
                    {'name': 'COL_Code', 'title': 'Code A', 'width': 80}]},
                {'name': 'TABLE_B', 'kind': 'Table', 'x': 10, 'y': 150, 'columns': [
                    {'name': 'COL_Code', 'title': 'Code B', 'width': 120}]},
                {'name': 'Odd', 'kind': 'Unknown custom control', 'x': 1, 'y': 2, 'metadata_unresolved': True}],
            'assets': [], 'unknown': ['U-EXAMPLE-1: no event behavior recovered'],
            'source': 'code/contacts.wdw'}


def write_layout(root, data=None, name='one.layout.json'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data or sample(), ensure_ascii=False), encoding='utf-8')
    return path


def inventory(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


class GenerateScreensTests(unittest.TestCase):
    def test_two_apps_qualified_columns_flags_and_language_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_layout(root / 'first')
            other = write_layout(root / 'second', sample('WIN_Library'))
            before = source.read_bytes()
            first = generator.generate(source, root / 'app-one/src/generated', 'en')
            second = generator.generate(other, root / 'app-two/src/generated', 'fr')
            layout = json.loads((root / 'app-one/src/generated' / first['inputs'][0]['layout']).read_text())
            translated = json.loads((root / 'app-two/src/generated' / second['inputs'][0]['layout']).read_text())
            self.assertEqual(layout['window']['title'], 'Contacts')
            self.assertEqual(translated['controls'][0]['caption'], 'Nom')
            self.assertEqual(layout['controls'][0]['path'], 'GROUP.EDT_Name')
            self.assertEqual(layout['controls'][0]['flags'], {'Required input': True, 'Visible': False})
            self.assertFalse(layout['controls'][0]['visible'])
            self.assertEqual(layout['controls'][1]['columns'][0]['path'], 'TABLE_A.COL_Code')
            self.assertEqual(layout['controls'][2]['columns'][0]['path'], 'TABLE_B.COL_Code')
            self.assertEqual(layout['source'], 'code/contacts.wdw')
            self.assertEqual(source.read_bytes(), before)
            self.assertIn('Unknown custom control', '\n'.join(layout['diagnostics']))
            self.assertIn('visibility unknown', '\n'.join(layout['diagnostics']))
            self.assertEqual(layout['unknown'], ['U-EXAMPLE-1: no event behavior recovered'])
            screen_ts = (root / 'app-one/src/generated/screens.ts').read_text()
            self.assertIn('import type { LegacyLayout } from "@windev-migration/ui";', screen_ts)
            self.assertIn('export const screens:', screen_ts)
            self.assertNotIn(str(root), screen_ts)

    def test_deterministic_regeneration_and_maintained_siblings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_layout(root / 'inputs')
            output = root / 'app/src/generated'
            generator.generate(source.parent, output, 'en')
            original = inventory(output)
            handwritten = output.parent / 'bindings.ts'
            handwritten.write_text('export const myBinding = 7;')
            generator.generate(source.parent, output, 'en')
            self.assertEqual(inventory(output), original)
            self.assertEqual(handwritten.read_text(), 'export const myBinding = 7;')
            (output / 'manual.ts').write_text('do not overwrite')
            with self.assertRaisesRegex(ValueError, 'Unexpected'):
                generator.generate(source, output)
            self.assertEqual((output / 'manual.ts').read_text(), 'do not overwrite')

    def test_refuses_handwritten_or_modified_generated_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_layout(root / 'inputs')
            output = root / 'generated'
            output.mkdir()
            with self.assertRaisesRegex(ValueError, 'ownership'):
                generator.generate(source, output)
            output.rmdir()
            generator.generate(source, output)
            (output / 'screens.ts').write_text('handwritten change')
            with self.assertRaisesRegex(ValueError, 'changed'):
                generator.generate(source, output)
            self.assertEqual((output / 'screens.ts').read_text(), 'handwritten change')

    def test_hostile_strings_stay_json_data_and_never_become_paths_or_markup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hostile = '../../CON/<script>"; process.exit(9); //\u2028'
            data = sample(hostile)
            data['controls'][0]['caption'] = '<img src=x onerror="alert(1)">\n${process.env.HOME}'
            source = write_layout(root / 'input', data)
            output = root / 'generated'
            manifest = generator.generate(source, output)
            self.assertEqual(json.loads((output / manifest['inputs'][0]['layout']).read_text())['window']['name'], hostile)
            self.assertTrue((output / manifest['inputs'][0]['layout']).is_relative_to(output))
            self.assertNotIn('<img', (output / 'screens.ts').read_text())
            self.assertIn('\\u2028', (output / 'screens.ts').read_text())
            self.assertEqual(len(list((output / 'layouts').glob('*.json'))), 1)

    def test_missing_language_is_diagnostic_and_password_flag_is_not_credentials(self):
        data = sample()
        data['controls'][0]['flags']['Password'] = True
        result = generator.normalize(data, 'one.json', 'de')
        self.assertTrue(result['controls'][0]['flags']['Password'])
        self.assertIn('language de unavailable', '\n'.join(result['diagnostics']))

    def test_rejects_raw_evidence_invalid_numbers_and_duplicate_identities(self):
        cases = []
        data = sample(); data['code'] = 'DO NOT COPY'; cases.append(data)
        data = sample(); data['controls'][0]['password'] = 'do-not-copy'; cases.append(data)
        data = sample(); data['format_version'] = 99; cases.append(data)
        data = sample(); data['controls'][0]['x'] = float('nan'); cases.append(data)
        data = sample(); data['controls'].append(dict(data['controls'][0])); cases.append(data)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                generator.normalize(data, 'bad.json')

    def test_duplicate_window_names_and_symlinks_are_refused_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_layout(root / 'inputs')
            write_layout(source.parent, name='two.json')
            output = root / 'generated'
            with self.assertRaisesRegex(ValueError, 'Duplicate window'):
                generator.generate(source.parent, output)
            self.assertFalse(output.exists())
            (source.parent / 'two.json').unlink()
            (root / 'link.json').symlink_to(source)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                generator.generate(root / 'link.json', output)
            with self.assertRaisesRegex(ValueError, 'contain input'):
                generator.generate(source, source.parent)
            with self.assertRaisesRegex(ValueError, 'outside the input'):
                generator.generate(source.parent, source.parent / 'generated')

    def test_window_nulls_radio_kind_and_incomplete_geometry_remain_explicit(self):
        result = generator.normalize({'window': {'name': 'WIN_Unknown'}, 'controls': [
            {'name': 'RAD_Choice', 'kind': 'RadioButton'}]}, 'minimal.json')
        self.assertIsNone(result['window']['title'])
        self.assertIsNone(result['window']['background_image'])
        self.assertIsNone(result['window']['size'])
        self.assertNotIn('unsupported', '\n'.join(result['diagnostics']))
        self.assertIn('geometry incomplete', '\n'.join(result['diagnostics']))

    def test_exact_dossier_kind_aliases_roundtrip_to_runtime_without_losing_literals(self):
        aliases = {'Combo box': 'Combo Box', 'Check box': 'Check Box', 'Radio button': 'RadioButton'}
        data = {'window': {'name': 'WIN_Dossier'}, 'controls': [
            {'name': f'CONTROL_{index}', 'kind': kind, 'x': 10, 'y': index * 30,
             'width': 200, 'height': 24, 'flags': {'Visible': True}}
            for index, kind in enumerate([*aliases, 'Unknown special widget'])]}
        result = generator.normalize(data, 'dossier.json')
        for control, (literal, canonical) in zip(result['controls'], aliases.items()):
            self.assertEqual(control['kind'], canonical)
            self.assertEqual(control['source_kind'], literal)
            self.assertNotIn(f'{control["path"]}: unsupported', '\n'.join(result['diagnostics']))
        self.assertEqual(result['controls'][-1]['kind'], 'Unknown special widget')
        self.assertNotIn('source_kind', result['controls'][-1])
        self.assertIn('Unknown special widget', '\n'.join(result['diagnostics']))
        self.assertEqual(generator.normalize(result, 'dossier.json'), result)
        self.assertEqual(data['controls'][0]['kind'], 'Combo box')

    def test_visibility_diagnostics_respect_literal_control_and_column_flags(self):
        result = generator.normalize({'window': {'name': 'WIN_Visibility'}, 'controls': [
            {'name': 'TABLE_Visible', 'kind': 'Table', 'x': 0, 'y': 0, 'width': 100, 'height': 100,
             'flags': {'Visible': True}, 'columns': [
                 {'name': 'COL_Shown', 'flags': {'Visible': True}},
                 {'name': 'COL_Hidden', 'flags': {'Visible': False}},
                 {'name': 'COL_Unknown'}]},
            {'name': 'BTN_Hidden', 'kind': 'Button', 'x': 0, 'y': 100, 'width': 80, 'height': 24,
             'visible': False, 'flags': {'Visible': True}}]}, 'visibility.json')
        visibility = [message for message in result['diagnostics'] if 'visibility unknown' in message]
        self.assertEqual(len(visibility), 1)
        self.assertTrue(visibility[0].startswith('TABLE_Visible.COL_Unknown:'))
        self.assertNotIn('visible', result['controls'][0])
        self.assertFalse(result['controls'][1]['visible'])

    def test_nontext_control_kind_is_a_validation_error(self):
        for kind in ([], {}, None, 5, False):
            data = sample()
            data['controls'][0]['kind'] = kind
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'kind must be text'):
                generator.normalize(data, 'malformed.json')

    def test_cli_creates_real_manifest_and_returns_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_layout(root / 'inputs')
            command = [sys.executable, str(ROOT / 'scripts/generate_screens.py'), '--input', str(source),
                       '--output', str(root / 'generated'), '--language', 'en']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['screens'], 1)
            (root / 'generated/screens.ts').write_text('edited')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Generation failed', result.stderr)


if __name__ == '__main__':
    unittest.main()
