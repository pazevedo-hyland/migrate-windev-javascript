#!/usr/bin/env python3
"""Validate a behavior-parity matrix (CSV) and gate on complete, evidenced coverage."""
import argparse
import csv
import json
from pathlib import Path
import re

REQUIRED = ['id', 'kind', 'element', 'evidence', 'confidence', 'target_behavior',
            'implemented_in', 'test', 'decision', 'status']
STATUSES = ['unmapped', 'specified', 'implemented', 'verified', 'excluded']
CONFIDENCE = {'verified', 'inferred', 'unresolved'}
DONE = {'verified', 'excluded'}
# One evidence item: a source location, a dossier or analysis reference, or a file (screenshot, export, golden).
# A JSON file may name the field: "dossier/windev-window/WIN_X.json (controls.BTN_Ok.flags)".
EVIDENCE = re.compile(r'\S+:\d+(?:-\d+)?|(?:dossier|analysis|export|golden|runtime): ?\S.*|.*\S\.[A-Za-z0-9]{2,5}(?: \(.+\))?')


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def check(matrix, seed=None, require_complete=False, element=None):
    """Return (errors, summary). Errors make the gate fail."""
    header, rows = read_csv(matrix)
    errors = [f'missing column: {c}' for c in REQUIRED if c not in header]
    if errors:
        return errors, {}
    ids = {}
    for number, row in enumerate(rows, start=2):
        where = f'line {number} ({row["id"] or "no id"})'
        value = {k: (row.get(k) or '').strip() for k in REQUIRED}
        if not value['id']:
            errors.append(f'{where}: empty id')
        elif value['id'] in ids:
            errors.append(f'{where}: duplicate id, first at line {ids[value["id"]]}')
        ids.setdefault(value['id'], number)
        if value['status'] not in STATUSES:
            errors.append(f'{where}: status must be one of {", ".join(STATUSES)}')
        if value['confidence'] not in CONFIDENCE:
            errors.append(f'{where}: confidence must be verified, inferred or unresolved')
        if not value['evidence']:
            errors.append(f'{where}: evidence is required (path:line, export or screenshot)')
        for item in filter(None, (i.strip() for i in value['evidence'].split(';'))):
            if not EVIDENCE.fullmatch(item):
                errors.append(f'{where}: evidence "{item}" is not path:line, dossier: <unit>/<control>, '
                              'analysis: <file>.<item>, export:/golden:/runtime: <ref> or a file')
        legacy = (row.get('legacy_behavior') or '').strip()
        if value['status'] == 'unmapped' and legacy and not re.search(r'\bU-(?:[A-Z0-9]+-)?\d+', legacy):
            errors.append(f'{where}: an unmapped row with described behavior must cite the unresolved item (U-nn) blocking it')
        if value['status'] in ('specified', 'implemented', 'verified') and not value['target_behavior']:
            errors.append(f'{where}: {value["status"]} rows need target_behavior')
        if value['status'] in ('implemented', 'verified') and not value['implemented_in']:
            errors.append(f'{where}: {value["status"]} rows need implemented_in')
        if value['status'] == 'verified':
            if not value['test']:
                errors.append(f'{where}: verified rows need the executed test reference')
            if value['confidence'] == 'unresolved':
                errors.append(f'{where}: a verified row cannot keep unresolved legacy behavior')
        if value['status'] == 'excluded' and not value['decision']:
            errors.append(f'{where}: excluded rows need a decision (ADR) reference')
        if require_complete and value['status'] not in DONE:
            errors.append(f'{where}: not complete ({value["status"]})')
    if seed:
        _, seed_rows = read_csv(seed)
        if element:
            seed_rows = [r for r in seed_rows if r.get('element') == element]
        missing = [r['id'] for r in seed_rows if r['id'] not in ids]
        # Seed rows may be refined or excluded, never silently dropped.
        errors.extend(f'seed row missing from matrix: {i}' for i in missing)
    counts = {s: sum(1 for r in rows if (r.get('status') or '').strip() == s) for s in STATUSES}
    total = len(rows)
    done = counts['verified'] + counts['excluded']
    summary = {'rows': total, 'statuses': counts,
               'complete_percent': round(100 * done / total, 1) if total else 0.0}
    return errors, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('matrix', type=Path, help='docs/parity/parity.csv')
    parser.add_argument('--seed', type=Path, help='parity-seed.csv produced by inspect_windev.py')
    parser.add_argument('--element', help='Only require the seed rows of this legacy element (per-unit files)')
    parser.add_argument('--require-complete', action='store_true',
                        help='Fail unless every row is verified or excluded')
    args = parser.parse_args()
    try:
        errors, summary = check(args.matrix, args.seed, args.require_complete, args.element)
    except OSError as error:
        parser.exit(1, f'Parity check failed: {error}\n')
    print(json.dumps(summary, indent=2))
    for error in errors:
        print(f'ERROR {error}')
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
