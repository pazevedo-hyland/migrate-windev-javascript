#!/usr/bin/env python3
"""Plan an unattended UI capture of a WINDEV app from inspector output.

For every window: which menu options or buttons open it, with which arguments, and whether
clicking that path is safe (only opens windows) and whether the window writes data when it
opens. The Windows capture script follows only safe paths.
"""
import argparse
import json
from pathlib import Path
import re

OPEN = re.compile(r'\b(Open|OpenChild|OpenSister|Ouvre|OuvreFille|OuvreSoeur)\s*\(\s*([A-Za-z_]\w*)\s*(?:,([^)]*))?\)', re.I)
# Statements a navigation-only block may contain.
NAVIGATION = re.compile(r'^(SWITCH|SELON|CASE|CAS|OTHER CASE|AUTRE CAS|END|FIN|IF|SI|ELSE|SINON|RETURN|RENVOYER'
                        r'|WinStatus|FenEtat|Restore|Restaure|Open|OpenChild|OpenSister|Ouvre|OuvreFille|OuvreSoeur)\b', re.I)
WRITES = re.compile(r'\b(HAdd|HModify|HDelete|HWrite|HCross|HDeleteAll|HCreation\w*|HImport\w*|HModifyStructure'
                    r'|HAjoute|HModifie|HSupprime|HEcrit|HRaye|HSupprimeTout|HCréation\w*|TableDelete|TableSupprime'
                    r'|fDelete|fSupprime|fRemove|fCopyFile|fRename|fCreate|fWrite|fEcrit|INIWrite|INIEcrit|RegistrySet\w*'
                    r'|ExeRun|LanceAppli|iPrint\w*|iImprime\w*|EmailSend\w*|HTTPRequest|EndProgram|FinProgramme)\b', re.I)
SQL_WRITE = re.compile(r'\b(insert\s+into|update\s+\w+\s+set|delete\s+from|drop\s+|alter\s+table)', re.I)
RUNS_QUERY = re.compile(r'\b(HExecuteQuery|HExecuteSQLQuery|HExécuteRequête\w*)\b', re.I)


def statements(code):
    for line in code.splitlines():
        line = line.split('//', 1)[0].strip()
        if line:
            yield line


def classify(code, query_writes=()):
    """'writes' if the code changes data or leaves the app, 'navigation' if it only opens windows."""
    lowered = code.lower()
    if WRITES.search(code) or SQL_WRITE.search(code) or any(q.lower() in lowered for q in query_writes):
        return 'writes'
    if all(NAVIGATION.match(s) for s in statements(code)):
        return 'navigation'
    return 'review'


LAYOUTS = {}


def load_blocks(inspect_dir):
    for path in sorted(Path(inspect_dir, 'code').rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        element = Path(data['path']).stem
        LAYOUTS[element.lower()] = data.get('layout', [])
        for block in data['blocks']:
            yield element, data['path'], block


def plan(inspect_dir):
    blocks = list(load_blocks(inspect_dir))
    # Queries named like writes (QRY_insert_…) are binary: treat calls to them as writes.
    query_writes = sorted({m for _, _, b in blocks for m in re.findall(r'\bQRY_\w*(?:insert|update|delete)\w*', b['code'], re.I)})
    windows = {}
    for element, path, block in blocks:
        if path.lower().endswith('.wdw'):
            windows.setdefault(element.lower(), {'window': element, 'source': path, 'entries': [],
                                                 'layout': LAYOUTS.get(element.lower(), []),
                                                 'opening_code': [], 'opening': 'no-writes'})
    for element, path, block in blocks:
        names = block['context']['names']
        event = block['context']['siblings'].get('type')
        window = windows.get(element.lower())
        # Window-level blocks (declarations, init, close): writing there makes opening or closing unsafe.
        if window and len(names) <= 1:
            writes = classify(block['code'], query_writes) == 'writes'
            window['opening_code'].append({'lines': f"{block['start_line']}-{block['end_line']}", 'event': event,
                                           'writes': writes, 'queries': bool(RUNS_QUERY.search(block['code']))})
        kind = classify(block['code'], query_writes)
        for match in OPEN.finditer(block['code']):
            target = windows.get(match[2].lower())
            if not target:
                continue
            target['entries'].append({
                'from': element, 'control': names[-1] if len(names) > 1 else element,
                'path': '/'.join(names), 'event': event, 'call': match[0],
                'arguments': (match[3] or '').strip(), 'evidence': f"{path}:{block['start_line']}-{block['end_line']}",
                'click': kind})
    for window in windows.values():
        # Event codes are raw, so every window-level block counts, including closing code.
        if any(c['writes'] for c in window['opening_code']):
            window['opening'] = 'writes'
        clicks = {e['click'] for e in window['entries']}
        if not window['entries']:
            window['capture'] = 'unreachable'
        elif window['opening'] == 'writes':
            window['capture'] = 'manual'
        elif 'navigation' in clicks:
            window['capture'] = 'auto'
        elif 'review' in clicks:
            window['capture'] = 'auto-review'
        else:
            window['capture'] = 'manual'
    return {'format_version': 1, 'query_writes': query_writes,
            'windows': sorted(windows.values(), key=lambda w: w['window'].lower())}


def checklist(result):
    lines = ['# Capture plan', '', '| Window | Capture | Opened from | Opening code |', '|---|---|---|---|']
    for w in result['windows']:
        entries = '; '.join(f"{e['path'] or e['from']} ({e['click']})" for e in w['entries'][:3]) or '—'
        lines.append(f"| {w['window']} | {w['capture']} | {entries} | {w['opening']} |")
    counts = {}
    for w in result['windows']:
        counts[w['capture']] = counts.get(w['capture'], 0) + 1
    lines += ['', 'Totals: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())),
              '', '`auto`: a caller only opens windows and the window writes nothing on open/close. '
              '`auto-review`: callers run other code but no detected writes — captured only with --allow-review. '
              '`manual`: every caller writes, or the window writes on open/close. `unreachable`: no caller in code '
              '(main window, or opened dynamically). Every automated step is still guarded by data-file hashes.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inspect_dir', type=Path, help='inspect_windev.py output directory')
    parser.add_argument('--out', type=Path, required=True, help='capture-plan.json to write')
    args = parser.parse_args()
    result = plan(args.inspect_dir)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    args.out.with_suffix('.md').write_text(checklist(result), encoding='utf-8')
    print(checklist(result).split('Totals: ')[1].splitlines()[0])


if __name__ == '__main__':
    main()
