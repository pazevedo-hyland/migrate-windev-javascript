#!/usr/bin/env python3
"""Bring named fields of existing layout files up to date with the current evidence, and nothing else.

A project keeps its window layouts (`layouts/<window>.layout.json`) as the screen generator's input, often
repaired by hand or by a project tool. When the evidence tools learn to read something new — fonts, a skin style,
the captions of columns that share a name — regenerating every layout would undo those repairs. This copies only
the fields you name, control by control (matched by `path`), from what `screen_layout.py` gives today:

  python3 scripts/refresh_layouts.py layouts --fields font style                 # controls
  python3 scripts/refresh_layouts.py layouts --column-fields caption input_type  # table columns
  ... --check     report what would change, write nothing
  ... --fill      only where the existing layout has no value (never replace one)

A control or column the current evidence does not have is left as it is and counted. Then run
generate_screens.py on the folder as usual.
"""
import argparse
import collections
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def tool(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_fields(target, source, fields, fill, counts, label):
    for field in fields:
        if field not in source or source[field] in (None, '', [], {}):
            continue
        if target.get(field) == source[field] or (fill and target.get(field) not in (None, '', [], {})):
            continue
        counts[f'{label}.{field} ' + ('added' if target.get(field) in (None, '', [], {}) else 'changed')] += 1
        target[field] = source[field]


def refresh(layout, fresh, fields=(), column_fields=(), fill=False):
    """Update `layout` in place from `fresh` (both screen_layout.py JSON). Returns a Counter of what changed."""
    counts = collections.Counter()
    current = {control.get('path') or control['name']: control for control in fresh.get('controls', [])}
    for control in layout.get('controls', []):
        source = current.get(control.get('path') or control['name'])
        if source is None:
            counts['controls not in the current evidence'] += 1
            continue
        copy_fields(control, source, fields, fill, counts, 'control')
        if column_fields and control.get('columns'):
            columns = {column.get('path') or column['name']: column for column in source.get('columns', [])}
            for column in control['columns']:
                match = columns.get(column.get('path') or column['name'])
                if match is None:
                    counts['columns not in the current evidence'] += 1
                    continue
                copy_fields(column, match, column_fields, fill, counts, 'column')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('layouts', type=Path, help='folder of <window>.layout.json files (or one file)')
    parser.add_argument('--latest', type=Path, default=Path('analysis-local/latest.json'), help='paths from prepare_evidence.py')
    parser.add_argument('--fields', nargs='*', default=[], help='control fields to copy (font, fonts, style, frames…)')
    parser.add_argument('--column-fields', nargs='*', default=[], help='table column fields to copy (caption, title, input_type…)')
    parser.add_argument('--fill', action='store_true', help='only set fields the layout does not have')
    parser.add_argument('--check', action='store_true', help='report only')
    parser.add_argument('--language', help='caption language, as for screen_layout.py')
    args = parser.parse_args()
    if not args.fields and not args.column_fields:
        raise SystemExit('name at least one field: --fields … or --column-fields …')
    layouter, latest = tool('screen_layout'), json.loads(args.latest.read_text(encoding='utf-8'))
    files = [args.layouts] if args.layouts.is_file() else sorted(args.layouts.glob('*.layout.json'))
    total, touched = collections.Counter(), 0
    for path in files:
        layout = json.loads(path.read_text(encoding='utf-8'))
        unit = layout.get('window', {}).get('name') or path.name.split('.')[0]
        try:
            fresh = layouter.layout(unit, latest, args.language)
        except (SystemExit, KeyError, ValueError, TypeError) as error:
            total['windows not in the current evidence'] += 1
            print(f'{unit}: skipped ({error})')
            continue
        counts = refresh(layout, fresh, args.fields, args.column_fields, args.fill)
        changed = sum(count for key, count in counts.items() if key.endswith(('added', 'changed')))
        total.update(counts)
        if changed and not args.check:
            path.write_text(json.dumps(layout, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        touched += bool(changed)
    print(f"{touched} of {len(files)} layouts {'would change' if args.check else 'changed'}")
    for key, count in sorted(total.items()):
        print(f'  {key}: {count}')


if __name__ == '__main__':
    main()
