#!/usr/bin/env python3
"""What an agent would still have to guess, unit by unit, before anyone spends a token on building.

Reads the paths in analysis-local/latest.json (prepare_evidence.py) and, for every window, report, class and set
of procedures, counts what the evidence leaves open:

  controls without a position, or of a kind the screen generator does not draw;
  a layout the screen generator refuses (it is run in memory on every window: nothing is written);
  event slots with neither code nor a predefined action that names its element;
  an embedded query whose SQL was not read;
  table and window names the code builds at run time; tables the analysis does not have;
  the gaps and runtime questions of evidence_report.py that name the unit.

Each open point is listed with what would close it. Units are ranked by open points and sized by their seed rows
and code lines: the plan of slices starts from the units with none. `--briefs <dir>` also writes one short
Markdown brief per unit — what it is, who opens it, what it touches, its events and its open points — for an
agent to read first instead of the whole evidence pack (unit_evidence.py), which it opens only where the brief
points.

  python3 scripts/readiness_report.py --out docs/readiness.md [--briefs docs/briefs]
"""
import argparse
import collections
import csv
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
GENERIC_UNKNOWN = ('fonts, font sizes and colors',)


def tool(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if path and Path(path).exists() else {}


def sibling_json(latest, key):
    return load(Path(latest[key]).with_suffix('.json')) if latest.get(key) else {}


def decoded_units(latest):
    """{unit lower: {'sql': embedded query SQL or None, 'actions': {control lower: target}}} from the decoder."""
    result = collections.defaultdict(lambda: {'sql': None, 'actions': {}})
    decoded = Path(latest['decoded']) if latest.get('decoded') else None
    for path in (decoded / 'properties').rglob('*.json') if decoded and (decoded / 'properties').exists() else []:
        entry = result[path.name.rsplit('.', 2)[0].lower()]
        for item in load(path).get('elements', []):
            entry['sql'] = entry['sql'] or item.get('sql')
            target = (item.get('fields') or {}).get('action_target')
            if target and item.get('name'):
                entry['actions'][item['name'].lower()] = target
    return result


def assess(latest, generator=None, layouter=None):
    """[unit record], most open points first. A record: unit, kind, source, size numbers, `open` (a list of
    {kind, what, closes}) and the facts a brief needs."""
    inspect = Path(latest['inspect'])
    report, code_map = sibling_json(latest, 'evidence_report'), sibling_json(latest, 'code_map').get('units', {})
    legend = sibling_json(latest, 'event_legend').get('codes', {}) if latest.get('event_legend') else {}
    decoded = decoded_units(latest)
    seeds = collections.Counter()
    seed_path = inspect / 'parity-seed.csv'
    if seed_path.exists():
        with seed_path.open(encoding='utf-8') as handle:
            seeds.update(row['element'].lower() for row in csv.DictReader(handle))
    proposals = {group['action']: group.get('proposal') for group in report.get('encoded_actions', [])}
    callers = {name.lower(): sites for name, sites in report.get('callers', {}).items()}
    first_window = next((line.split()[-1].lower() for path in Path(latest.get('dossier') or '.', 'project').glob('*.json')
                         for line in load(path).get('lines', []) if line.startswith('First window ')), None)
    records = []
    for path in sorted((inspect / 'code').rglob('*.json')):
        source = load(path)
        unit = source.get('name')
        if not unit:
            continue
        key, mapped = unit.lower(), next((v for k, v in code_map.items() if k.lower() == unit.lower()), {})
        kind = mapped.get('kind') or {'.wdw': 'window', '.wde': 'report', '.wdc': 'class', '.wdg': 'procedures',
                                      '.wdr': 'query', '.wdp': 'project'}.get(Path(source.get('path', '')).suffix.lower(), 'element')
        blocks = source.get('blocks', [])
        events = [{'control': '/'.join(block['context']['names'][1:]) or unit,
                   'event': legend.get(block['context']['siblings'].get('type') or 'none', {}).get('event')
                   or f"event {block['context']['siblings'].get('type')}",
                   'lines': f"{block['start_line']}-{block['end_line']}", 'procedures': block.get('procedures', [])}
                  for block in blocks]
        opened = []
        # Positions and kinds, from the layout the screen generator would take.
        controls = positioned = 0
        if kind == 'window' and layouter:
            try:
                layout = layouter.layout(unit, latest)
                controls = len(layout['controls'])
                missing = [c['path'] for c in layout['controls'] if c.get('x') is None or c.get('width') is None]
                positioned = controls - len(missing)
                if missing:
                    opened.append({'kind': 'position', 'what': f"{len(missing)} control(s) without a position: {', '.join(missing[:6])}"
                                   + ('…' if len(missing) > 6 else ''),
                                   'closes': 'the dossier image or the running window; place them by hand in the adapter'})
                for line in layout.get('unknown', []):
                    if not line.startswith(GENERIC_UNKNOWN):
                        opened.append({'kind': 'layout', 'what': line, 'closes': 'the dossier, or the window opened in WINDEV'})
                if generator:
                    try:
                        generator.normalize(json.loads(json.dumps(layout)), unit)
                    except ValueError as error:
                        opened.append({'kind': 'generator', 'what': f'generate_screens.py refuses the layout: {error}',
                                       'closes': 'a fix in screen_layout.py or generate_screens.py (report it)'})
            except (SystemExit, KeyError, ValueError, TypeError) as error:
                opened.append({'kind': 'layout', 'what': f'no layout: {error}', 'closes': 'screen_layout.py on this unit, by hand'})
        # Event slots that hold neither code nor an action anyone named.
        for slot in source.get('encoded_slots', []):
            control = slot['names'][-1] if slot['names'] else unit
            if slot.get('has_code') or control.lower() in decoded[key]['actions']:
                continue
            proposal = proposals.get(slot.get('action')) or {}
            opened.append({'kind': 'action', 'what': f"{control}: a predefined action with no code ({slot.get('action')})"
                           + (f"; proposed: {proposal.get('answer')}" if proposal.get('answer') else ''),
                           'closes': 'docs/evidence/encoded-actions.md (one answer per action), or the running application'})
        if kind == 'report' and not decoded[key]['sql'] and any('embedded query' in gap and gap.lower().startswith(key)
                                                                for gap in report.get('gaps', [])):
            opened.append({'kind': 'query', 'what': 'embedded query without its SQL', 'closes': 'the report editor, or a printout on known data'})
        dynamic = [site if isinstance(site, str) else json.dumps(site, ensure_ascii=False) for site in mapped.get('dynamic', [])]
        if dynamic:
            # One point per unit: the sites are read together, and their number says how much of the unit is indirect.
            lines_of = [site.rsplit(':', 1)[-1] for site in dynamic]
            opened.append({'kind': 'dynamic', 'sites': len(dynamic),
                           'what': f"{len(dynamic)} table, item or window name(s) built at run time, at line(s) {', '.join(lines_of[:12])}"
                                   + ('…' if len(lines_of) > 12 else ''),
                           'closes': 'read the code around each; list the values the name can take in the mapping note'})
        for table, sites in mapped.get('unknown_tables', {}).items():
            opened.append({'kind': 'table', 'what': f'{table}: used as a data file, not in the analysis ({len(sites)} site(s))',
                           'closes': 'an alias, a query or an external file: say which in the mapping note'})
        for gap in report.get('gaps', []):
            if gap.lower().startswith(key + ':') or gap.lower().startswith(key + ' '):
                if not ('embedded query' in gap and any(o['kind'] == 'query' for o in opened)) and 'no image' not in gap:
                    opened.append({'kind': 'gap', 'what': gap, 'closes': 'see docs/evidence-report.md'})
        for question in report.get('questions', []):
            if re.search(rf'\b{re.escape(unit)}\b', question['question'], re.I):
                answer = (question.get('proposal') or {}).get('answer')
                opened.append({'kind': 'question', 'what': f"{question['id']}: {question['question']}"
                               + (f' — proposed: {answer}' if answer else ''), 'closes': 'the running application'})
        used_by = callers.get(key, [])
        records.append({
            'unit': unit, 'kind': kind, 'source': source.get('path'), 'seed_rows': seeds[key], 'code_blocks': len(blocks),
            'code_lines': sum(block['end_line'] - block['start_line'] + 1 for block in blocks),
            'controls': controls, 'controls_positioned': positioned, 'open': opened,
            'opened_by': used_by, 'first_window': key == first_window,
            'tables': {name: sorted(k for k in uses if uses[k]) for name, uses in mapped.get('tables', {}).items()},
            'queries': sorted(mapped.get('queries', {})), 'opens': sorted(mapped.get('opens', {})),
            'prints': sorted(mapped.get('prints', {})), 'calls': sorted(mapped.get('calls', {})), 'events': events})
    return sorted(records, key=lambda record: (-len(record['open']), -record['seed_rows'], record['unit'].lower()))


def brief(record):
    """One unit in a page: what an agent reads before opening anything else."""
    lines = [f"# {record['unit']} ({record['kind']})", '',
             f"Source `legacy/{record['source']}` · {record['seed_rows']} parity rows · {record['code_blocks']} code blocks, "
             f"{record['code_lines']} lines" + (f" · {record['controls']} controls" if record['controls'] else ''), '']
    if record['first_window']:
        lines += ['The project opens with this window.', '']
    elif record['kind'] in ('window', 'report'):
        opened = '; '.join(record['opened_by'][:5]) + (f" (+{len(record['opened_by']) - 5})" if len(record['opened_by']) > 5 else '')
        lines += [f"Opened or printed by: {opened}" if opened else 'Nothing in the code opens or prints it: confirm it is in use.', '']
    for title, values in (('Opens', record['opens']), ('Prints', record['prints']), ('Queries', record['queries'])):
        if values:
            lines += [f"{title}: {', '.join(values)}", '']
    if record['tables']:
        lines += ['Data files: ' + '; '.join(f"{name} ({', '.join(uses)})" for name, uses in sorted(record['tables'].items())), '']
    if record['events']:
        lines += ['## Events with code', '', '| Control | Event | Lines | Calls |', '|---|---|---|---|']
        lines += [f"| {event['control']} | {event['event']} | {event['lines']} | {', '.join(event['procedures'][:6])} |"
                  for event in record['events']]
        lines.append('')
    lines += ['## Open points', '']
    lines += [f"- {point['what']} → {point['closes']}" for point in record['open']] or ['None: everything this unit needs is in the evidence.']
    lines += ['', '## Read next, only as needed', '',
              f"- everything about the unit: `python3 scripts/unit_evidence.py {record['unit']}`"]
    if record['kind'] == 'window':
        lines.append(f"- its layout as data: `python3 scripts/screen_layout.py {record['unit']}`; its picture: `docs/evidence/images/{record['unit']}.*`")
    lines.append('- the code itself: the source file above, at the lines of the event you are porting')
    return '\n'.join(lines) + '\n'


def trust(latest):
    """How far the decoder's reading applies to this project, from its own counts: lines for the report, and
    whether anything says "check before trusting". The offsets were measured on one WINDEV version; a project of
    another version shows it here first."""
    coverage, calibration = latest.get('decoded_coverage') or {}, latest.get('decoded_calibration') or {}
    if not coverage:
        return ['The decoder did not run: no designer properties were read from the sources.'], True
    share = lambda part, whole: f'{part} of {whole}' + (f' ({100 * part // whole}%)' if whole else '')
    lines, doubt = [], False
    properties, failed = coverage.get('properties', 0), coverage.get('properties_failed', 0)
    lines.append(f'- designer properties decoded: {share(properties - failed, properties)}')
    controls, read = coverage.get('controls', 0), coverage.get('controls_with_fields', 0)
    lines.append(f'- window controls with position and size: {share(read, controls)}')
    if coverage.get('report_controls'):
        lines.append(f"- report controls with geometry: {share(coverage.get('report_controls_with_geometry', 0), coverage['report_controls'])}")
    if coverage.get('binary_windows') or coverage.get('binary_reports'):
        lines.append(f"- elements read from binary files: {coverage.get('binary_windows', 0)} windows, {coverage.get('binary_reports', 0)} reports")
    if 'analysis_tables' in coverage:
        lines.append(f"- analysis file: {coverage['analysis_tables']} data files, {coverage.get('analysis_items', 0)} items")
    doubt = bool(failed) or (controls and read < 0.95 * controls)
    if calibration:
        compared = {field: counts for field, counts in calibration.items() if counts.get('same', 0) + counts.get('different', 0)}
        off = {field: counts for field, counts in compared.items()
               if counts['different'] > 0.02 * (counts['same'] + counts['different'])}
        differing = ', '.join('{} ({} of {} differ)'.format(field, counts['different'], counts['same'] + counts['different'])
                              for field, counts in sorted(off.items()))
        lines.append(f'- against the printed dossier: {len(compared)} kinds of field compared, {len(compared) - len(off)} agree'
                     + (f'; **check before use**: {differing}' if off else ''))
    else:
        lines.append('- against a printed dossier: nothing compared (no dossier). The positions inside each record were '
                     'measured on one WINDEV version: print the dossier of three or four windows once and run again, or '
                     'compare a few layouts with the running application (docs/new-windev-version.md)')
    return lines, doubt


def markdown(records, latest=None):
    opened = [record for record in records if record['open']]
    kinds = collections.Counter(point['kind'] for record in records for point in record['open'])
    labels = {'position': 'controls without a position', 'layout': 'layout facts missing', 'generator': 'layouts the generator refuses',
              'action': 'predefined actions with no code and no named element', 'query': 'embedded queries without SQL',
              'dynamic': 'units that build names at run time', 'table': 'data files not in the analysis', 'gap': 'evidence gaps',
              'question': 'runtime questions'}
    lines = ['# Readiness: what the evidence leaves open, unit by unit', '',
             'Generated by `scripts/readiness_report.py` from the evidence of `prepare_evidence.py`. An open point is something '
             'an implementer would have to guess; each says what closes it. Plan the first slices among the units with none, '
             'and settle the points of a unit before its slice starts.', '',
             f"{len(records)} units, {len(records) - len(opened)} with no open point, "
             f"{sum(len(record['open']) for record in records)} open points in {len(opened)} units.", '']
    if latest is not None:
        facts, doubt = trust(latest)
        lines += ['## How far the decoder applies here', '',
                  *(['**Something below does not hold for this project: treat layouts and decoded properties as unverified '
                     'until docs/new-windev-version.md is followed.**', ''] if doubt else []), *facts, '']
    if kinds:
        lines += ['| Open points | Count |', '|---|---|'] + [f'| {labels.get(kind, kind)} | {count} |' for kind, count in kinds.most_common()] + ['']
    lines += ['## Units, most open points first', '', '| Unit | Kind | Open | Parity rows | Code lines | Controls placed |', '|---|---|---|---|---|---|']
    for record in records:
        placed = f"{record['controls_positioned']}/{record['controls']}" if record['controls'] else ''
        lines.append(f"| {record['unit']} | {record['kind']} | {len(record['open'])} | {record['seed_rows']} | {record['code_lines']} | {placed} |")
    lines += ['', '## Open points', '']
    for record in opened:
        lines += [f"### {record['unit']}", ''] + [f"- {point['what']} → {point['closes']}" for point in record['open']] + ['']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--latest', type=Path, default=Path('analysis-local/latest.json'), help='paths from prepare_evidence.py')
    parser.add_argument('--out', type=Path, required=True, help='Markdown report (a .json sibling is written)')
    parser.add_argument('--briefs', type=Path, help='also write one short brief per unit in this folder')
    args = parser.parse_args()
    latest = load(args.latest)
    records = assess(latest, tool('generate_screens'), tool('screen_layout'))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown(records, latest), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding='utf-8')
    if args.briefs:
        args.briefs.mkdir(parents=True, exist_ok=True)
        for record in records:
            (args.briefs / f"{record['unit']}.md").write_text(brief(record), encoding='utf-8')
    opened = sum(bool(record['open']) for record in records)
    print(f"{len(records)} units, {len(records) - opened} with no open point, {sum(len(r['open']) for r in records)} open points"
          + (f'; briefs in {args.briefs}' if args.briefs else ''))


if __name__ == '__main__':
    main()
