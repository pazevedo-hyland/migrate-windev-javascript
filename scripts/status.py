#!/usr/bin/env python3
"""Report migration progress from the parity matrix and roadmap; export untracked work items."""
import argparse
import csv
import json
from pathlib import Path
import re

STATUSES = ['unmapped', 'specified', 'implemented', 'verified', 'excluded']
DONE = {'verified', 'excluded'}
MAX_LISTED = 100


def read_parity(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        return [{k: (v or '').strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def read_roadmap(path):
    """Parse the first Markdown table that has a Status column."""
    rows, header = [], None
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.lstrip().startswith('|'):
            if header and rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if header is None:
            if 'Status' in cells:
                header = cells
            continue
        if all(re.fullmatch(r':?-+:?', c) for c in cells):
            continue
        row = dict(zip(header, cells))
        if row.get('Status'):
            rows.append(row)
    return rows


def percent(done, total):
    return round(100 * done / total, 1) if total else 0.0


def summarize(rows, roadmap=None):
    groups = {}
    for row in rows:
        groups.setdefault((row.get('kind', ''), row.get('element', '')), []).append(row)
    elements = []
    for (kind, element), items in sorted(groups.items()):
        counts = {s: sum(1 for r in items if r.get('status') == s) for s in STATUSES}
        done = counts['verified'] + counts['excluded']
        elements.append({'kind': kind, 'element': element, 'rows': len(items), **counts,
                         'complete_percent': percent(done, len(items)),
                         'tickets': sorted({r['ticket'] for r in items if r.get('ticket')})})
    totals = {s: sum(1 for r in rows if r.get('status') == s) for s in STATUSES}
    summary = {'rows': len(rows), 'statuses': totals,
               'complete_percent': percent(totals['verified'] + totals['excluded'], len(rows)),
               'unresolved_legacy_behavior': sum(1 for r in rows if r.get('confidence') == 'unresolved'),
               'elements': elements}
    if roadmap is not None:
        status_counts = {}
        for slice_ in roadmap:
            status_counts[slice_['Status']] = status_counts.get(slice_['Status'], 0) + 1
        summary['roadmap'] = {
            'slices': len(roadmap), 'statuses': status_counts,
            'open': [{'number': s.get('#', ''), 'slice': s.get('Slice', ''), 'status': s['Status']}
                     for s in roadmap if s['Status'] in ('In progress', 'Blocked')]}
    return summary


def markdown(summary):
    s = summary['statuses']
    lines = ['# Migration status', '',
             f"**Parity: {summary['complete_percent']}% complete** — {summary['rows']} rows: "
             + ', '.join(f'{k} {v}' for k, v in s.items())
             + f". Legacy behavior still unresolved: {summary['unresolved_legacy_behavior']}.", '']
    if 'roadmap' in summary:
        road = summary['roadmap']
        lines += [f"**Roadmap**: {road['slices']} slices — "
                  + ', '.join(f'{k} {v}' for k, v in road['statuses'].items()) + '.', '']
        lines += [f"- #{o['number']} {o['slice']} — **{o['status']}**" for o in road['open']]
        lines += [''] if road['open'] else []
    lines += ['| Kind | Element | Rows | Unmapped | Specified | Implemented | Verified | Excluded | Done % | Tickets |',
              '|---|---|---|---|---|---|---|---|---|---|']
    for e in sorted(summary['elements'], key=lambda e: (e['complete_percent'], e['kind'], e['element'])):
        lines.append(f"| {e['kind']} | {e['element']} | {e['rows']} | {e['unmapped']} | {e['specified']} | "
                     f"{e['implemented']} | {e['verified']} | {e['excluded']} | {e['complete_percent']} | "
                     f"{' '.join(e['tickets'])} |")
    return '\n'.join(lines) + '\n'


def work_items(rows, label):
    """One story per legacy element whose open rows have no ticket yet."""
    groups = {}
    for row in rows:
        if row.get('status') not in DONE and not row.get('ticket'):
            groups.setdefault((row.get('kind', ''), row.get('element', '')), []).append(row)
    items = []
    for (kind, element), open_rows in sorted(groups.items()):
        listed = open_rows[:MAX_LISTED]
        description = [f'Migrate legacy {kind} {element} to parity. Done when every row below is verified '
                       f'(executed test) or excluded (ADR), and npm run verify passes.', '', 'Parity rows:']
        description += [f"- {r['id']} [{r.get('status')}] {r.get('context') or ''} {r.get('event') or ''} "
                        f"— {r.get('evidence', '')}".replace('  ', ' ') for r in listed]
        if len(open_rows) > MAX_LISTED:
            description.append(f'- … and {len(open_rows) - MAX_LISTED} more in docs/parity/parity.csv')
        items.append({'Summary': f'Migrate {kind} {element} ({len(open_rows)} parity rows)',
                      'Issue Type': 'Story', 'Description': '\n'.join(description),
                      'Labels': [label, re.sub(r'\W+', '-', kind) or 'unknown'],
                      'Parity IDs': ' '.join(r['id'] for r in open_rows)})
    return items


def write_work_items(items, path):
    with Path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        # Jira's CSV importer maps repeated "Labels" columns to several labels.
        writer.writerow(['Summary', 'Issue Type', 'Description', 'Labels', 'Labels', 'Parity IDs'])
        for item in items:
            writer.writerow([item['Summary'], item['Issue Type'], item['Description'],
                             *item['Labels'], item['Parity IDs']])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parity', type=Path, default=Path('docs/parity/parity.csv'))
    parser.add_argument('--roadmap', type=Path, help='ROADMAP.md with a Status column')
    parser.add_argument('--json', action='store_true', help='print JSON instead of Markdown')
    parser.add_argument('--work-items', type=Path, help='write a tracker-importable CSV of untracked work')
    parser.add_argument('--label', default='windev-migration', help='label added to exported work items')
    args = parser.parse_args()
    try:
        rows = read_parity(args.parity)
        summary = summarize(rows, read_roadmap(args.roadmap) if args.roadmap else None)
        if args.work_items:
            items = work_items(rows, args.label)
            write_work_items(items, args.work_items)
            summary['work_items_written'] = len(items)
    except OSError as error:
        parser.exit(1, f'Status failed: {error}\n')
    print(json.dumps(summary, indent=2) if args.json else markdown(summary), end='' if not args.json else '\n')


if __name__ == '__main__':
    main()
