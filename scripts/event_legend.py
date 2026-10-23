#!/usr/bin/env python3
"""Derive WINDEV event-code meanings from the project's own compile folder (evidence, not guesses).

The compiled per-window files (`<project>.cpl/**/<WINDOW>.<hash>.wdw.wcw`) contain the event label
of every coded event ("Click BTN_Save", "Exit from EDT_Name", "End of initialization of WIN_X").
Pairing them with the raw event codes of the text sources gives a legend backed by the compiler.
Only unambiguous controls are counted: exactly one coded event in the source (besides
initialization) and exactly one non-initialization label in the compiled file.
"""
import argparse
import collections
import importlib.util
import json
from pathlib import Path
import re

# "Click BTN_X", "Exit from EDT_X", "Initialization of BTN_X ( SC_Parent )", "Left button down on EDT_X (WM_LBUTTONDOWN)"
LABEL = re.compile(r'^(.*?) (?:of |from |in |on )?([A-Za-z_]\w*)(?: \( .* \)| \([A-Z_]+\))?$')
UTF16 = re.compile(rb'(?:[\x20-\x7e\xc0-\xff]\x00){4,}')


def load_inspector():
    path = Path(__file__).with_name('inspect_windev.py')
    spec = importlib.util.spec_from_file_location('inspect_windev', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compiled_labels(data):
    """{control: set of event labels} from a compiled .wcw file."""
    labels = collections.defaultdict(set)
    for raw in UTF16.findall(data):
        match = LABEL.match(raw.decode('utf-16-le'))
        if match and re.match(r'^[A-Z][a-z]', match[1]) and len(match[1]) < 45:
            labels[match[2]].add(match[1])
    return labels


def legend(source_dir, compile_dir):
    inspector = load_inspector()
    compiled = {}
    # Compiled code: windows in .wcw, reports in .wce.
    for pattern in ('*.wcw', '*.wce'):
        for path in Path(compile_dir).rglob(pattern):
            compiled.setdefault(path.name.split('.')[0].lower(), path)
    votes = collections.defaultdict(collections.Counter)
    windows = 0
    sources = sorted(Path(source_dir).glob('*.[wW][dD][wW]')) + sorted(Path(source_dir).glob('*.[wW][dD][eE]'))
    for source in sources:
        wcw = compiled.get(source.stem.lower())
        text = inspector.decode_text(source.read_bytes())
        if wcw is None or text is None:
            continue
        windows += 1
        labels = compiled_labels(wcw.read_bytes())
        events = collections.defaultdict(set)
        for block in inspector.extract_blocks(text):
            declared = [p.lower() for p in block['procedures']]
            if declared and declared[0] not in (source.stem.lower(), 'mywindow', 'mafenêtre', 'mafenetre'):
                continue  # a local procedure, not an event
            names = block['context']['names']
            events[names[-1] if names else source.stem].add(block['context']['siblings'].get('type') or 'none')
        for control, codes in events.items():
            named = set(labels.get(control, set()))
            codes = set(codes)
            # The block without a raw code is the declarations block (it holds PROCEDURE <window>()).
            if 'none' in codes and 'Global declarations' in named:
                votes['none']['Global declarations'] += 1
                codes.discard('none')
            # A control whose only coded event and only compiled label are its initialization names that code.
            if named - {'Global declarations'} == {'Initialization'} and len(codes - {'none'}) == 1:
                votes[next(iter(codes - {'none'}))]['Initialization'] += 1
            named -= {'Initialization', 'Global declarations'}
            coded = codes - {'14'} if len(codes) > 1 else codes
            if len(coded) == 1 and len(named) == 1:
                votes[next(iter(coded))][next(iter(named))] += 1
    result = {}
    for code, counter in sorted(votes.items(), key=lambda item: -sum(item[1].values())):
        (best, count), total = counter.most_common(1)[0], sum(counter.values())
        result[code] = {'event': best, 'evidence': count, 'conflicts': {k: v for k, v in counter.items() if k != best}}
    return {'windows': windows, 'codes': result}


def markdown(data):
    lines = ['# Event codes (derived from the compile folder)', '',
             f"Evidence from {data['windows']} elements (windows and reports): compiled event labels paired with raw codes of the text "
             'sources where unambiguous. Codes without evidence stay `inferred` until confirmed.', '',
             '| Code | Event | Evidence | Conflicts |', '|---|---|---|---|']
    for code, item in data['codes'].items():
        conflicts = ', '.join(f'{k} ({v})' for k, v in item['conflicts'].items()) or '—'
        lines.append(f"| {code} | {item['event']} | {item['evidence']} | {conflicts} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source_dir', type=Path, help='folder with the text-format .wdw sources')
    parser.add_argument('--compile-dir', type=Path, required=True, help='the project .cpl folder')
    parser.add_argument('--out', type=Path, help='write Markdown here (e.g. docs/mapping/event-codes.md)')
    args = parser.parse_args()
    data = legend(args.source_dir, args.compile_dir)
    text = markdown(data)
    if args.out:
        args.out.write_text(text, encoding='utf-8')
        args.out.with_suffix('.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
