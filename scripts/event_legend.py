#!/usr/bin/env python3
"""Derive WINDEV event-code meanings (and embedded report query items) from the project's compile folder.

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


QUERY_STRING = re.compile(rb'(?:[\x20-\x7e]|[\xc2-\xf4][\x80-\xbf]+){3,}')


def names_in(data, name):
    """The whole name (not a prefix of a longer one: WIN_Data is not WIN_Data_Inicio) in ASCII or UTF-16."""
    ascii_name = re.compile(rb'(?<![\w])' + re.escape(name.encode()) + rb'(?![\w])')
    wide = re.compile(rb'(?<![\w]\x00)' + re.escape(name.encode('utf-16-le')) + rb'(?![\w]\x00)')
    return bool(ascii_name.search(data) or wide.search(data))


def report_queries(compile_dir):
    """{report: [{'item', 'caption'}]}: the items an embedded report query selects, from the compiled report
    (`.wbe`). The dossier does not print embedded queries; their compiled form keeps item names and captions
    as plain strings after `<REPORT>$Query`. Selection conditions and sort are not there."""
    queries = {}
    for path in sorted(Path(compile_dir).rglob('*.wbe')):
        data = path.read_bytes()
        start = data.find(b'$Query')
        if start < 0:
            continue
        strings = [s.decode('utf-8', 'replace') for s in QUERY_STRING.findall(data[start + 6:start + 6000])]
        strings = [s for s in strings if re.match(r'[^\W\d]', s)]  # drop binary noise such as "}|D"
        items = []
        while len(strings) >= 2 and re.fullmatch(r'[A-Za-z_]\w*', strings[0]):
            items.append({'item': strings[0], 'caption': strings[1]})
            strings = strings[2:]
        if items:
            queries[path.name.split('.')[0]] = items
    return queries


def legend(source_dir, compile_dir):
    inspector = load_inspector()
    compiled = {}
    # Compiled code: windows in .wcw, reports in .wce.
    for pattern in ('*.wcw', '*.wce'):
        for path in Path(compile_dir).rglob(pattern):
            compiled.setdefault(path.name.split('.')[0].lower(), path)
    votes = collections.defaultdict(collections.Counter)
    references = {}  # element -> other elements its compiled code names (opened, printed, called)
    observations = []  # (raw codes, compiled labels) per control, for the elimination passes
    procedures = collections.Counter()  # slot types of local procedures, proven by their PROCEDURE line
    windows = 0
    sources = sorted(Path(source_dir).glob('*.[wW][dD][wW]')) + sorted(Path(source_dir).glob('*.[wW][dD][eE]'))
    queries = sorted(Path(source_dir).glob('*.[wW][dD][rR]'))
    element_names = {p.stem for p in sources + queries}
    for source in sources:
        wcw = compiled.get(source.stem.lower())
        text = inspector.decode_text(source.read_bytes())
        if wcw is None or text is None:
            continue
        windows += 1
        data = wcw.read_bytes()
        labels = compiled_labels(data)
        references[source.stem] = {name for name in element_names if name.lower() != source.stem.lower()
                                   and names_in(data, name)}
        events = collections.defaultdict(set)
        own = {source.stem.lower(), inspector.element_name(text, source.stem).lower(), 'mywindow', 'mafenêtre',
               'mafenetre', 'myreport', 'monetat'}
        for block in inspector.extract_blocks(text):
            declared = [p.lower() for p in block['procedures']]
            code = block['context']['siblings'].get('type') or 'none'
            if declared and declared[0] not in own:
                # A local procedure: its PROCEDURE line in the source proves what the slot type is.
                if code != 'none':
                    procedures[code] += 1
                continue
            names = block['context']['names']
            events[names[-1] if names else source.stem].add(code)
        for control, codes in events.items():
            named = set(labels.get(control, set()))
            codes = set(codes)
            # The block without a raw code is the declarations block (it holds PROCEDURE <window>()).
            if 'none' in codes and 'Global declarations' in named:
                votes['none']['Global declarations'] += 1
            codes.discard('none')
            named.discard('Global declarations')
            # A control whose only coded event and only compiled label are its initialization names that code.
            if named == {'Initialization'} and len(codes) == 1:
                votes[next(iter(codes))]['Initialization'] += 1
            observations.append((codes, named))
    # Every control is labelled "Initialization" whether or not it has code, so that label pairs only as above.
    # Then pair one-to-one, repeatedly removing the codes already named and their labels from each control:
    # "Click" known for 18 leaves {2} and {Closing} on a window coded for both.
    known = {}
    while True:
        known.update({code: counter.most_common(1)[0][0] for code, counter in votes.items()})
        found = collections.defaultdict(collections.Counter)
        for codes, named in observations:
            left_codes = {c for c in codes if c not in known}
            left_labels = named - set(known.values()) - {'Initialization'}
            if len(left_codes) == 1 and len(left_labels) == 1:
                found[next(iter(left_codes))][next(iter(left_labels))] += 1
        if not found:
            break
        for code, counter in found.items():
            votes[code].update(counter)
    for code, count in procedures.items():
        votes[code]['Local procedure'] += count  # after pairing, so a conflict shows instead of hiding a code
    result = {}
    for code, counter in sorted(votes.items(), key=lambda item: -sum(item[1].values())):
        (best, count), total = counter.most_common(1)[0], sum(counter.values())
        result[code] = {'event': best, 'evidence': count, 'conflicts': {k: v for k, v in counter.items() if k != best}}
    return {'windows': windows, 'codes': result, 'report_queries': report_queries(compile_dir),
            'compiled_references': {k: sorted(v) for k, v in sorted(references.items()) if v},
            # The project customizes WINDEV's message and dialog boxes: they follow the skin template.
            'skinned_dialogs': sorted({f.name.split('.')[0] for f in Path(compile_dir).rglob('WINDEV*BOX.*.wdw.*')})}


def markdown(data):
    lines = ['# Event codes (derived from the compile folder)', '',
             f"Evidence from {data['windows']} elements (windows and reports): compiled event labels paired with raw codes of the text "
             'sources where unambiguous. Codes without evidence stay `inferred` until confirmed.', '',
             '| Code | Event | Evidence | Conflicts |', '|---|---|---|---|']
    for code, item in data['codes'].items():
        conflicts = ', '.join(f'{k} ({v})' for k, v in item['conflicts'].items()) or '—'
        lines.append(f"| {code} | {item['event']} | {item['evidence']} | {conflicts} |")
    if data.get('report_queries'):
        lines += ['', '## Embedded report queries (items selected, from the compiled reports)', '',
                  'Item names and captions only: selection conditions and sort are not in the compiled file.', '']
        lines += [f"- **{report}**: " + ', '.join(f"`{i['item']}` ({i['caption']})" for i in items)
                  for report, items in data['report_queries'].items()]
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
