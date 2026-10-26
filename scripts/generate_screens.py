#!/usr/bin/env python3
"""Generate a typed screen catalogue from visual layout JSON, without translating business rules.

The output directory belongs entirely to this generator. Regeneration requires its manifest and
unchanged generated files; handwritten or edited files are refused. Inputs are read only. Assets,
raw WINDEV sources, event code, credentials and data are never copied by this command.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re


MANIFEST = '.windev-generated.json'
VERSION = 1
KIND_ALIASES = {'Combo box': 'Combo Box', 'Check box': 'Check Box', 'Radio button': 'RadioButton'}
KINDS = {'Button', 'Edit control', 'Caption', 'Static', 'Combo Box', 'Check Box', 'Table',
         'Image', 'Group', 'Supercontrol', 'Shape', 'Calendar', 'List Box', 'List box', 'RadioButton'}
TOP_KEYS = {'format_version', 'window', 'controls', 'assets', 'unknown', 'image', 'source',
            'provenance', 'language', 'diagnostics'}
RAW_KEYS = {'code', 'blocks', 'encoded_slots', 'dialogs', 'records', 'rows', 'password',
            'credentials', 'connection_string', 'secret', 'token', 'raw', 'lines'}


def dumps(value):
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text_literal(value):
    # JSON escaping is also valid inside a TypeScript string. Escape JS line separators explicitly.
    return json.dumps(value, ensure_ascii=True)


def reject_raw(value, path='layout'):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in RAW_KEYS and not (key.lower() == 'password' and isinstance(child, bool)):
                raise ValueError(f'{path}.{key}: raw source, business data or credentials are not layout inputs')
            reject_raw(child, f'{path}.{key}')
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_raw(child, f'{path}[{index}]')


def localized(value, language, diagnostics, context):
    if not isinstance(value, dict):
        return value
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ValueError(f'{context}: expected text or a language-to-text object')
    if language and language in value:
        return value[language]
    if not value:
        diagnostics.append(f'{context}: no extracted text')
        return None
    selected = sorted(value)[0]
    diagnostics.append(f'{context}: language {language or "unspecified"} unavailable; preview uses {selected}')
    return value[selected]


def normalize(value, source, language=None):
    if not isinstance(value, dict) or not isinstance(value.get('window'), dict) or not isinstance(value.get('controls'), list):
        raise ValueError(f'{source}: expected screen_layout.py JSON with window and controls')
    extra = set(value) - TOP_KEYS
    if extra:
        raise ValueError(f'{source}: unsupported layout fields: {", ".join(sorted(extra))}')
    reject_raw(value)
    result = deepcopy(value)
    if result.get('format_version', VERSION) != VERSION:
        raise ValueError(f'{source}: unsupported layout format_version')
    window = result['window']
    if not isinstance(window.get('name'), str) or not window['name'].strip():
        raise ValueError(f'{source}: window.name must be nonempty text')
    if len(window['name']) > 512:
        raise ValueError(f'{source}: window.name is too long')
    window.setdefault('title', None)
    window.setdefault('background_image', None)
    window.setdefault('size', None)
    diagnostics = list(result.get('diagnostics', []))
    if not all(isinstance(item, str) for item in diagnostics):
        raise ValueError(f'{source}: diagnostics must contain text')
    unknown = result.setdefault('unknown', [])
    if not isinstance(unknown, list) or not all(isinstance(item, str) for item in unknown):
        raise ValueError(f'{source}: unknown must contain text')
    if 'title' in window:
        window['title'] = localized(window['title'], language, diagnostics, 'window.title')
    size = window.get('size')
    if size is not None and (not isinstance(size, dict) or any(
            not isinstance(size.get(key), (int, float)) or isinstance(size[key], bool)
            or not math.isfinite(size[key]) or size[key] <= 0 for key in ('width', 'height'))):
        raise ValueError(f'{source}: invalid window size')
    names, paths = {}, set()

    def control(item, parent=''):
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not item['name']:
            raise ValueError(f'{source}: each control/column needs a name')
        name = item['name']
        identity = item.get('path') or (f'{parent}.{name}' if parent else name)
        if not isinstance(identity, str) or not identity or identity in paths:
            raise ValueError(f'{source}: ambiguous or duplicate control path {identity!r}')
        paths.add(identity)
        names[name] = names.get(name, 0) + 1
        item['path'] = identity
        literal_kind = item.get('kind')
        if 'kind' in item and not isinstance(literal_kind, str):
            raise ValueError(f'{source}: {identity}.kind must be text')
        if literal_kind in KIND_ALIASES:
            item.setdefault('source_kind', literal_kind)
            item['kind'] = KIND_ALIASES[literal_kind]
        for key in ('x', 'y', 'width', 'height', 'caption_width'):
            number = item.get(key)
            if number is not None and (not isinstance(number, (int, float)) or isinstance(number, bool)
                                       or not math.isfinite(number)):
                raise ValueError(f'{source}: {identity}.{key} must be a finite number')
        if item.get('visible') is not None and not isinstance(item['visible'], bool):
            raise ValueError(f'{source}: {identity}.visible must be boolean or unknown')
        flags = item.get('flags')
        if flags is not None and (not isinstance(flags, dict) or any(
                not isinstance(flag, bool) for flag in flags.values())):
            raise ValueError(f'{source}: {identity}.flags must contain extracted booleans')
        for key in ('caption', 'title', 'input_mask'):
            if key in item:
                item[key] = localized(item[key], language, diagnostics, f'{identity}.{key}')
        if not parent and item.get('kind') not in KINDS:
            diagnostics.append(f'{identity}: unsupported or unknown kind {item.get("kind")!r}; provide a custom control')
        if not parent and any(item.get(key) is None for key in ('x', 'y', 'width', 'height')):
            diagnostics.append(f'{identity}: geometry incomplete; provide verified dimensions or a custom control')
        visibility = item.get('visible')
        if visibility is None and flags is not None:
            visibility = flags.get('Visible')
        if visibility is None:
            diagnostics.append(f'{identity}: visibility unknown; preview visibility is not legacy evidence')
        if item.get('metadata_unresolved'):
            diagnostics.append(f'{identity}: source metadata remains unresolved')
        columns = item.get('columns', [])
        if not isinstance(columns, list):
            raise ValueError(f'{source}: {identity}.columns must be an array')
        for column in columns:
            control(column, identity)

    for item in result['controls']:
        control(item)
    for name, count in sorted(names.items()):
        if count > 1:
            diagnostics.append(f'{name}: repeated legacy name; bind and select controls by qualified path')
    result['format_version'] = VERSION
    result['diagnostics'] = sorted(set(diagnostics))
    if language:
        result['language'] = language
    return result


def input_files(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Input symlinks are refused')
    if path.is_file():
        if path.suffix.lower() != '.json':
            raise ValueError('Input must be JSON')
        return [(path, path.name)]
    if not path.is_dir():
        raise ValueError(f'No input file or directory: {path}')
    entries = sorted(path.rglob('*'), key=lambda item: item.relative_to(path).as_posix())
    if any(item.is_symlink() for item in entries):
        raise ValueError('Input symlinks are refused')
    # A directory is an explicit collection of layouts, not an arbitrary evidence dump.
    files = [(item, item.relative_to(path).as_posix()) for item in entries
             if item.is_file() and item.suffix.lower() == '.json']
    if not files:
        raise ValueError(f'No JSON layouts found: {path}')
    return files


def prepare(input_path, language=None):
    output, records, entries, ids = {}, [], [], set()
    for index, (path, source) in enumerate(input_files(input_path)):
        data = path.read_bytes()
        try:
            raw = json.loads(data.decode('utf-8-sig'))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f'{source}: invalid UTF-8 JSON') from error
        layout = normalize(raw, source, language)
        identity = layout['window']['name']
        if identity in ids:
            raise ValueError(f'Duplicate window name: {identity!r}')
        ids.add(identity)
        stem = re.sub(r'[^a-zA-Z0-9_-]', '_', identity)[:48].strip('_') or 'screen'
        filename = f'layouts/{stem}-{sha(identity.encode("utf-8"))[:10]}.layout.json'
        output[filename] = dumps(layout).encode('utf-8')
        entries.append((identity, filename, source))
        records.append({'source': source, 'sha256': sha(data), 'id': identity,
                        'layout': filename, 'diagnostics': layout['diagnostics']})
    lines = ['// Generated by generate_screens.py; edit screen bindings outside this directory.',
             'import type { LegacyLayout } from "@windev-migration/ui";']
    for index, (_, filename, _) in enumerate(entries):
        lines.append(f'import layout{index} from {text_literal("./" + filename)};')
    lines += ['', 'export const screens: { id: string; layout: LegacyLayout; source: string }[] = [']
    for index, (identity, _, source) in enumerate(entries):
        lines.append(f'  {{ id: {text_literal(identity)}, layout: layout{index} as unknown as LegacyLayout, source: {text_literal(source)} }},')
    lines += ['];', '']
    output['screens.ts'] = '\n'.join(lines).encode('utf-8')
    manifest = {'format_version': VERSION, 'generator': 'generate_screens.py',
                'language': language, 'inputs': records,
                'outputs': {name: sha(content) for name, content in sorted(output.items())}}
    output[MANIFEST] = dumps(manifest).encode('utf-8')
    return output, manifest


def check_owned(output):
    if output.is_symlink():
        raise ValueError('Output symlinks are refused')
    if not output.exists():
        return
    if not output.is_dir() or not (output / MANIFEST).is_file():
        raise ValueError(f'Refusing existing output without generator ownership: {output}')
    entries = list(output.rglob('*'))
    if any(item.is_symlink() for item in entries):
        raise ValueError('Generated output contains a symlink')
    try:
        manifest = json.loads((output / MANIFEST).read_text(encoding='utf-8'))
        if manifest['generator'] != 'generate_screens.py' or manifest['format_version'] != VERSION:
            raise ValueError('Unknown generator manifest')
        expected = manifest['outputs']
        if not isinstance(expected, dict):
            raise ValueError('Invalid generated inventory')
        actual = {item.relative_to(output).as_posix() for item in entries if item.is_file()}
        if actual != set(expected) | {MANIFEST}:
            raise ValueError('Unexpected or missing files in generated output')
        for name, digest in expected.items():
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or sha((output / path).read_bytes()) != digest:
                raise ValueError(f'Generated file changed: {name}')
    except (KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        raise ValueError('Invalid generator ownership manifest') from error


def generate(input_path, output, language=None):
    output = Path(output)
    input_path = Path(input_path)
    files = input_files(input_path)
    if input_path.is_dir() and input_path.resolve() in output.resolve().parents:
        raise ValueError('Output must be outside the input layout collection')
    if any(output.resolve() == path.resolve() or output.resolve() in path.resolve().parents for path, _ in files):
        raise ValueError('Output must not contain input layouts')
    contents, manifest = prepare(input_path, language)
    check_owned(output)
    # Validate everything before the first write; never touch a maintained sibling file.
    previous = []
    if output.exists():
        previous = list(json.loads((output / MANIFEST).read_text(encoding='utf-8'))['outputs'])
    output.mkdir(parents=True, exist_ok=True)
    for name, data in contents.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for name in previous:
        if name not in contents:
            (output / name).unlink()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='one layout JSON or a directory containing only layout JSON')
    parser.add_argument('--output', required=True, type=Path, help='owned generated directory, e.g. PROJECT/src/generated')
    parser.add_argument('--language', help='explicit caption language; missing translations remain diagnostic')
    args = parser.parse_args()
    try:
        result = generate(args.input, args.output, args.language)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Generation failed: {error}\n')
    print(json.dumps({'screens': len(result['inputs']), 'output': str(args.output),
                      'diagnostics': sum(len(item['diagnostics']) for item in result['inputs'])}))


if __name__ == '__main__':
    main()
