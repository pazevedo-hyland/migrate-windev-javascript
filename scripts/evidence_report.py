#!/usr/bin/env python3
"""One report on whether the evidence is complete before mapping starts.

Merges the inspector output, the dossier extract and the event legend, and writes:
  1. coverage per element (windows, reports, queries, tables): what evidence exists and what is missing;
  2. platform usage: the WLanguage functions the code calls, grouped by what the new app must provide,
     with literal arguments (command-line options, INI files, external programs, printed reports);
  3. runtime questions: what only someone watching the running app can answer.
"""
import argparse
import collections
import json
from pathlib import Path
import re

CATEGORIES = {
    'data access': ['HReadSeek', 'HReadSeekFirst', 'HReadFirst', 'HReadNext', 'HReadLast', 'HReadPrevious', 'HFound',
                    'HOut', 'HAdd', 'HModify', 'HDelete', 'HReset', 'HFilter', 'HDeactivateFilter', 'HExecuteQuery',
                    'HExecuteSQLQuery', 'HCancelDeclaration', 'HNbRec', 'HLockRecord', 'HLockFile', 'HUnlockRecNum',
                    'HOnError', 'HTransactionStart', 'HTransactionEnd', 'HTransactionCancel', 'HOpenConnection',
                    'HChangeConnection', 'HDescribeConnection', 'HChangeDir', 'HSubstDir', 'HDescribeTrigger',
                    'HCreationIfNotFound', 'ScreenToFile', 'FileToScreen'],
    'windows and navigation': ['Open', 'OpenChild', 'OpenSister', 'Close', 'ExecuteProcess', 'WinStatus', 'Restore',
                               'MenuDelete', 'SetFocus', 'ReturnToCapture'],
    'dialogs': ['Info', 'Error', 'YesNo', 'OKCancel', 'Dialog', 'Confirm', 'Warning'],
    'tables and lists': ['TableDisplay', 'TableSelect', 'TableDelete', 'TableAdd', 'ListAdd', 'ListSeek',
                         'ListSelectPlus', 'ListDisplay'],
    'printing and reports': ['iPrintReport', 'iPreview', 'iDestination', 'iPrint', 'iConfigure'],
    'files, INI and registry': ['fOpen', 'fClose', 'fRead', 'fWrite', 'fDelete', 'fCopyFile', 'fFileExist',
                                'fExeDir', 'fCurrentDir', 'fDataDir', 'CompleteDir', 'INIRead', 'INIWrite',
                                'RegistryQueryValue', 'RegistrySetValue'],
    'external programs and system': ['ExeRun', 'ShellExecute', 'CommandLine', 'EndProgram', 'SysEnvironment',
                                     'NetMachineName', 'KeyPressed', 'Multitask', 'Timer', 'TimerSys', 'ThreadExecute'],
    'email, web, devices': ['EmailStartSMTPSession', 'EmailSendMessage', 'HTTPRequest', 'RESTSend', 'sOpen',
                            'sRead', 'sWrite', 'Beep', 'Speak'],
}
LITERALS = {'CommandLine': 0, 'INIRead': 3, 'INIWrite': 3, 'ExeRun': 0, 'iPrintReport': 0, 'Open': 0,
            'OpenChild': 0, 'fOpen': 0}


class CaseInsensitive(dict):
    """WINDEV names are case-insensitive: the dossier and the sources may spell them differently."""

    def __init__(self, items):
        super().__init__(items)
        self.lower = {k.lower(): k for k in items}

    def get(self, key, default=None):
        return super().get(self.lower.get(key.lower(), key), default)


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def elements_from_inspector(inspect_dir):
    elements = {}
    for path in Path(inspect_dir, 'code').rglob('*.json'):
        data = load_json(path)
        elements[data.get('name') or Path(data['path']).stem] = {'path': data['path'], **data}
    return elements


def dossier_items(dossier_dir):
    if not dossier_dir:
        return {}, {}, {}, {}
    root = Path(dossier_dir)
    load = lambda kind: CaseInsensitive({p.stem: load_json(p) for p in (root / kind).glob('*.json')})
    analysis = next(iter(load('analysis').values()), {})
    return load('windev-window'), load('report'), load('query'), analysis.get('files', {})


def coverage(inspect_dir, dossier_dir, schema_tables):
    inspected = elements_from_inspector(inspect_dir)
    windows, reports, queries, tables = dossier_items(dossier_dir)
    rows, gaps = [], []
    for name, data in sorted(inspected.items(), key=lambda item: item[0].lower()):
        kind = Path(data['path']).suffix.lower()
        if kind not in ('.wdw', '.wde'):
            continue
        dossier = (windows if kind == '.wdw' else reports).get(name)
        layout = [c for c in data.get('layout', []) if c['kind'] == 'control']
        described = set((dossier or {}).get('controls', {}))
        captioned = {n for n, c in (dossier or {}).get('controls', {}).items() if c.get('caption')}
        missing = [c['name'] for c in layout if c['name'] not in described]
        row = {'element': name, 'kind': 'window' if kind == '.wdw' else 'report', 'code_blocks': len(data['blocks']),
               'controls': len(layout), 'dossier': bool(dossier), 'described': len(described & {c['name'] for c in layout}),
               'captions': len(captioned), 'image': bool((dossier or {}).get('image_file')),
               'dialogs': len(data.get('dialogs', []))}
        rows.append(row)
        if not dossier:
            gaps.append(f'{name}: no dossier entry (captions, tab order, masks unknown)')
        elif missing:
            gaps.append(f'{name}: {len(missing)} controls without dossier description: {", ".join(missing[:8])}')
        if dossier and not row['image']:
            gaps.append(f'{name}: no image in the dossier')
    for name, query in sorted(queries.items()):
        rows.append({'element': name, 'kind': 'query', 'sql': bool(query.get('sql')),
                     'parameters': len(query.get('parameters', []))})
        if not query.get('sql'):
            gaps.append(f'{name}: query without SQL in the dossier')
    for name in sorted(schema_tables):
        described = tables.get(name)
        rows.append({'element': name, 'kind': 'table', 'items': len((described or {}).get('items', [])),
                     'typed': bool(described)})
        if not described:
            gaps.append(f'{name}: table without typed items in the dossier analysis')
    return rows, gaps


def arguments(code, start):
    """Top-level call arguments from just after '(' (nested calls and strings respected)."""
    args, depth, current, quoted = [], 0, '', False
    for char in code[start:]:
        if char == '"':
            quoted = not quoted
        elif not quoted and char == '(':
            depth += 1
        elif not quoted and char == ')':
            if depth == 0:
                break
            depth -= 1
        elif not quoted and char == ',' and depth == 0:
            args.append(current.strip())
            current = ''
            continue
        current += char
    args.append(current.strip())
    return args


def calls(inspect_dir):
    """{function: [(element, line, first literal argument)]} across all code blocks."""
    names = {n.lower(): n for group in CATEGORIES.values() for n in group}
    pattern = re.compile(r'\b(' + '|'.join(sorted(names, key=len, reverse=True)) + r')\s*\(', re.I)
    found = collections.defaultdict(list)
    for name, data in elements_from_inspector(inspect_dir).items():
        for block in data['blocks']:
            for offset, line in enumerate(block['code'].splitlines()):
                code = line.split('//', 1)[0]
                for match in pattern.finditer(code):
                    function = names[match[1].lower()]
                    found_args = arguments(code, match.end())
                    index = LITERALS.get(function)
                    literal = found_args[index] if index is not None and index < len(found_args) else ''
                    found[function].append((name, block['start_line'] + offset, literal))
    return found


def text_in(labels, language):
    return labels.get(language) or next(iter(labels.values()), '?')


def runtime_questions(inspect_dir, dossier_dir, language='pt-PT'):
    """What the code and the dossier cannot settle. Identical dialogs are asked once."""
    questions = []
    windows, _, _, _ = dossier_items(dossier_dir)
    dialogs = collections.defaultdict(list)
    for name, data in sorted(elements_from_inspector(inspect_dir).items()):
        for dialog in data.get('dialogs', []):
            key = (text_in(dialog['label'], language),
                   tuple(text_in(b['label'], language) for b in dialog['buttons']), dialog['cancel_button'])
            dialogs[key].append(name)
    for (message, labels, cancel), used_in in sorted(dialogs.items(), key=lambda item: -len(item[1])):
        questions.append(f'Dialog "{message}" ({" / ".join(labels)}), in {len(used_in)} window(s): '
                         f'{", ".join(used_in[:6])}{"…" if len(used_in) > 6 else ""} — which button do Esc and the '
                         f'close box trigger? (cancel_button = {cancel}; position or value is not documented)')
    validates = collections.defaultdict(list)
    for name, data in sorted(elements_from_inspector(inspect_dir).items()):
        code = '\n'.join(b['code'] for b in data['blocks'])
        for control, details in windows.get(name, {}).get('controls', {}).items():
            raw = ' '.join(details.get('raw', [])) + ' ' + details.get('row', '')
            if details.get('kind') == 'Button' and re.search(r'\bValidate\b', raw) and 'Close(' not in code:
                caption = details.get('caption')
                caption = next(iter(caption.values())) if isinstance(caption, dict) else caption or control
                validates[caption].append(f'{name}.{control}')
    # Windows built from the same template behave alike: one question per caption.
    for caption, used_in in sorted(validates.items(), key=lambda item: -len(item[1])):
        questions.append(f'Validate button "{caption}" with no Close() in code, in {len(used_in)} window(s): '
                         f'{", ".join(used_in[:5])}{"…" if len(used_in) > 5 else ""} — after its code succeeds, '
                         'does the window close?')
    return questions


def markdown(rows, gaps, used, questions):
    lines = ['# Evidence report', '', '## 1. Coverage', '',
             '| Element | Kind | Code blocks | Controls | Dossier | Described | Captions | Image | Dialogs | SQL | Items |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        cell = lambda key: ('✅' if r[key] is True else '❌' if r[key] is False else r[key]) if key in r else ''
        lines.append(f"| {r['element']} | {r['kind']} | {cell('code_blocks')} | {cell('controls')} | {cell('dossier')} | "
                     f"{cell('described')} | {cell('captions')} | {cell('image')} | {cell('dialogs')} | {cell('sql')} | "
                     f"{cell('items')} |")
    lines += ['', f'### Gaps ({len(gaps)})', ''] + [f'- {g}' for g in gaps] + ['', '## 2. Platform usage', '']
    for category, functions in CATEGORIES.items():
        present = [(f, used[f]) for f in functions if used.get(f)]
        if not present:
            continue
        lines.append(f'**{category}**: ' + ', '.join(f'`{f}` ×{len(sites)}' for f, sites in present))
        for function, sites in present:
            literals = sorted({s[2] for s in sites if s[2]})
            if function in LITERALS and literals and function not in ('Open', 'OpenChild'):
                lines.append(f'  - `{function}` arguments: ' + ', '.join(f'`{l}`' for l in literals[:15]))
        lines.append('')
    lines += [f'## 3. Runtime questions ({len(questions)})', '',
              'Only someone using the running application can answer these. Record answers as evidence.', '']
    lines += [f'- [ ] {q}' for q in questions]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inspect_dir', type=Path, help='inspect_windev.py output')
    parser.add_argument('--dossier', type=Path, help='dossier_extract.py output')
    parser.add_argument('--out', type=Path, required=True, help='Markdown report (a .json sibling is written too)')
    parser.add_argument('--language', default='pt-PT', help="the application's language for dialog texts")
    args = parser.parse_args()
    inventory = load_json(args.inspect_dir / 'inventory.json')
    tables = set()
    for path in Path(args.inspect_dir, 'schema').rglob('*.json'):
        tables |= {t['attributes'].get('Nom') or t['attributes'].get('Name', '') for t in load_json(path)['tables']}
    rows, gaps = coverage(args.inspect_dir, args.dossier, tables)
    used = calls(args.inspect_dir)
    questions = runtime_questions(args.inspect_dir, args.dossier, args.language)
    args.out.write_text(markdown(rows, gaps, used, questions), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(
        {'files': len(inventory['files']), 'coverage': rows, 'gaps': gaps, 'questions': questions,
         'usage': {f: [list(s) for s in sites] for f, sites in used.items()}}, indent=1, ensure_ascii=False),
        encoding='utf-8')
    print(f'{len(rows)} elements, {len(gaps)} gaps, {len(used)} platform functions used, {len(questions)} runtime questions')


if __name__ == '__main__':
    main()
