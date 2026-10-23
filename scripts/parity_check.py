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
# assumed: built on a proposed answer (answer sheet) or a default decision; a test may verify it, and the progress
# page counts it apart until a person confirms it.
CONFIDENCE = {'verified', 'inferred', 'assumed', 'unresolved'}
DONE = {'verified', 'excluded'}
# One evidence item: a source location, a dossier or analysis reference, or a file (screenshot, export, golden).
# A JSON file may name the field: "dossier/windev-window/WIN_X.json (controls.BTN_Ok.flags)".
EVIDENCE = re.compile(r'\S+:\d+(?:-\d+)?|(?:dossier|analysis|export|golden|runtime|proposed): ?\S.*|[^\s;]+\.[A-Za-z0-9]{2,5}(?: \(.+\))?')


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def unit_of(row, units):
    """The legacy unit a row belongs to: its element, or for a rule row titled freely, the first part of its context."""
    element = (row.get('element') or '').strip()
    if element.lower() in units:
        return units[element.lower()]
    first = (row.get('context') or '').split('/')[0].split('.')[0].strip()
    return units.get(first.lower(), element)


def check(matrix, seed=None, require_complete=False, element=None, check_files=False):
    """Return (errors, summary). Errors make the gate fail. element: one unit or several, comma-separated."""
    header, rows = read_csv(matrix)
    errors = [f'missing column: {c}' for c in REQUIRED if c not in header]
    if errors:
        return errors, {}
    _, seed_rows = read_csv(seed) if seed else ([], [])
    units = {r['element'].lower(): r['element'] for r in seed_rows if r.get('element')}
    wanted = {e.strip().lower() for e in element.split(',')} if element else None
    ids = {}
    for number, row in enumerate(rows, start=2):
        ids.setdefault((row.get('id') or '').strip(), number)
        if wanted and unit_of(row, units).lower() not in wanted:
            continue  # checks are scoped to the units asked for
        where = f'line {number} ({row["id"] or "no id"})'
        value = {k: (row.get(k) or '').strip() for k in REQUIRED}
        if not value['id']:
            errors.append(f'{where}: empty id')
        elif ids[value['id']] != number:
            errors.append(f'{where}: duplicate id, first at line {ids[value["id"]]}')
        if value['status'] not in STATUSES:
            errors.append(f'{where}: status must be one of {", ".join(STATUSES)}')
        if value['confidence'] not in CONFIDENCE:
            errors.append(f'{where}: confidence must be verified, inferred, assumed or unresolved')
        if 'proposed:' in value['evidence'] and value['confidence'] == 'verified':
            errors.append(f'{where}: a row citing a proposed answer is "assumed", not "verified", until it is answered')
        if not value['evidence']:
            errors.append(f'{where}: evidence is required (path:line, export or screenshot)')
        for item in filter(None, (i.strip() for i in value['evidence'].split(';'))):
            if check_files and EVIDENCE.fullmatch(item) and not re.match(r'(?:dossier|analysis|export|golden|runtime|proposed):', item):
                path = re.split(r':\d|\s\(', item)[0]
                if not Path(path).exists() and not Path('legacy', path).exists():  # seed evidence is legacy-relative
                    errors.append(f'{where}: evidence file not found: {path}')
            if 'analysis-local/' in item:
                errors.append(f'{where}: evidence "{item[:80]}" points into analysis-local/ (dated, not committed): cite '
                              '"dossier: <unit>/<field>", the legacy/ source line, or docs/evidence/images/<file>')
                continue
            if not EVIDENCE.fullmatch(item):
                errors.append(f'{where}: evidence "{item}" is not path:line, dossier: <unit>/<control>, '
                              'analysis: <file>.<item>, export:/golden:/runtime:/proposed: <ref> or a file')
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
        scoped = [r for r in seed_rows if not wanted or r.get('element', '').lower() in wanted]
        seeded = {r['id'] for r in seed_rows}
        same = {}
        for r in seed_rows:
            same.setdefault((r['element'].lower(), r.get('context', ''), r.get('event', '')), []).append(r['id'])
        renamed = {}
        # A SRC- row the current seed no longer has: the evidence changed, or the tools now name the same block
        # differently. One seed row with the same element, context and event is the new name for it.
        for row in rows:
            if row['id'].startswith('SRC-') and row['id'] not in seeded and (
                    not wanted or unit_of(row, units).lower() in wanted):
                match = [i for i in same.get(((row.get('element') or '').lower(), row.get('context', ''),
                                              row.get('event', '')), []) if i not in ids]
                if len(match) == 1:
                    renamed[match[0]] = row['id']
                    errors.append(f'matrix row {row["id"]} is now seed row {match[0]} (same element, context and '
                                  'event): rename it')
                else:
                    errors.append(f'matrix row not in the current seed (stale evidence): {row["id"]} — re-check it '
                                  'against the new inspector output, then delete it or turn it into a RULE- row')
        # Seed rows may be refined or excluded, never silently dropped.
        errors.extend(f'seed row missing from matrix: {r["id"]}' for r in scoped
                      if r['id'] not in ids and r['id'] not in renamed)
    if wanted:  # the summary describes the units asked for, not the whole matrix
        rows = [r for r in rows if unit_of(r, units).lower() in wanted]
    counts = {s: sum(1 for r in rows if (r.get('status') or '').strip() == s) for s in STATUSES}
    total = len(rows)
    done = counts['verified'] + counts['excluded']
    summary = {'rows': total, 'statuses': counts,
               'verified_on_assumptions': sum(1 for r in rows if (r.get('status') or '').strip() == 'verified'
                                              and (r.get('confidence') or '').strip() == 'assumed'),
               'complete_percent': round(100 * done / total, 1) if total else 0.0}
    return errors, summary


VAGUE = re.compile(r'not extracted|not proven|unknown|read from the image|untested|\bprobably\b|to be checked|\bto check\b', re.I)


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
    parser.add_argument('--element', help='Only check these legacy units, comma-separated (e.g. a slice\'s windows)')
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
        problems = lint_note(note)
        errors.extend(problems)
        print(f'note {note}: {len(problems)} open points without a U- id')
    print(json.dumps(summary, indent=2))
    for error in errors:
        print(f'ERROR {error}')
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
