#!/usr/bin/env python3
"""Rebuild the aggregate parity matrix from per-unit parity CSVs, so parallel workers never write the same file.

Each worker writes only its unit's file (`docs/parity/<UNIT>.csv`, same columns as `parity.csv`). This merges every
CSV of the folder except the seed and the aggregate itself:

- a row in a unit file replaces the aggregate row with the same id (the unit files are the source of truth);
- an aggregate row no unit file holds is kept as it is (rows that only ever lived in `parity.csv`);
- an id present in two unit files, a unit file without an `id` column, or a column the aggregate does not have is
  an error, and nothing is written;
- `--exclude <element>=<decision>` (repeatable) re-applies an accepted exclusion (status `excluded`, decision set) to
  every row of that element after the merge, so a unit file regenerated from older notes cannot revive it;
- order: seed order first, then the other ids sorted, so the diff of a merge stays small.

Columns: the aggregate's header, else the seed's. Values are copied as they are; validation stays with
`parity_check.py` (run it after merging). `--check` writes nothing and exits 1 when the aggregate would change.
"""
import argparse
import csv
import io
from pathlib import Path
import sys


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def merge(directory, out=None, seed=None, exclusions=None):
    """Return (text, rows, errors) of the merged aggregate. Nothing is written here."""
    directory = Path(directory)
    out = Path(out) if out else directory / 'parity.csv'
    seed = Path(seed) if seed else directory / 'parity-seed.csv'
    errors = []
    old_columns, old_rows = read_csv(out) if out.exists() else ([], [])
    seed_columns, seed_rows = read_csv(seed) if seed.exists() else ([], [])
    columns = old_columns or seed_columns
    if not columns:
        return None, {}, [f'no column header: neither {out} nor {seed} exists']
    if 'id' not in columns:
        return None, {}, [f'{out if old_columns else seed}: no id column']
    skip = {out.resolve(), seed.resolve()}
    rows, origin = {}, {}
    for path in sorted(directory.glob('*.csv'), key=lambda p: p.name.lower()):
        if path.resolve() in skip:
            continue
        header, unit_rows = read_csv(path)
        if 'id' not in header:
            errors.append(f'{path.name}: no id column')
            continue
        extra = [column for column in header if column not in columns]
        if extra:
            errors.append(f'{path.name}: columns not in the aggregate: {", ".join(extra)}')
            continue
        for number, row in enumerate(unit_rows, start=2):
            identifier = (row.get('id') or '').strip()
            if not identifier:
                errors.append(f'{path.name}:{number}: empty id')
            elif identifier in rows:
                errors.append(f'{path.name}:{number}: id {identifier} already in {origin[identifier]}')
            else:
                rows[identifier] = {column: row.get(column) or '' for column in columns}
                origin[identifier] = path.name
    for row in old_rows:
        identifier = (row.get('id') or '').strip()
        if identifier and identifier not in rows:
            rows[identifier] = {column: row.get(column) or '' for column in columns}
    for element, decision in (exclusions or {}).items():
        hits = [row for row in rows.values() if (row.get('element') or '').strip() == element]
        if not hits:
            errors.append(f'--exclude {element}: no row has this element')
        for row in hits:
            row['status'], row['decision'] = 'excluded', decision
    if errors:
        return None, rows, errors
    seeded = [r['id'].strip() for r in seed_rows if (r.get('id') or '').strip() in rows]
    order = list(dict.fromkeys(seeded)) + sorted(set(rows) - set(seeded))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    for identifier in order:
        writer.writerow(rows[identifier])
    return buffer.getvalue(), rows, []


def exclusion(value):
    element, separator, decision = value.partition('=')
    if not separator or not element.strip() or not decision.strip():
        raise argparse.ArgumentTypeError('expected <element>=<decision>, e.g. WIN_Old=docs/decisions/002-scope.md')
    return element.strip(), decision.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory', type=Path, nargs='?', default=Path('docs/parity'), help='default: docs/parity')
    parser.add_argument('--out', type=Path, help='aggregate matrix (default: <directory>/parity.csv)')
    parser.add_argument('--seed', type=Path, help='seed whose order comes first (default: <directory>/parity-seed.csv)')
    parser.add_argument('--exclude', type=exclusion, action='append', default=[], metavar='ELEMENT=DECISION',
                        help='re-apply an accepted exclusion to every row of an element (repeatable)')
    parser.add_argument('--check', action='store_true', help='write nothing; exit 1 if the aggregate would change')
    args = parser.parse_args()
    out = args.out or args.directory / 'parity.csv'
    try:
        text, rows, errors = merge(args.directory, out, args.seed, dict(args.exclude))
    except OSError as error:
        parser.exit(1, f'Parity merge failed: {error}\n')
    for error in errors:
        print(f'ERROR {error}', file=sys.stderr)
    if errors:
        raise SystemExit(1)
    data = text.encode('utf-8')
    changed = not out.exists() or out.read_bytes() != data
    if not args.check and changed:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    state = ('would change' if args.check else 'written') if changed else 'unchanged'
    print(f'{len(rows)} rows; {out} {state}')
    raise SystemExit(1 if args.check and changed else 0)


if __name__ == '__main__':
    main()
