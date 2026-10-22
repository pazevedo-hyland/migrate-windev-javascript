#!/usr/bin/env python3
"""Compare legacy and target CSV exports table by table (golden master / reconciliation)."""
import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import unicodedata


def normalize(value, rules):
    """Apply only declared normalizations: an undeclared difference stays a difference."""
    value = '' if value is None else value
    if rules.get('trim', True):
        value = value.strip()
    if rules.get('empty_as_null') and value == '':
        return None
    if rules.get('decimal') and value != '':
        try:
            number = Decimal(value.replace(' ', '').replace(',', '.'))
        except InvalidOperation:
            return value
        places = rules.get('decimal_places')
        return str(number.quantize(Decimal(1).scaleb(-places)) if places is not None else number.normalize())
    for pattern in rules.get('date_formats', []):
        try:
            return datetime.strptime(value, pattern).isoformat()
        except ValueError:
            continue
    if rules.get('casefold'):
        value = value.casefold()
    if rules.get('strip_accents'):
        value = ''.join(c for c in unicodedata.normalize('NFD', value) if unicodedata.category(c) != 'Mn')
    return value


def load(path, side):
    with Path(path).open(newline='', encoding=side.get('encoding', 'utf-8-sig')) as handle:
        return list(csv.DictReader(handle, delimiter=side.get('delimiter', ',')))


def compare_table(name, spec, legacy_dir, target_dir, defaults, limit):
    legacy_side = {**defaults.get('legacy', {}), **spec.get('legacy', {})}
    target_side = {**defaults.get('target', {}), **spec.get('target', {})}
    legacy = load(Path(legacy_dir) / spec.get('legacy_file', f'{name}.csv'), legacy_side)
    target = load(Path(target_dir) / spec.get('target_file', f'{name}.csv'), target_side)
    rename = spec.get('rename', {})  # legacy column -> target column; keys use target names
    ignore = set(spec.get('ignore', []))
    columns = spec.get('columns', {})
    keys = spec['key']

    def keyed(rows, translate, label):
        result, duplicates = {}, []
        for row in rows:
            cells = {(rename.get(c, c) if translate else c): v for c, v in row.items() if c not in ignore}
            key = tuple(normalize(cells.get(k), columns.get(k, {})) for k in keys)
            if key in result:
                duplicates.append(list(key))
            result[key] = cells
        return result, [f'{label} duplicate key {d}' for d in duplicates]

    legacy_rows, problems = keyed(legacy, True, 'legacy')
    target_rows, more = keyed(target, False, 'target')
    problems += more
    missing = [list(k) for k in legacy_rows if k not in target_rows]
    extra = [list(k) for k in target_rows if k not in legacy_rows]
    mismatches = []
    for key in legacy_rows.keys() & target_rows.keys():
        before, after = legacy_rows[key], target_rows[key]
        for column in sorted(set(before) - ignore):
            if column not in after:
                problems.append(f'target lacks column {column}')
                continue
            rules = columns.get(column, {})
            if normalize(before[column], rules) != normalize(after[column], rules):
                mismatches.append({'key': list(key), 'column': column,
                                   'legacy': before[column], 'target': after[column]})
    problems = sorted(set(problems))
    mismatches.sort(key=lambda m: (str(m['key']), m['column']))
    return {'legacy_rows': len(legacy), 'target_rows': len(target),
            'missing_in_target': len(missing), 'extra_in_target': len(extra),
            'mismatched_cells': len(mismatches), 'problems': problems,
            'samples': {'missing': sorted(missing, key=str)[:limit], 'extra': sorted(extra, key=str)[:limit],
                        'mismatches': mismatches[:limit]},
            'equal': not (missing or extra or mismatches or problems)}


def compare(config, legacy_dir, target_dir, limit=20):
    defaults = {k: config.get(k, {}) for k in ('legacy', 'target')}
    tables = {name: compare_table(name, spec, legacy_dir, target_dir, defaults, limit)
              for name, spec in config['tables'].items()}
    return {'equal': all(t['equal'] for t in tables.values()), 'tables': tables}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path, help='JSON table/key/normalization spec')
    parser.add_argument('--legacy', required=True, type=Path, help='Directory of legacy CSV exports')
    parser.add_argument('--target', required=True, type=Path, help='Directory of target CSV exports')
    parser.add_argument('--report', type=Path, help='Write the JSON report here')
    parser.add_argument('--limit', type=int, default=20, help='Sample size per difference type')
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        report = compare(config, args.legacy, args.target, args.limit)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f'Comparison failed: {error}\n')
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report:
        args.report.write_text(text, encoding='utf-8')
    print(text if not args.report else json.dumps(
        {name: {k: v for k, v in t.items() if k != 'samples'} for name, t in report['tables'].items()}, indent=2))
    raise SystemExit(0 if report['equal'] else 1)


if __name__ == '__main__':
    main()
