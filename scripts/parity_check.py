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
EVIDENCE = re.compile(r'\S+:\d+(?:-\d+)?|(?:dossier|analysis|export|golden|runtime): ?\S.*|[^\s;]+\.[A-Za-z0-9]{2,5}(?: \(.+\))?')


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def check(matrix, seed=None, require_complete=False, element=None, check_files=False):
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
            if check_files and EVIDENCE.fullmatch(item) and not re.match(r'(?:dossier|analysis|export|golden|runtime):', item):
                path = re.split(r':\d|\s\(', item)[0]
                if not Path(path).exists():
                    errors.append(f'{where}: evidence file not found: {path}')
            if 'analysis-local/' in item:
                errors.append(f'{where}: evidence "{item[:80]}" points into analysis-local/ (dated, not committed): cite '
                              '"dossier: <unit>/<field>", the legacy/ source line, or docs/evidence/images/<file>')
                continue
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
        # A SRC- row the current seed no longer has describes evidence that changed: re-check it against the
        # new inspector output, then delete it or turn it into a RULE- row.
        seeded = {r['id'] for r in seed_rows}
        stale = [i for i, row in ((r['id'], r) for r in rows)
                 if i.startswith('SRC-') and i not in seeded and (not element or row.get('element') == element)]
        errors.extend(f'matrix row not in the current seed (stale evidence): {i}' for i in stale)
    counts = {s: sum(1 for r in rows if (r.get('status') or '').strip() == s) for s in STATUSES}
    total = len(rows)
    done = counts['verified'] + counts['excluded']
    summary = {'rows': total, 'statuses': counts,
               'complete_percent': round(100 * done / total, 1) if total else 0.0}
    return errors, summary


VAGUE = re.compile(r'not extracted|not proven|unknown|read from the image|untested|\bprobably\b|\bcheck\b', re.I)


def lint_note(path):
    """Open points written as prose instead of U- items: each such line must carry a U-<UNIT>-nn id."""
    problems = []
    for number, line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), start=1):
        if VAGUE.search(line) and not re.search(r'\bU-(?:[A-Z0-9]+-)?\d+', line):
            problems.append(f'{Path(path).name}:{number}: open point without a U- id: {line.strip()[:100]}')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('matrix', type=Path, help='docs/parity/parity.csv')
    parser.add_argument('--seed', type=Path, help='parity-seed.csv produced by inspect_windev.py')
    parser.add_argument('--element', help='Only require the seed rows of this legacy element (per-unit files)')
    parser.add_argument('--note', type=Path, action='append', default=[],
                        help='Mapping note or spec to lint for open points without a U- id (repeatable)')
    parser.add_argument('--check-files', action='store_true',
                        help='Fail when a cited evidence file does not exist (paths relative to the current folder)')
    parser.add_argument('--require-complete', action='store_true',
                        help='Fail unless every row is verified or excluded')
    args = parser.parse_args()
    try:
        errors, summary = check(args.matrix, args.seed, args.require_complete, args.element, args.check_files)
    except OSError as error:
        parser.exit(1, f'Parity check failed: {error}\n')
    for note in args.note:
        errors.extend(lint_note(note))
    print(json.dumps(summary, indent=2))
    for error in errors:
        print(f'ERROR {error}')
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
