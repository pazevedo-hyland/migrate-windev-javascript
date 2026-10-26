import json
from pathlib import Path
import tempfile
import unittest

from helpers import load
from test_generate_screens import sample

bootstrap = load('scripts/create_project.py')


def template(root):
    root.mkdir()
    (root / 'src/generated').mkdir(parents=True)
    (root / 'src/generated/screens.ts').write_text('starter sample')
    (root / 'package.json').write_text('{"name":"__APP_NAME__"}')
    (root / 'package-lock.json').write_text('{"name":"__APP_NAME__","packages":{"":{"name":"__APP_NAME__"}}}')
    (root / 'config.json').write_text('{"identifier":"__APP_IDENTIFIER__", "title":"__APP_TITLE__"}')
    (root / 'README.md').write_text('Synthetic starter')
    (root / 'template-manifest.json').write_text(json.dumps({'schemaVersion': 1, 'files': ['package.json', 'package-lock.json', 'config.json']}))
    return root


class CreateProjectTests(unittest.TestCase):
    def test_nested_secrets_and_private_caches_are_refused(self):
        for name in ('.env', '.env.local', '.git', 'analysis-local'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = template(root / 'template')
                private = source / 'packages/reports' / name
                private.parent.mkdir(parents=True)
                if name.startswith('.env'):
                    private.write_text('synthetic-private-value')
                else:
                    private.mkdir()
                with self.assertRaisesRegex(ValueError, 'Unsafe starter'):
                    bootstrap.create(root / 'absent', 'safe-app', template=source)
                self.assertFalse((root / 'absent').exists())

    def test_real_starter_bootstrap_retains_only_portable_sources_and_replaces_all_names(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'real-consumer'
            bootstrap.create(target, 'real-consumer')
            self.assertTrue((target / 'packages/ui/src/ui/legacy/wd.tsx').is_file())
            self.assertTrue((target / 'packages/reports/src/renderer.ts').is_file())
            self.assertFalse((target / 'node_modules').exists())
            self.assertFalse((target / 'dist').exists())
            self.assertNotIn('__APP_', (target / 'src/App.tsx').read_text())
            self.assertEqual(json.loads((target / 'package-lock.json').read_text())['name'], 'real-consumer')
            self.assertIn('name = "real-consumer"', (target / 'src-tauri/Cargo.lock').read_text())

    def test_two_apps_replace_declared_files_only_without_mutating_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = template(root / 'template')
            for name in ('parts-desk', 'library-catalogue'):
                target = root / name
                result = bootstrap.create(target, name, template=source)
                self.assertEqual(json.loads((target / 'package.json').read_text())['name'], name)
                self.assertEqual(json.loads((target / 'package-lock.json').read_text())['packages']['']['name'], name)
                self.assertEqual(result['identifier'], 'com.migration.' + name.replace('-', ''))
                self.assertFalse((target / 'template-manifest.json').exists())
                self.assertFalse((target / '.git').exists())
                self.assertFalse(result['layouts_generated'])
                self.assertEqual((target / 'src/generated/screens.ts').read_text(), 'starter sample')
            self.assertIn('__APP_NAME__', (source / 'package.json').read_text())

    def test_optional_generation_replaces_only_new_starter_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = template(root / 'template')
            layout = root / 'screen.json'
            layout.write_text(json.dumps(sample()))
            target = root / 'new-app'
            result = bootstrap.create(target, 'new-app', layout, 'fr', source)
            self.assertTrue(result['layouts_generated'])
            self.assertIn('WIN_Contacts', (target / 'src/generated/screens.ts').read_text())
            self.assertEqual((target / 'README.md').read_text(), 'Synthetic starter')
            self.assertEqual((source / 'src/generated/screens.ts').read_text(), 'starter sample')
            self.assertTrue((target / 'src/generated/.windev-generated.json').is_file())

    def test_existing_destination_and_bad_names_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = template(root / 'template')
            target = root / 'existing'
            target.mkdir()
            (target / 'keep.txt').write_text('keep')
            with self.assertRaisesRegex(ValueError, 'existing'):
                bootstrap.create(target, 'valid', template=source)
            for name in ('../oops', 'Uppercase', 'app";$(id)', 'a/b', '1app', 'a' * 65, 'two--hyphens'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'slug'):
                    bootstrap.create(root / 'absent', name, template=source)
            self.assertEqual((target / 'keep.txt').read_text(), 'keep')
            self.assertFalse((root / 'absent').exists())

    def test_invalid_layout_leaves_no_partial_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = template(root / 'template')
            invalid = root / 'bad.json'
            invalid.write_text('{"blocks":["raw code"]}')
            with self.assertRaises(ValueError):
                bootstrap.create(root / 'absent', 'valid', invalid, template=source)
            self.assertFalse((root / 'absent').exists())
            self.assertEqual(sorted(path.name for path in root.iterdir()), ['bad.json', 'template'])

    def test_template_symlinks_private_folders_and_unknown_placeholders_are_refused(self):
        for kind in ('symlink', 'private', 'unknown', 'undeclared', 'manifest-path'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = template(root / 'template')
                if kind == 'symlink':
                    (source / 'link').symlink_to(source / 'README.md')
                elif kind == 'private':
                    (source / 'legacy').mkdir()
                elif kind == 'unknown':
                    (source / 'package.json').write_text('__APP_SECRET__')
                elif kind == 'undeclared':
                    (source / 'README.md').write_text('__APP_NAME__')
                else:
                    (source / 'template-manifest.json').write_text('{"schemaVersion":1,"files":["../outside"]}')
                with self.assertRaises(ValueError):
                    bootstrap.create(root / 'absent', 'valid', template=source)
                self.assertFalse((root / 'absent').exists())

    def test_validation_artifacts_are_ignored_without_following_their_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = template(root / 'template')
            for folder in ('node_modules', 'dist', 'test-results', 'playwright-report', 'src-tauri/target',
                           'packages/ui/node_modules', 'coverage'):
                artifact = source / folder
                artifact.mkdir(parents=True)
                (artifact / 'generated.pdf').write_bytes(b'%PDF synthetic validation output')
                (artifact / 'link').symlink_to(root / 'absent')
            (source / 'scratch.pdf').write_bytes(b'%PDF synthetic validation output')
            (source / '.DS_Store').write_bytes(b'temporary finder metadata')
            target = root / 'app'
            bootstrap.create(target, 'clean-starter', template=source)
            copied = {path.relative_to(target).as_posix() for path in target.rglob('*') if path.is_file()}
            self.assertFalse(any('node_modules' in path or 'target/' in path for path in copied))
            self.assertFalse(any(path.endswith('.pdf') or path.endswith('.DS_Store') for path in copied))
            self.assertEqual((target / 'README.md').read_text(), 'Synthetic starter')

    def test_private_root_rule_preserves_nested_legacy_ui_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = template(root / 'template')
            component = source / 'packages/ui/src/ui/legacy/control.ts'
            component.parent.mkdir(parents=True)
            component.write_text('export const syntheticControl = true;')
            target = root / 'app'
            bootstrap.create(target, 'valid', template=source)
            self.assertEqual((target / 'packages/ui/src/ui/legacy/control.ts').read_text(), component.read_text())
            (source / 'legacy').mkdir()
            with self.assertRaisesRegex(ValueError, 'Unsafe starter'):
                bootstrap.create(root / 'another', 'valid', template=source)
            self.assertFalse((root / 'another').exists())


if __name__ == '__main__':
    unittest.main()
