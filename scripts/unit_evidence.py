#!/usr/bin/env python3
"""Everything the evidence says about one unit, in one JSON: the mapper's starting point and the reviewer's diff.

Reads the paths in analysis-local/latest.json (prepare_evidence.py) and gathers, for one window or report:
its seed rows; its code blocks with event meanings; its encoded actions with every other slot in the project
holding the same action ID (with or without code: often what settles the action); the parsed dossier fields
(no raw lines); who opens or prints it and what it opens, prints or calls; and the gaps and runtime questions
that name it. Two packs of the same unit from two evidence versions compare with a plain `diff`.
"""
import argparse
import csv
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if path and Path(path).exists() else {}


def strip(value):
    """Parsed dossier fields only: drop raw text, keep the structure."""
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in ('raw', 'lines')}
    return value


def pack(unit, latest):
    inspect, dossier = Path(latest['inspect']), latest.get('dossier')
    report = load(Path(latest['evidence_report']).with_suffix('.json'))
    compiled = load(Path(latest['event_legend']).with_suffix('.json')) if latest.get('event_legend') else {}
    legend = compiled.get('codes', {})
    meaning = lambda code: legend.get(code or 'none', {}).get('event', 'unknown')
    sources = (load(p) for p in (inspect / 'code').rglob('*.json'))
    source = next((s for s in sources if s.get('name', '').lower() == unit.lower()), None)
    if source is None:
        raise SystemExit(f'{unit}: not in {inspect}')
    with (inspect / 'parity-seed.csv').open(encoding='utf-8') as handle:
        seed = [{k: r[k] for k in ('id', 'kind', 'context', 'event', 'evidence')}
                for r in csv.DictReader(handle) if r['element'].lower() == unit.lower()]
    blocks = [{'control': '/'.join(b['context']['names']), 'event': b['context']['siblings'].get('type'),
               'meaning': meaning(b['context']['siblings'].get('type')), 'lines': f"{b['start_line']}-{b['end_line']}",
               'procedures': b['procedures'], 'encoded_properties': b.get('encoded_properties', False)}
              for b in source['blocks']]
    groups = {g['action']: g['slots'] for g in report.get('encoded_actions', [])}
    proposals = {g['action']: g.get('proposal') for g in report.get('encoded_actions', [])}
    actions = []
    for slot in source.get('encoded_slots', []):
        others = [s for s in groups.get(slot['action'], [])
                  if not (s['element'].lower() == unit.lower() and s['control'] == slot['names'][-1])]
        actions.append({'control': '/'.join(slot['names']), 'event': slot['event'], 'meaning': meaning(slot['event']),
                        'line': slot['line'], 'has_code': slot['has_code'], 'action': slot['action'],
                        'proposed': proposals.get(slot['action']), 'same_action_elsewhere': others})
    element = {}
    for kind in ('windev-window', 'report'):
        path = Path(dossier or '.', kind, f'{unit}.json')
        if dossier and path.exists():
            element = strip(load(path))
    callers = next((v for k, v in report.get('callers', {}).items() if k.lower() == unit.lower()), [])
    calls = {f: [s for s in sites if s[0].lower() == unit.lower()] for f, sites in report.get('usage', {}).items()}
    mentions = lambda items: [i for i in items if unit.lower() in i.lower()]
    return {'unit': unit, 'source': source['path'], 'seed_rows': seed, 'blocks': blocks, 'encoded_actions': actions,
            'dossier': element, 'opened_or_printed_by': callers,
            'calls': {f: [{'line': s[1], 'argument': s[2]} for s in sites] for f, sites in calls.items() if sites},
            'embedded_query_items': next((v for k, v in compiled.get('report_queries', {}).items()
                                          if k.lower() == unit.lower()), None),
            'gaps': mentions(report.get('gaps', [])), 'runtime_questions': [q for q in report.get('questions', [])
                                                                           if unit.lower() in q['question'].lower()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('unit', help='window or report name, e.g. WIN_Table_Clientes')
    parser.add_argument('--latest', type=Path, default=Path('analysis-local/latest.json'), help='paths from prepare_evidence.py')
    parser.add_argument('--out', type=Path, help='write here instead of stdout (e.g. analysis-local/units/<unit>.json)')
    args = parser.parse_args()
    text = json.dumps(pack(args.unit, load(args.latest)), indent=1, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + '\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
