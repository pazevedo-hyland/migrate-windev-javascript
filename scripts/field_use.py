#!/usr/bin/env python3
"""Which extracted fields does anything read? A check of the toolkit against itself, at no cost.

Every extraction tool writes JSON for the next tool, a template or an agent. This lists each field name found in
those outputs — window layouts, the analysis, the schema draft, the code map, the evidence report — with how often
it occurs, and looks for the name in the code and documents that could consume it: the other scripts, the
templates (UI kit, starter, server tools, skills, prompts) and the guide's chapters. A field nothing mentions is
either waiting for a consumer or dead weight in every agent's context: both are worth knowing before a migration
pays for them.

The search is by name (`'field'`, `"field"`, `.field`, `` `field` ``): a field read through a generic loop counts as
unread, and a common word can count as read by accident. Read the result as a list of places to look.

  python3 scripts/field_use.py --out docs/field-use.md            (in a project, after prepare_evidence.py)
  python3 scripts/field_use.py --out docs/field-use.md --consumers src packages   (also search the application)
"""
import argparse
import collections
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
TEXT = {'.py', '.ts', '.tsx', '.mjs', '.js', '.md', '.json', '.css'}
# Output -> the scripts that write it (not counted as its readers).
WRITERS = {'layout': {'screen_layout.py', 'windev_decode.py', 'dossier_extract.py', 'inspect_windev.py', 'windev_fieldmap.py'},
           'analysis': {'windev_decode.py'}, 'schema draft': {'schema_draft.py'}, 'code map': {'code_map.py'},
           'evidence report': {'evidence_report.py'}}
OWN = {'field_use.py'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if path and Path(path).exists() else {}


def tool(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def keys_of(value, prefix, counts, depth=0, open_maps=()):
    """Count field names by where they sit (`control.font.face`). Keys of a map of names (`open_maps`: units,
    tables…) are data, not fields: their values are walked under one name."""
    if isinstance(value, dict):
        for key, child in value.items():
            if prefix in open_maps:
                keys_of(child, prefix + '.*', counts, depth + 1, open_maps)
                continue
            counts[f'{prefix}.{key}'] += 1
            keys_of(child, f'{prefix}.{key}', counts, depth + 1, open_maps)
    elif isinstance(value, list):
        for child in value:
            keys_of(child, prefix, counts, depth + 1, open_maps)


def produced(latest, layouter=None):
    """{output: Counter(field path)} from the outputs of the latest run."""
    result = collections.defaultdict(collections.Counter)
    inspect = Path(latest['inspect']) if latest.get('inspect') else None
    if layouter and inspect:
        for path in sorted((inspect / 'code').rglob('*.json')):
            source = load(path)
            if Path(source.get('path', '')).suffix.lower() != '.wdw' or not source.get('name'):
                continue
            try:
                layout = layouter.layout(source['name'], latest)
            except (SystemExit, KeyError, ValueError, TypeError):
                continue
            keys_of(layout.get('window', {}), 'window', result['layout'], open_maps=('window.flags',))
            for control in layout.get('controls', []):
                keys_of(control, 'control', result['layout'], open_maps=('control.flags', 'control.columns.flags'))
    if latest.get('decoded'):
        for table in load(Path(latest['decoded'], 'analysis.json')).get('tables', []):
            keys_of({k: v for k, v in table.items() if k != 'items'}, 'file', result['analysis'])
            keys_of(table.get('items', []), 'item', result['analysis'])
    draft = load(Path(latest['schema_draft']).with_suffix('.json')) if latest.get('schema_draft') else {}
    for table in draft.get('tables', []):
        keys_of(table.get('columns', []), 'column', result['schema draft'])
        keys_of(table.get('keys', []), 'key', result['schema draft'])
    code_map = load(Path(latest['code_map']).with_suffix('.json')) if latest.get('code_map') else {}
    for unit in code_map.get('units', {}).values():
        keys_of(unit, 'unit', result['code map'], open_maps=('unit.tables', 'unit.queries', 'unit.calls', 'unit.opens',
                                                             'unit.prints', 'unit.globals', 'unit.unknown_tables'))
    report = load(Path(latest['evidence_report']).with_suffix('.json')) if latest.get('evidence_report') else {}
    keys_of({k: v for k, v in report.items() if k not in ('callers', 'usage')}, 'report', result['evidence report'])
    return result


def consumer_texts(folders):
    """{relative path: text} of everything that could read a field."""
    texts = {}
    for folder in folders:
        folder = Path(folder)
        files = [folder] if folder.is_file() else [p for p in folder.rglob('*') if p.is_file()]
        for path in files:
            if path.suffix.lower() not in TEXT or any(part in ('node_modules', '.git', 'dist', 'target', 'generated', 'tests')
                                                      for part in path.parts) or path.stat().st_size > 2_000_000:
                continue
            try:
                texts[path.as_posix()] = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
    return texts


def readers(name, texts, writers):
    """Files that mention the field name as a key, a property or a quoted word; the output's own writers excluded."""
    pattern = re.compile(rf"""(?:['"`.]){re.escape(name)}(?:['"`]|\b)""")
    return sorted(path for path, text in texts.items()
                  if Path(path).name not in writers | OWN and pattern.search(text))


def audit(latest, texts, layouter=None):
    rows = []
    for output, counts in produced(latest, layouter).items():
        for path, count in sorted(counts.items()):
            found = readers(path.rsplit('.', 1)[-1], texts, WRITERS.get(output, set()))
            code = [f for f in found if not f.endswith('.md')]
            rows.append({'output': output, 'field': path, 'occurrences': count, 'read_by_code': code[:5],
                         'code_readers': len(code), 'mentioned_in_docs': len(found) - len(code)})
    return rows


def markdown(rows):
    unread = [row for row in rows if not row['code_readers']]
    lines = ['# Extracted fields and who reads them', '',
             'Generated by `scripts/field_use.py`. A field with no reader in code is either waiting for a consumer or '
             'costs context for nothing; one mentioned only in documents is read by people and agents, not by a tool. '
             'The search is by name: check before acting on a line.', '',
             f"{len(rows)} fields in {len({row['output'] for row in rows})} outputs; {len(unread)} with no reader in code, "
             f"{sum(not row['mentioned_in_docs'] for row in unread)} of them not mentioned in any document either.", '',
             '## No reader in code', '', '| Output | Field | Occurrences | Mentioned in documents |', '|---|---|---|---|']
    lines += [f"| {row['output']} | `{row['field']}` | {row['occurrences']} | {row['mentioned_in_docs'] or 'no'} |"
              for row in sorted(unread, key=lambda row: (row['output'], -row['occurrences']))]
    lines += ['', '## Read by code', '', '| Output | Field | Occurrences | Readers (first five) |', '|---|---|---|---|']
    lines += [f"| {row['output']} | `{row['field']}` | {row['occurrences']} | {', '.join(Path(f).name for f in row['read_by_code'])}"
              + (f" (+{row['code_readers'] - 5})" if row['code_readers'] > 5 else '') + ' |'
              for row in rows if row['code_readers']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--latest', type=Path, default=Path('analysis-local/latest.json'), help='paths from prepare_evidence.py')
    parser.add_argument('--consumers', type=Path, nargs='*', default=[],
                        help='more folders to search for readers (the application: src, packages, server)')
    parser.add_argument('--out', type=Path, required=True, help='Markdown report (a .json sibling is written)')
    args = parser.parse_args()
    folders = [HERE, *(p for p in (HERE.parent / 'templates', HERE.parent / 'docs', HERE.parent / 'skills') if p.exists()),
               *HERE.parent.glob('*.md'), *args.consumers]
    rows = audit(load(args.latest), consumer_texts(folders), tool('screen_layout'))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown(rows), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f"{len(rows)} fields, {sum(not row['code_readers'] for row in rows)} with no reader in code -> {args.out}")


if __name__ == '__main__':
    main()
