#!/usr/bin/env python3
"""Create a new isolated React/Tauri migration starter. Existing destinations are always refused.

Only templates/starter is copied. The command never inspects or copies a legacy project, application
records or credentials, installs dependencies, initializes Git or connects to an external service.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / 'templates/starter'
TEMPLATE_MANIFEST = 'template-manifest.json'
FORBIDDEN_ROOTS = {'legacy'}
FORBIDDEN_PARTS = {'analysis-local', '.git', '.env'}
SKIP_PARTS = {'node_modules', 'target', 'dist', 'test-results', 'playwright-report', 'coverage',
              '.vite', '.vitest', '__pycache__', '.pytest_cache', '.DS_Store'}
PLACEHOLDERS = {'__APP_NAME__', '__APP_TITLE__', '__APP_IDENTIFIER__'}


def generator():
    spec = importlib.util.spec_from_file_location('starter_generate_screens', HERE / 'generate_screens.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create(output, name, layouts=None, language=None, template=None):
    output, template = Path(output), Path(template or TEMPLATE)
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', name) or len(name) > 64:
        raise ValueError('name must be a lowercase app slug beginning with a letter (maximum 64 characters)')
    if output.exists() or output.is_symlink():
        raise ValueError(f'Refusing existing destination: {output}')
    if output.resolve() == template.resolve() or template.resolve() in output.resolve().parents:
        raise ValueError('Destination must be outside the starter template')
    if not template.is_dir() or template.is_symlink():
        raise ValueError(f'No starter template: {template}')
    paths = []
    for current, directories, filenames in os.walk(template, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in SKIP_PARTS)
        for name_in_template in [*directories, *filenames]:
            path = Path(current, name_in_template)
            if name_in_template in SKIP_PARTS or path.suffix.lower() == '.pdf':
                continue
            paths.append(path)
    paths.sort()
    for path in paths:
        relative = path.relative_to(template)
        if (path.is_symlink() or relative.parts[0] in FORBIDDEN_ROOTS
                or any(part in FORBIDDEN_PARTS or part.startswith('.env.') for part in relative.parts)):
            raise ValueError(f'Unsafe starter template entry: {relative}')
    manifest_path = template / TEMPLATE_MANIFEST
    if not manifest_path.is_file():
        raise ValueError('Starter template must declare template-manifest.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 1 or not isinstance(manifest.get('files'), list):
        raise ValueError('Unsupported starter template manifest')
    replacement_files = set()
    replacements = {'__APP_NAME__': name, '__APP_TITLE__': name,
                    '__APP_IDENTIFIER__': 'com.migration.' + name.replace('-', '')}
    rendered = {}
    for name_in_template in manifest['files']:
        if not isinstance(name_in_template, str):
            raise ValueError('Template replacement paths must be text')
        relative = Path(name_in_template)
        if relative.is_absolute() or '..' in relative.parts or not (template / relative).is_file():
            raise ValueError(f'Invalid template replacement path: {name_in_template}')
        replacement_files.add(relative.as_posix())
    for path in paths:
        if not path.is_file() or path == manifest_path:
            continue
        relative = path.relative_to(template).as_posix()
        data = path.read_bytes()
        if relative in replacement_files:
            text = data.decode('utf-8')
            for token, value in replacements.items():
                text = text.replace(token, value)
            if re.search(r'__APP_[A-Z_]+__', text):
                raise ValueError(f'Unknown app placeholder in {relative}')
            data = text.encode('utf-8')
        elif any(token.encode('ascii') in data for token in PLACEHOLDERS):
            raise ValueError(f'Undeclared placeholder replacement in {relative}')
        rendered[relative] = data
    prepared = generator().prepare(layouts, language)[0] if layouts is not None else None
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f'.{output.name}-', dir=output.parent))
    try:
        for relative, data in rendered.items():
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if prepared is not None:
            target_root = temporary / 'src/generated'
            # Starter-owned placeholder files are replaced only in the fresh temporary project.
            if target_root.exists():
                shutil.rmtree(target_root)
            for relative, data in prepared.items():
                target = target_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        metadata = {'format_version': 1, 'generator': 'create_project.py', 'name': name,
                    'identifier': replacements['__APP_IDENTIFIER__'], 'layouts_generated': prepared is not None}
        (temporary / '.windev-starter.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        if output.exists() or output.is_symlink():
            raise ValueError(f'Destination appeared during generation: {output}')
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--name', required=True, help='lowercase app slug, e.g. parts-desk')
    parser.add_argument('--layouts', type=Path, help='optional visual layout JSON file/directory')
    parser.add_argument('--language', help='explicit layout caption language')
    args = parser.parse_args()
    try:
        result = create(args.output, args.name, args.layouts, args.language)
    except (OSError, ValueError, UnicodeError) as error:
        parser.exit(1, f'Project creation failed: {error}\n')
    print(json.dumps({'output': str(args.output), **result}))


if __name__ == '__main__':
    main()
