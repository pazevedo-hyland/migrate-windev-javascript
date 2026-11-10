#!/usr/bin/env python3
"""Turn the decoder's audit into decisions: every unexplained difference of a unit gets an answer before the unit is done.

`windev_decode.py` lists, per control, the bytes that differ from the usual value of its kind and that no property
explains (`audit.json`). This keeps one row per such control in `docs/evidence/audit-decisions.csv`:

  unit,control,differences,decision
  WIN_Order,BTN_Save,"128:01/05 1005:01/05","image has 1 state instead of 5: reproduced (screen spec §3)"

  python3 scripts/audit_decisions.py --init                 # add a row for every control not listed yet
  python3 scripts/audit_decisions.py --unit WIN_Order        # what is still undecided for one unit
  python3 scripts/audit_decisions.py --require-complete [--unit WIN_Order]   # exit 1 while a row has no decision

A decision says what the difference is and what was done ("explained: …", "reproduced: …", "no visible effect:
checked on the thumbnail", "open: U-12"). A row whose differences changed since it was decided (the sources or the
field map changed) is reported as stale and counts as undecided. Rows are never removed or rewritten by the tool.
"""
import argparse
import csv
import json
from pathlib import Path

COLUMNS = ['unit', 'control', 'differences', 'decision']


def findings(audit_path):
    """{(unit, control): 'position:value/usual …'} for designer chunks (identifiers and link chunks are left out)."""
    found = {}
    for element in json.loads(Path(audit_path).read_text(encoding='utf-8'))['elements']:
        if not element['name'] or not element['variant'].endswith(('/0.14', '/15.14')):
            continue
        text = ' '.join(f"{d['position']}:{d['value']}/{d['usual']}" for d in element['differences'])
        key = element['unit'], element['name']
        found[key] = f'{found[key]} | {text}' if key in found else text
    return found


def read_rows(path):
    if not Path(path).exists():
        return []
    with Path(path).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def status(found, rows, unit=None):
    """(undecided, stale, decided) lists of (unit, control) for the audit's current findings."""
    by_key = {(row['unit'], row['control']): row for row in rows}
    undecided, stale, decided = [], [], []
    for key, differences in sorted(found.items()):
        if unit and key[0].lower() != unit.lower():
            continue
        row = by_key.get(key)
        if not row or not row['decision'].strip():
            undecided.append(key)
        elif row['differences'] != differences:
            stale.append(key)
        else:
            decided.append(key)
    return undecided, stale, decided


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--latest', type=Path, default=Path('analysis-local/latest.json'))
    parser.add_argument('--audit', type=Path, help='default: <decoded>/audit.json from latest.json')
    parser.add_argument('--decisions', type=Path, default=Path('docs/evidence/audit-decisions.csv'))
    parser.add_argument('--unit')
    parser.add_argument('--init', action='store_true', help='append a row without decision for each unlisted control')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    audit = args.audit or Path(json.loads(args.latest.read_text(encoding='utf-8'))['decoded'], 'audit.json')
    found, rows = findings(audit), read_rows(args.decisions)
    if args.init:
        listed = {(row['unit'], row['control']) for row in rows}
        added = [{'unit': unit, 'control': control, 'differences': differences, 'decision': ''}
                 for (unit, control), differences in sorted(found.items())
                 if (unit, control) not in listed and (not args.unit or unit.lower() == args.unit.lower())]
        args.decisions.parent.mkdir(parents=True, exist_ok=True)
        with args.decisions.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows + added)
        rows += added
    undecided, stale, decided = status(found, rows, args.unit)
    print(json.dumps({'controls_with_differences': len(undecided) + len(stale) + len(decided), 'decided': len(decided),
                      'undecided': len(undecided), 'stale': len(stale)}))
    for label, keys in (('undecided', undecided), ('stale', stale)):
        for unit, control in keys[:200] if args.unit else []:
            print(f'{label}: {unit}/{control}: {found[unit, control]}')
    if args.require_complete and (undecided or stale):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
