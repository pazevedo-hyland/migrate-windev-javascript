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
            'OpenChild': 0, 'OpenSister': 0, 'ExecuteProcess': 0, 'fOpen': 0}


# Buttons of WINDEV's skin templates, named alike in every project that uses one.
TEMPLATE_BUTTONS = [(r'SYST_?(FERMER|CLOSE)', 'Close the window'), (r'SYST_?MINI', 'Minimize the window'),
                    (r'SYST_?MAXI', 'Maximize or restore the window'),
                    (r'^BTN_UMC$', "Open WINDEV's user macro-code editor (U.M.C., a WINDEV developer feature): "
                                   'propose to exclude')]
RETURNS = re.compile(r'\.\.ReturnedValue\s*=', re.I)
CLOSES = re.compile(r'\bClose\s*\(', re.I)
CLOSES_AFTER = ('closes when its code runs to the end; stays open when the code stops early with RETURN '
                '(a failed check)')


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
    # `_general` holds a part's overview page, not an element.
    load = lambda kind: CaseInsensitive({p.stem: load_json(p) for p in (root / kind).glob('*.json')
                                         if not p.stem.startswith('_')})
    analysis = next(iter(load('analysis').values()), {})
    return load('windev-window'), load('report'), load('query'), analysis.get('files', {})


def coverage(inspect_dir, dossier_dir, schema_tables):
    inspected = elements_from_inspector(inspect_dir)
    windows, reports, queries, tables = dossier_items(dossier_dir)
    index = Path(dossier_dir or '.', 'index.json')
    images = load_json(index).get('images', True) if dossier_dir and index.exists() else True
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
        if dossier and not row['image'] and images:  # an extract run with --no-images has none at all
            gaps.append(f'{name}: no image in the dossier')
        if (dossier or {}).get('data_source') == 'Embedded query':
            gaps.append(f'{name}: embedded query — its SQL is not in the dossier (the items it selects are in '
                        'docs/mapping/event-codes.md from the compile folder; export the conditions and sort from the '
                        'report editor, or derive them from a legacy printout on known data)')
        encoded = [s for s in data.get('encoded_slots', []) if not s['has_code']]
        row['encoded_actions'] = len(encoded)
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
    """{function: [(element, line, the naming argument, source path)]} across all code blocks."""
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
                    # The argument that names what is called (LITERALS); otherwise the first one (the file, control…).
                    position = index if index is not None else 0
                    literal = found_args[position] if position < len(found_args) else ''
                    found[function].append((name, block['start_line'] + offset, literal, data.get('path', name)))
    return found


def text_in(labels, language=None):
    return (labels.get(language) if language else None) or next(iter(labels.values()), '?')


def control_code(data, control):
    """The code of one control's events (WLanguage names are case-insensitive)."""
    return '\n'.join(b['code'] for b in data['blocks']
                     if (b.get('context', {}).get('names') or [''])[-1].lower() == control.lower())


def callers(used):
    """{element: ['<source path>:<line> (<function> in <caller>)']}: who opens each window and prints each report.

    Paths are relative to the folder the inspector read (prefix it, e.g. `legacy/code/`)."""
    index = collections.defaultdict(list)
    for function in ('Open', 'OpenChild', 'OpenSister', 'iPrintReport', 'ExecuteProcess'):
        for element, line, literal, *path in used.get(function, []):
            target = re.match(r'[A-Za-z_][\w$]*', literal or '')
            if target:
                index[target[0]].append(f'{path[0] if path else element}:{line} ({function} in {element})')
    # WLanguage names are case-insensitive: open(win_sistema) opens WIN_sistema.
    merged = collections.defaultdict(set)
    spelling = {}
    for name, sites in index.items():
        spelling.setdefault(name.lower(), name)
        merged[name.lower()].update(sites)
    return CaseInsensitive({spelling[key]: sorted(sites) for key, sites in merged.items()})


def navigation(caller_index, rows, first):
    """Navigation map (Mermaid) from proven call sites: who opens each window and prints each report.
    Elements with no caller are listed, not guessed: the encoded actions may open them."""
    kinds = {row['element']: row['kind'] for row in rows}
    edges = collections.defaultdict(list)
    for target, sites in caller_index.items():
        for site in sites:
            match = re.match(r'(.+):(\d+) \((\w+) in (\w+)\)$', site)
            if match:
                edges[(match[4], target, match[3])].append(f'{match[1]}:{match[2]}')
            elif re.match(r'(\w+) \(named in its compiled code', site):
                edges[(site.split()[0], target, 'compiled')].append('compile folder')
    node = lambda name: re.sub(r'\W', '_', name)
    lines = ['# Navigation map (from code)', '',
             'Generated by `scripts/evidence_report.py` from `Open`/`OpenChild`/`OpenSister`/`iPrintReport`/`ExecuteProcess` '
             'call sites with a literal target; dashed: the target is only named in the caller\'s compiled code (a '
             'predefined action or a dynamic call). Windows or reports reached in no known way are listed below.', '', '```mermaid', 'flowchart LR']
    if first:
        lines.append(f'  START(( )) --> {node(first)}')
    for (caller, target, function), sites in sorted(edges.items()):
        shape = f'{node(target)}[/{target}/]' if kinds.get(target) == 'report' else f'{node(target)}[{target}]'
        label = '' if function == 'Open' else f'|{function}|'
        arrow = '-.->' if function == 'compiled' else '-->'  # named in compiled code only: who, not how
        lines.append(f'  {node(caller)}[{caller}] {arrow}{label} {shape}')
    lines.append('```')
    reached = {target.lower() for _, target, _ in edges} | {(first or '').lower()}
    orphans = sorted(r['element'] for r in rows if r['kind'] in ('window', 'report') and r['element'].lower() not in reached)
    lines += ['', f'## Not reached in any known way ({len(orphans)})', '']
    lines += [f'- {name} ({kinds[name]})' for name in orphans]
    lines += ['', '## Call sites', '', '| From | To | Function | Evidence |', '|---|---|---|---|']
    lines += [f'| {c} | {t} | {f} | {", ".join(s[:4])}{"…" if len(s) > 4 else ""} |' for (c, t, f), s in sorted(edges.items())]
    return '\n'.join(lines) + '\n'


def first_window(dossier_dir):
    """The project's first window, as the dossier's project section states it (it has no caller)."""
    for path in Path(dossier_dir or '.', 'project').glob('*.json') if dossier_dir else []:
        for line in load_json(path).get('lines', []):
            if line.startswith('First window '):
                return line.split(' ', 2)[2].strip()
    return None


def runtime_questions(inspect_dir, dossier_dir, language=None, actions=(), skinned=()):
    """What the code and the dossier cannot settle, each with the answer the evidence or WINDEV's convention proposes:
    [(question, {'answer', 'basis'})]. The work goes on with the proposal; a person confirms or corrects it later.
    Identical dialogs are asked once."""
    questions = []
    windows, _, _, _ = dossier_items(dossier_dir)
    elements = elements_from_inspector(inspect_dir)
    dialogs = collections.defaultdict(list)
    for name, data in sorted(elements.items()):
        for dialog in data.get('dialogs', []):
            key = (text_in(dialog['label'], language),
                   tuple(text_in(b['label'], language) for b in dialog['buttons']), dialog['cancel_button'])
            dialogs[key].append(name)
    for (message, labels, cancel), used_in in sorted(dialogs.items(), key=lambda item: -len(item[1])):
        questions.append((f'Dialog "{message}" ({" / ".join(labels)}), in {len(used_in)} window(s): '
                          f'{", ".join(used_in[:6])}{"…" if len(used_in) > 6 else ""} — which button do Esc and the '
                          f'close box trigger? (cancel_button = {cancel}; position or value is not documented)',
                          {'answer': f'"{labels[-1]}"', 'basis': 'convention: the last button is the cancel choice, '
                                                                 'and the one that changes nothing'}))
    closing = {(s['element'].lower(), s['control'].lower()): a for a in actions for s in a['slots']
               if 'Close the window' in (a.get('proposal') or {}).get('answer', '')}
    validates = collections.defaultdict(list)
    for name, data in sorted(elements.items()):
        for control, details in windows.get(name, {}).get('controls', {}).items():
            raw = ' '.join(details.get('raw', [])) + ' ' + details.get('row', '')
            if details.get('kind') != 'Button' or not re.search(r'\bValidate\b', raw):
                continue
            short = control.split('.')[-1]
            code = control_code(data, short)
            if CLOSES.search(code):
                continue
            action = closing.get((name.lower(), short.lower()))
            if action:
                proposal = (CLOSES_AFTER, f"its predefined action {action['action']} closes the window")
            elif RETURNS.search(code):
                proposal = (CLOSES_AFTER, 'the code sets ..ReturnedValue, which reaches the caller only '
                                          'when the window closes')
            else:
                proposal = ('stays open', 'WINDEV closes a window only by Close() or a predefined action; '
                                          'neither is there')
            caption = details.get('caption')
            caption = next(iter(caption.values())) if isinstance(caption, dict) else caption or short
            validates[(caption, proposal)].append(f'{name}.{short}')
    # Windows built from the same template behave alike: one question per caption and proposal.
    for (caption, (answer, basis)), used_in in sorted(validates.items(), key=lambda item: -len(item[1])):
        questions.append((f'Validate button "{caption}" with no Close() in its code, in {len(used_in)} window(s): '
                          f'{", ".join(used_in[:5])}{"…" if len(used_in) > 5 else ""} — after its code succeeds, '
                          'does the window close?', {'answer': answer, 'basis': basis}))
    # Message boxes are drawn by WINDEV itself: title, icon and button labels are in no source. One screenshot of
    # each kind settles every box of the application.
    kinds = collections.Counter()
    for data in elements.values():
        for block in data['blocks']:
            kinds.update(m.group(1) for m in re.finditer(r'\b(Info|Error|Warning|YesNo|OKCancel|Confirm)\s*\(',
                                                         block['code']))
    if kinds:
        used = ', '.join(f'{k} ×{v}' for k, v in kinds.most_common())
        look = ("drawn with the project's skin template (the compile folder holds " + ', '.join(skinned) + ')'
                if skinned else "Windows' standard message box")
        questions.append((f'Message boxes ({used}): a screenshot of one of each kind — what are the title, icon and '
                          'button labels, and which button is the default?',
                          {'answer': f'{look}; title: the application\'s title; standard Info/Error/Question icons; '
                                     'OK, or Yes/No for YesNo; the first button is the default, except on a '
                                     'confirmation that deletes or overwrites: the safe one until confirmed',
                           'basis': 'WINDEV default message boxes' + (' customized by the skin template' if skinned else '')}))
    return questions


def encoded_actions(inspect_dir, dossier_dir, language=None):
    """Event slots with encoded properties grouped by action ID (equal encoded values = same predefined action),
    largest first; slots that also have code are included and marked. Answering one group (WINDEV: the control's
    Actions tab, or clicking it in the app) settles all its slots."""
    windows, reports, _, _ = dossier_items(dossier_dir)
    groups = collections.defaultdict(list)
    for name, data in sorted(elements_from_inspector(inspect_dir).items()):
        described = (windows.get(name) or reports.get(name) or {}).get('controls', {})
        for slot in data.get('encoded_slots', []):
            control = slot['names'][-1]
            details = described.get(control) or next((c for n, c in described.items() if n.split('.')[-1] == control), {})
            caption = details.get('caption')
            caption = text_in(caption, language) if isinstance(caption, dict) else caption
            groups[slot.get('action', '?')].append({'element': name, 'control': control, 'event': slot['event'],
                                                    'caption': caption, 'button_type': details.get('button_type'),
                                                    'has_code': slot['has_code'],
                                                    'evidence': f"{data['path']}:{slot['line']}"})
    return [{'action': action, 'slots': slots} for action, slots in sorted(groups.items(), key=lambda kv: -len(kv[1]))]


def propose_actions(actions, inspect_dir, uncalled, preview):
    """The answer the evidence proposes for each action group, strongest rule first, or a labelled default.
    uncalled: {window: [reports no code calls but its compiled code names]}, case-insensitive."""
    elements = CaseInsensitive(elements_from_inspector(inspect_dir))
    left = collections.defaultdict(list)  # window -> code-less groups no rule explains, all in that window
    for group in actions:
        slots = group['slots']
        named = {answer for s in slots for pattern, answer in TEMPLATE_BUTTONS if re.search(pattern, s['control'], re.I)}
        coded = [control_code(elements.get(s['element'], {'blocks': []}), s['control']) for s in slots if s['has_code']]
        proposal = None
        if len(named) == 1:
            # Equal encoded values are the same action: the skin template's own button names the whole group.
            example = next(s['control'] for s in slots if any(re.search(p, s['control'], re.I) for p, _ in TEMPLATE_BUTTONS))
            proposal = (next(iter(named)), f'same encoded action as the skin-template button {example}')
        elif all(s['button_type'] == 'Abort' for s in slots):
            proposal = ('Close the window without saving', 'every control in the group is an Abort button')
        elif coded and len(coded) == len(slots):
            proposal = (('Close the window after the code (it returns the value the code sets)',
                         'the code sets ..ReturnedValue, which reaches the caller only when the window closes')
                        if all(RETURNS.search(c) and not CLOSES.search(c) for c in coded)
                        else ('Nothing beyond the code next to it', 'default: the code does the work'))
        elif not coded and len({s['element'].lower() for s in slots}) == 1:
            left[slots[0]['element'].lower()].append(group)
        if proposal:
            group['proposal'] = {'answer': proposal[0], 'basis': proposal[1]}
    for window, groups in left.items():
        reports = uncalled.get(window) or []
        if len(groups) == 1 and len(reports) == 1:  # the one unexplained control and the one report nothing calls
            groups[0]['proposal'] = {
                'answer': f'Print {reports[0]}' + (" (preview first, as the app's own print calls do)" if preview else ''),
                'basis': f"the compiled code of {groups[0]['slots'][0]['element']} names {reports[0]}, which no code calls, "
                         'and no other rule explains this control'}
    for group in actions:
        group.setdefault('proposal', {'answer': 'Nothing (the control does nothing)',
                                      'basis': 'default: no evidence of what it does'})
    return actions


def answer_sheet(actions, questions):
    """A fill-in sheet for someone with WINDEV or the running app: one line per action group and question, with the
    proposal the migration uses until an answer is written."""
    proposed = lambda p: f"{p['answer']} — {p['basis']}".replace('|', '/') if p else ''
    lines = ['# Answers from WINDEV or the running app', '',
             'The migration does not wait for these: it builds with `Proposed` and cites `proposed: A-xxxxxx` (or `Q-nn`). '
             'Confirm or correct it: fill `Answer`, `How checked` (WINDEV Actions tab / used in the app / other) and '
             '`By, date`; rows then cite `runtime: A-xxxxxx`, and a different answer reopens the rows that cited the '
             'proposal. New groups appear in docs/evidence-report.md §4 when the evidence is regenerated: add them here '
             'by hand; this file is never overwritten (only the Proposed cell of an unanswered line is refreshed).', '',
             '## Encoded actions', '', '| Action | Slots | Example | Proposed | Answer | How checked | By, date |',
             '|---|---|---|---|---|---|---|']
    for group in actions:
        example = group['slots'][0]
        names = ', '.join(sorted({s['control'] for s in group['slots']}))
        lines.append(f"| {group['action']} | {len(group['slots'])} ({names}) | {example['element']}.{example['control']} | "
                     f"{proposed(group.get('proposal'))} | | | |")
    lines += ['', '## Runtime questions', '', '| # | Question | Proposed | Answer | How checked | By, date |',
              '|---|---|---|---|---|---|']
    lines += [f'| Q-{n:02d} | {q.replace("|", "/")} | {proposed(p)} | | | |' for n, (q, p) in enumerate(questions, 1)]
    return '\n'.join(lines) + '\n'


def refresh_proposals(kept, fresh):
    """Update the Proposed cell of unanswered lines from a fresh sheet; answers and everything else stay as written."""
    cells = lambda line: [c.strip() for c in line.strip().strip('|').split('|')]
    proposals = {}
    for line in fresh.splitlines():
        if line.startswith(('| A-', '| Q-')):
            row = cells(line)
            proposals[row[0]] = row[3] if line.startswith('| A-') else row[2]
    out, column, changed = [], None, False
    for line in kept.splitlines():
        row = cells(line)
        if 'Proposed' in row and 'Answer' in row:
            column = (row.index('Proposed'), row.index('Answer'))
        elif column and line.startswith(('| A-', '| Q-')) and len(row) > column[1] and not row[column[1]] \
                and row[0] in proposals:
            if row[column[0]] != proposals[row[0]]:
                row[column[0]] = proposals[row[0]]
                line, changed = '| ' + ' | '.join(row) + ' |', True
        out.append(line)
    return '\n'.join(out) + '\n' if changed else kept  # unchanged: byte for byte


def markdown(rows, gaps, used, questions, actions=()):
    lines = ['# Evidence report', '', '## 1. Coverage', '',
             '| Element | Kind | Code blocks | Encoded actions | Controls | Dossier | Described | Captions | Image | Dialogs | SQL | Items |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        cell = lambda key: ('✅' if r[key] is True else '❌' if r[key] is False else r[key]) if key in r else ''
        lines.append(f"| {r['element']} | {r['kind']} | {cell('code_blocks')} | {cell('encoded_actions')} | {cell('controls')} | {cell('dossier')} | "
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
              'Only someone using the running application can confirm these; until then the work uses the proposal.', '']
    lines += [f'- [ ] Q-{n:02d} {q}\n  - proposed: {p["answer"]} ({p["basis"]})' for n, (q, p) in enumerate(questions, 1)]
    total = sum(len(a['slots']) for a in actions)
    lines += ['', f'## 4. Encoded actions ({len(actions)} distinct, {total} slots)', '',
              'Event slots whose predefined action WINDEV keeps encoded, with no code or next to code (the action may run '
              'besides the code). Slots with the same action ID hold the '
              'same encoded value, hence the same action: one answer per group (from the control\'s Actions tab in WINDEV, '
              'or by using it in the app) settles every slot in it. Largest groups first.', '']
    for group in actions:
        names = sorted({s['control'] for s in group['slots']})
        captions = sorted({s['caption'] for s in group['slots'] if s['caption']})
        types = sorted({s['button_type'] for s in group['slots'] if s['button_type']})
        example = group['slots'][0]
        with_code = sum(1 for s in group['slots'] if s.get('has_code'))
        lines.append(f"- [ ] `{group['action']}` × {len(group['slots'])}{f' ({with_code} next to code)' if with_code else ''} "
                     f"(event {example['event']}): "
                     f"{', '.join(names[:6])}{'…' if len(names) > 6 else ''}"
                     + (f"; captions {', '.join(repr(c) for c in captions[:4])}" if captions else '')
                     + (f"; button type {', '.join(types)}" if types else '')
                     + f" — e.g. {example['element']}.{example['control']} ({example['evidence']}). What does it do?"
                     + (f"\n  - proposed: {group['proposal']['answer']} ({group['proposal']['basis']})" if group.get('proposal') else ''))
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inspect_dir', type=Path, help='inspect_windev.py output')
    parser.add_argument('--dossier', type=Path, help='dossier_extract.py output')
    parser.add_argument('--out', type=Path, required=True, help='Markdown report (a .json sibling is written too)')
    parser.add_argument('--compiled', type=Path, help='event_legend.py JSON (docs/mapping/event-codes.json), for '
                                                        'references found in the compile folder')
    parser.add_argument('--language', help="the application's language for dialog texts (default: each text's first)")
    args = parser.parse_args()
    inventory = load_json(args.inspect_dir / 'inventory.json')
    tables = set()
    for path in Path(args.inspect_dir, 'schema').rglob('*.json'):
        tables |= {t['attributes'].get('Nom') or t['attributes'].get('Name', '') for t in load_json(path)['tables']}
    rows, gaps = coverage(args.inspect_dir, args.dossier, tables)
    used = calls(args.inspect_dir)
    caller_index = callers(used)
    # Key the JSON by each element's real name, not by the spelling of its first call site.
    known = {row['element'].lower(): row['element'] for row in rows}
    caller_index = CaseInsensitive({known.get(name.lower(), name): sites for name, sites in caller_index.items()})
    first = first_window(args.dossier)
    legend = load_json(args.compiled) if args.compiled else {}
    compiled = legend.get('compiled_references', {})
    uncalled = collections.defaultdict(list)
    for row in rows:
        if row['kind'] in ('window', 'report') and not caller_index.get(row['element']) and row['element'] != first:
            # The compiled code of another element naming it: a predefined action (e.g. a Print button) or a
            # dynamic call. Evidence of who reaches it, not of how.
            named_by = sorted(k for k, refs in compiled.items() if row['element'] in refs)
            if named_by:
                for window in named_by:
                    uncalled[window].append(row['element'])
                caller_index[row['element']] = [f'{k} (named in its compiled code: predefined action or dynamic call)'
                                                for k in named_by]
                gaps.append(f"{row['element']}: no call in code; named in the compiled code of {', '.join(named_by)} "
                            '(a predefined button action there is the likely caller — see encoded actions)')
            else:
                gaps.append(f"{row['element']}: no caller found in code (a predefined button action — see encoded "
                            "actions —, dynamic, unreachable, or the project's first window)")
    # An embedded report query reached only from one window that browses one file: propose what that table shows.
    windows, _, _, _ = dossier_items(args.dossier)
    for window, reports in uncalled.items():
        tables = [c for c in (windows.get(window) or {}).get('controls', {}).values()
                  if c.get('kind') == 'Table' and c.get('browsed_file')]
        for index, gap in enumerate(gaps):
            report = gap.split(':', 1)[0]
            if report in reports and 'embedded query' in gap and len(tables) == 1:
                file, item = tables[0]['browsed_file'], tables[0].get('browsed_item')
                order = f', by {item}' if item else ''
                gaps[index] = (f'{gap} — proposed: every record of {file}, no condition, in the order of the table '
                               f'that prints it ({window}{order}); confirm on a legacy printout')
    actions = propose_actions(encoded_actions(args.inspect_dir, args.dossier, args.language), args.inspect_dir,
                              CaseInsensitive(uncalled), bool(used.get('iPreview')))
    questions = runtime_questions(args.inspect_dir, args.dossier, args.language, actions,
                                  legend.get('skinned_dialogs', ()))
    args.out.with_name('navigation.md').write_text(navigation(caller_index, rows, first), encoding='utf-8')
    sheet = args.out.parent / 'evidence' / 'encoded-actions.md'
    if not sheet.exists():  # written once: it holds the human's answers afterwards, never regenerated over them
        sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.write_text(answer_sheet(actions, questions), encoding='utf-8')
    else:
        sheet.write_text(refresh_proposals(sheet.read_text(encoding='utf-8'), answer_sheet(actions, questions)),
                         encoding='utf-8')
    args.out.write_text(markdown(rows, gaps, used, questions, actions), encoding='utf-8')
    args.out.with_suffix('.json').write_text(json.dumps(
        {'files': len(inventory['files']), 'coverage': rows, 'gaps': gaps,
         'questions': [{'id': f'Q-{n:02d}', 'question': q, 'proposal': p} for n, (q, p) in enumerate(questions, 1)],
         'callers': caller_index,
         'encoded_actions': actions,
         'usage': {f: [list(s) for s in sites] for f, sites in used.items()}}, indent=1, ensure_ascii=False),
        encoding='utf-8')
    print(f'{len(rows)} elements, {len(gaps)} gaps, {len(used)} platform functions used, {len(questions)} runtime questions, '
          f'{len(actions)} distinct encoded actions on {sum(len(a["slots"]) for a in actions)} slots '
          f'({sum(1 for a in actions for s in a["slots"] if not s.get("has_code"))} without code)')


if __name__ == '__main__':
    main()
