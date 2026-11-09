#!/usr/bin/env python3
"""Learn where each designer property sits in decoded `internal_properties`, apply it, and list what stays unexplained.

Replacing every string of a property chunk by one zero byte gives the layout an all-empty element would have: byte N
then means the same thing in every element of a kind, counted from the right anchor (the start, the end, or for a
window control the start and the end of the block all controls share).

  learn   compare those bytes, position by position, with what a dossier extract says about the same elements (any
          subset of windows is enough) and keep the positions that explain a property for every element. Each
          property is then tested on windows it was not learned from: only those that predict them without an error
          are `strong`
  audit   list, per element, the bytes that differ from the usual value of its kind and that no property explains:
          what a migration has not looked at yet

  python3 scripts/windev_fieldmap.py learn legacy/<project> --dossier <dossier dir> --out fieldmap.json
  python3 scripts/windev_fieldmap.py audit legacy/<project> [--map fieldmap.json] --out audit.json

`windev_decode.py` applies a field map (`--fieldmap`, default: `windev_fieldmap.json` beside the scripts) to every
element. A learned position is evidence by agreement, not by definition: an entry records how many elements agreed,
how many values were seen and its held-out score. Use `strong` entries; confirm `weak` ones on the running
application or by changing the property on a copy of one window. An enumeration value never seen while learning is
reported as `unknown:<bytes>`, not guessed.
"""
import argparse
import collections
import json
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import windev_decode as decoder  # noqa: E402

DEFAULT_MAP = Path(__file__).with_name('windev_fieldmap.json')
# Dossier properties that are free text of the application: matched to string slots, never kept as enumerations.
TEXT_ONLY = re.compile(r'caption|title|image|file|item|mask|content|tooltip|note|menu|link|group|hint|message|format|'
                       r'path|name|text|value|style|font', re.I)
# What the decoder already reads exactly, and the dossier lines that restate it.
ALREADY = re.compile(r'^(x|y|width|height|caption|tab_order|state|button_type|kind|path|decoded|pane|plane|image|'
                     r'background_image|title|'
                     r'line:(Caption|Tab order|Anchor|Title|Image|Background image|Link between data|Group|Plane|'
                     r'TAB Key|Nb\. background states)\b.*|flag:(Visible|TAB Key))$')
MAX_LABELS = 16
FRAMES = ('start', 'end', 'block', 'after')


def normalise(data):
    """(bytes with each framed string replaced by one zero byte, {position: string bytes}, original->new offset)."""
    out, slots, position, cuts = bytearray(), {}, 0, []
    for match in decoder.FRAMED.finditer(data):
        out += data[position:match.start()]
        slots[len(out)] = match[2]
        out.append(0)
        position = match.end()
        cuts.append((match.end(), match.end() - match.start() - 1))
    out += data[position:]
    return bytes(out), slots, lambda offset: offset - sum(lost for end, lost in cuts if end <= offset)


def variant(suffix, owner, kind, chunk):
    kind = kind if owner in ('controls', 'columns') else ''
    return f"{suffix.lstrip('.')}/{owner}/{kind}/{chunk['id']}.{chunk['version']}"


def sample_of(unit, suffix, slot, chunk, fields, encoding='cp1252'):
    data, slots, moved = normalise(chunk['data'])
    anchors = {'start': 0, 'end': len(data)}
    if slot['owner'] == 'controls' and chunk['id'] == 0:
        match = decoder.COMMON.search(chunk['data'])
        if match:
            anchors['block'] = moved(match.start() + 4)
            if fields.get('_end'):
                anchors['after'] = moved(fields['_end'])
    parsed = set()
    spans = decoder.fonts(chunk['data'], encoding)[1] + (list(fields.get('_spans') or []) if chunk['id'] == 0 else [])
    if chunk['id'] == 15 and 'x_mm' in fields:
        try:        # a report band or control: its name, 8 bytes, then the four doubles of its geometry
            spans.append((decoder.framed_string(chunk['data'], 0, encoding)[1] + 8, 32))
        except (ValueError, IndexError, struct.error):
            pass
    for offset, width in spans:
        parsed.update(range(moved(offset), moved(offset) + width))
    return {'parsed': parsed, 'unit': unit, 'name': slot['name'], 'owner': slot['owner'], 'line': slot['line'],
            'variant': variant(suffix, slot['owner'], slot['type'], chunk), 'length': len(data), 'data': data,
            'anchors': anchors, 'fields': fields if chunk['id'] in (0, 15) else {},
            'slots': {pos: decoder.text(value, encoding) for pos, value in slots.items()}}


def collect(project, encoding='cp1252'):
    """Every chunk of every element of a project's window and report sources, normalised."""
    samples = []
    for path in sorted(Path(project).rglob('*')):
        if path.suffix.lower() not in ('.wdw', '.wde') or not path.is_file() or '.cpl' in path.as_posix().lower():
            continue
        source = decoder.read_text(path.read_bytes())
        if not source or 'internal_properties' not in source:
            continue
        for slot in decoder.property_slots(source):
            try:
                chunks = decoder.decode_properties(slot['value'])
            except (ValueError, IndexError, struct.error, KeyError):
                continue
            fields = decoder.describe(slot['owner'], slot['type'], chunks, encoding, keep_end=True) or {}
            samples += [sample_of(path.stem, path.suffix.lower(), slot, chunk, fields, encoding) for chunk in chunks]
    return samples


# ---------------------------------------------------------------- what the dossier says

def continuations(groups):
    """{leading words: the words seen after them} over the detail lines of every element of one kind."""
    following = collections.defaultdict(set)
    for lines in groups:
        for line in lines:
            words = line.split(' ')
            for cut in range(1, len(words)):
                following[' '.join(words[:cut])].add(words[cut])
    return following


def split_lines(groups, following):
    """Dossier detail lines are "Key value" without a separator. The key is the longest leading run of words (none
    of them a number) that is followed by at least two different words across the elements of a kind: so
    "Horz. scrollbar", not "Horz."."""
    result = []
    for lines in groups:
        properties = {}
        for line in lines:
            words = line.split(' ')
            limit = next((i for i, word in enumerate(words) if re.fullmatch(r'-?\d+([.,]\d+)?', word)), len(words))
            cut = next((c for c in range(min(limit, len(words) - 1), 0, -1)
                        if len(following[' '.join(words[:c])]) >= 2), None)
            if cut:
                properties[' '.join(words[:cut])] = ' '.join(words[cut:])
        result.append(properties)
    return result


def dossier_truth(dossier):
    """{(unit lower, control lower): {property: value}} from a dossier extract: named fields, flags and detail lines."""
    truth = {}
    windows = {path: json.loads(path.read_text(encoding='utf-8')).get('controls') or {}
               for path in sorted(Path(dossier, 'windev-window').glob('*.json'))}
    raw_by_kind = collections.defaultdict(list)
    for controls in windows.values():
        for control in controls.values():
            raw_by_kind[control.get('kind')].append(control.get('raw') or [])
    following = {kind: continuations(groups) for kind, groups in raw_by_kind.items()}
    for path, controls in windows.items():
        by_kind = collections.defaultdict(list)
        for name, control in controls.items():
            by_kind[control.get('kind')].append(name)
        for kind, names in by_kind.items():
            for name, lines in zip(names, split_lines([controls[n].get('raw') or [] for n in names], following[kind])):
                properties = {f'line:{key}': value for key, value in lines.items()}
                for key, value in controls[name].items():
                    if key == 'flags':
                        properties.update({f'flag:{flag}': bool(state) for flag, state in (value or {}).items()})
                    elif key not in ('raw', 'row') and isinstance(value, (str, int, bool)):
                        properties[key] = value
                    elif isinstance(value, dict) and value and all(isinstance(v, str) for v in value.values()):
                        properties[key] = next(iter(value.values()))
                truth[path.stem.lower(), name.lower()] = {k: v for k, v in properties.items() if not ALREADY.match(k)}
    return truth


# ---------------------------------------------------------------- learning

def squeeze(value):
    return re.sub(r'[\s\x80-\U0010ffff]+', '', str(value))


def number(raw):
    return int.from_bytes(raw, 'little', signed=len(raw) == 4 and raw[3] >= 0x80)


def candidates(rows):
    """(position, width) worth testing: where bytes differ between the rows."""
    length = len(rows[0])
    varying = [any(row[i] != rows[0][i] for row in rows) for i in range(length)]
    found = []
    for i in range(length):
        if varying[i]:
            found.append((i, 1))
            if i == 0 or not varying[i - 1]:
                found += [(i, width) for width in (2, 4) if i + width <= length]
    return found


def learn_group(rows, slots, truths):
    """One aligned group of chunks: {property: entry} for the properties one position explains for every member."""
    learned = {}
    if not rows or not rows[0]:
        return learned
    spots = candidates(rows)
    names = collections.Counter(key for truth in truths for key in truth)
    for name, count in names.items():
        have = [i for i, truth in enumerate(truths) if name in truth]
        values = [truths[i][name] for i in have]
        distinct = collections.Counter(map(str, values))
        if count < 4 or len(distinct) < 2:
            continue
        # Free text: the string slot holding it.
        texts = [i for i, v in zip(have, values) if isinstance(v, str) and v]
        slot_hits = collections.Counter()
        for i in texts:
            for position, value in slots[i].items():
                if squeeze(value) and squeeze(value) == squeeze(truths[i][name]):
                    slot_hits[position] += 1
        if slot_hits:
            position, hits = slot_hits.most_common(1)[0]
            wrong = sum(1 for i in texts if position in slots[i] and squeeze(slots[i][position]) != squeeze(truths[i][name]))
            if hits >= 3 and not wrong and len({squeeze(truths[i][name]) for i in texts}) >= 2:
                learned[name] = {'kind': 'string', 'position': position, 'samples': hits}
                continue
        if TEXT_ONLY.search(name) and not name.startswith('flag:'):
            continue
        fits = []
        for position, width in spots:
            table, back = {}, {}
            for i, value in zip(have, values):
                raw = rows[i][position:position + width]
                if table.setdefault(raw, str(value)) != str(value) or back.setdefault(str(value), raw) != raw:
                    break
            else:
                if len(table) >= 2:
                    shifts = {int(label) - number(raw) for raw, label in table.items()} \
                        if all(re.fullmatch(r'-?\d+', label) for label in table.values()) else set()
                    fits.append((len(shifts) == 1, width, position, table, next(iter(shifts)) if len(shifts) == 1 else 0))
        if not fits:
            continue
        places = {position for _, _, position, _, _ in fits}
        numeric, width, position, table, shift = max(fits, key=lambda fit: (fit[0], fit[1]))
        if not numeric and len(table) > MAX_LABELS:
            continue
        entry = {'kind': 'number' if numeric else 'enum', 'position': position, 'width': width, 'samples': count,
                 'distinct': len(table), 'minority': sorted(distinct.values())[-2],
                 'alternatives': len({p for p in places if not position <= p < position + width})}
        if numeric and shift:
            entry['add'] = shift
        if not numeric:
            entry['values'] = {raw.hex(): label for raw, label in sorted(table.items())}
        learned[name] = entry
    return learned


def framed_view(members, frame):
    """The members that have this anchor, cut to the bytes all of them have around it; positions count from the
    anchor."""
    having = [m for m in members if frame in m[0]['anchors']]
    if len(having) < 4:
        return None
    before = min(sample['anchors'][frame] for sample, _ in having)
    after = min(sample['length'] - sample['anchors'][frame] for sample, _ in having)
    rows, slots = [], []
    for sample, _ in having:
        anchor = sample['anchors'][frame]
        rows.append(sample['data'][anchor - before:anchor + after])
        slots.append({pos - anchor + before: value for pos, value in sample['slots'].items()
                      if anchor - before <= pos < anchor + after})
    return rows, slots, [known for _, known in having], before


def known_of(sample, truth):
    known = dict(truth.get((sample['unit'].lower(), sample['name'].lower()), {})) \
        if sample['owner'] in ('controls', 'columns') else {}
    for key, value in sample['fields'].items():
        # Numbers and the two fixed lists only: an application's own texts must never end up in a field map.
        if (isinstance(value, (int, bool)) or key in ('state', 'button_type')) and not key.startswith('_') \
                and key not in ('window_x', 'window_y'):
            known[f'field:{key}'] = value
    return known


def learn(samples, truth):
    """The field map: {variant: {frame: {property: entry}}}, positions relative to the frame's anchor. A property is
    kept in the frame where most elements agreed; the decoder's own fields are learned too (prefix `field:`), which
    marks where they sit."""
    groups = collections.defaultdict(list)
    for sample in samples:
        known = known_of(sample, truth)
        if known:
            groups[sample['variant']].append((sample, known))
    result = {}
    for name, members in sorted(groups.items()):
        best = {}
        for frame in FRAMES:
            view = framed_view(members, frame)
            if not view:
                continue
            rows, slots, truths, before = view
            for prop, entry in learn_group(rows, slots, truths).items():
                entry['position'] -= before
                if prop not in best or entry['samples'] > best[prop][1]['samples']:
                    best[prop] = (frame, entry)
        frames = collections.defaultdict(dict)
        for prop, (frame, entry) in sorted(best.items()):
            frames[frame][prop] = entry
        if frames:
            result[name] = dict(frames)
    return result


# ---------------------------------------------------------------- applying

def entries_for(fieldmap, sample):
    """The entries that apply to one chunk, positions resolved to it: {property: entry}."""
    chosen = {}
    for frame, learned in (fieldmap.get(sample['variant']) or {}).items():
        if frame not in sample['anchors']:
            continue
        for prop, entry in learned.items():
            position = entry['position'] + sample['anchors'][frame]
            if 0 <= position and position + entry.get('width', 1) <= sample['length']:
                chosen[prop] = {**entry, 'position': position}
    return chosen


def read(entry, sample):
    if entry['kind'] == 'string':
        return sample['slots'].get(entry['position'], '')
    raw = sample['data'][entry['position']:entry['position'] + entry['width']]
    if entry['kind'] == 'number':
        return number(raw) + entry.get('add', 0)
    return entry['values'].get(raw.hex(), f'unknown:{raw.hex()}')


def apply(fieldmap, sample, weak=False):
    """Named properties of one chunk: {property: value} from `strong` entries (`weak` ones too when asked);
    `field:` entries are left out."""
    return {prop: read(entry, sample) for prop, entry in entries_for(fieldmap, sample).items()
            if not prop.startswith('field:') and (weak or entry.get('confidence') == 'strong')}


def same(expected, value):
    if isinstance(expected, bool):
        return str(expected) == str(value)
    return squeeze(expected) == squeeze(value)


def cross_validate(samples, truth, folds=4):
    """Learn on some windows, predict the others, for every fold: {(variant, property): [predictions, correct]}.
    This is what tells a real position from one that only fits by coincidence."""
    units = sorted({sample['unit'] for sample in samples})
    scores = collections.defaultdict(lambda: [0, 0])
    for fold in range(folds):
        held = set(units[fold::folds])
        fieldmap = learn([s for s in samples if s['unit'] not in held], truth)
        for sample in samples:
            if sample['unit'] not in held:
                continue
            known = known_of(sample, truth)
            for prop, entry in entries_for(fieldmap, sample).items():
                if prop in known and not prop.startswith('field:'):
                    value = read(entry, sample)
                    if entry['kind'] == 'string' and not value and not known[prop]:
                        continue
                    if isinstance(value, str) and value.startswith('unknown:'):
                        continue    # a value this round never saw: it abstains (as when applied), it is not wrong
                    scores[sample['variant'], prop][0] += 1
                    scores[sample['variant'], prop][1] += same(known[prop], value) or (
                        entry['kind'] == 'string' and value == '' and str(known[prop]).strip() == '0')
    return scores


def learn_validated(samples, truth, folds=4, needed=8):
    """The field map with a confidence per entry: `strong` when the held-out windows gave at least `needed`
    predictions and none was wrong."""
    fieldmap = learn(samples, truth)
    scores = cross_validate(samples, truth, folds)
    for name, frames in fieldmap.items():
        for learned in frames.values():
            for prop, entry in learned.items():
                predictions, correct = scores.get((name, prop), (0, 0))
                entry['held_out'] = f'{correct}/{predictions}'
                # Held-out windows share the project's habits: two values that always go together still fit. So a
                # position must also be the only one that fits, and a yes/no property needs several of each.
                solid = entry['kind'] == 'string' or (not entry['alternatives']
                                                      and entry['minority'] >= 3)
                entry['confidence'] = 'strong' if predictions >= needed and correct == predictions and solid else 'weak'
    return fieldmap


def audit(samples, fieldmap):
    """Per element, the bytes that differ from the most common value of its variant and that nothing explains.

    Positions where most elements differ from each other are identifiers or stamps, not properties: counted per
    variant, not listed per element. Returns (per-variant summary, per-element findings)."""
    groups = collections.defaultdict(list)
    for sample in samples:
        groups[sample['variant'], sample['length']].append(sample)
    summary, findings = {}, []
    for (name, length), members in sorted(groups.items()):
        modes, identifiers = [], set()
        for position in range(length):
            counts = collections.Counter(sample['data'][position] for sample in members)
            modes.append(counts.most_common(1)[0][0])
            if len(members) >= 8 and len(counts) > max(8, len(members) // 4):
                identifiers.add(position)
        unexplained_total = clean = named = 0
        for sample in members:
            entries = entries_for(fieldmap, sample)
            named = max(named, sum(not p.startswith('field:') for p in entries))
            explained = set(sample['slots']) | sample['parsed']
            for entry in entries.values():
                explained.update(range(entry['position'], entry['position'] + entry.get('width', 1)))
            runs, run = [], None
            for position in range(length):
                differs = sample['data'][position] != modes[position] and position not in explained \
                    and position not in identifiers
                if differs and run and position - run[1] <= 1:
                    run[1] = position
                elif differs:
                    run = [position, position]
                    runs.append(run)
            if not runs:
                clean += 1
                continue
            unexplained_total += len(runs)
            findings.append({'unit': sample['unit'], 'name': sample['name'], 'line': sample['line'], 'variant': name,
                             'length': length,
                             'differences': [{'position': start, 'value': sample['data'][start:end + 1].hex(),
                                              'usual': bytes(modes[start:end + 1]).hex()} for start, end in runs[:40]]})
        summary[f'{name}@{length}'] = {'elements': len(members), 'without_unexplained_difference': clean,
                                       'unexplained_runs': unexplained_total, 'named_properties': named,
                                       'identifier_bytes': len(identifiers)}
    return summary, findings


def merge_maps(base, learned):
    """A project's own map over a base one: each property comes from the project when it is `strong` there, from the
    base when only the base is."""
    merged = json.loads(json.dumps(base))
    for name, frames in learned.items():
        for frame, entries in frames.items():
            for prop, entry in entries.items():
                elsewhere = [f for f, props in merged.get(name, {}).items() if prop in props]
                if entry['confidence'] == 'strong' or not elsewhere or prop.startswith('field:'):
                    for other in elsewhere:
                        del merged[name][other][prop]
                    merged.setdefault(name, {}).setdefault(frame, {})[prop] = entry
    return merged


def shareable(fieldmap):
    """What may leave the project: `strong` entries and the decoder's own fields. Weak enumerations can hold words
    of the application; none are kept."""
    kept = {}
    for name, frames in fieldmap.items():
        for frame, entries in frames.items():
            for prop, entry in entries.items():
                if prop.startswith('field:'):
                    # Only where the decoder's field sits (for the audit): its values are not needed.
                    entry = {key: value for key, value in entry.items() if key != 'values'}
                    entry['kind'] = 'position'
                elif entry['confidence'] != 'strong':
                    continue
                kept.setdefault(name, {}).setdefault(frame, {})[prop] = entry
    return kept


def load_map(path=None):
    path = Path(path) if path else DEFAULT_MAP
    return json.loads(path.read_text(encoding='utf-8'))['variants'] if path.exists() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    learner = commands.add_parser('learn', help='learn property positions from a dossier extract')
    learner.add_argument('project', type=Path)
    learner.add_argument('--dossier', type=Path, required=True)
    learner.add_argument('--out', type=Path, required=True)
    learner.add_argument('--folds', type=int, default=4, help='held-out rounds (default 4)')
    learner.add_argument('--base', type=Path, default=DEFAULT_MAP,
                         help='a field map to complete: its strong entries stay where this project proves nothing')
    learner.add_argument('--shareable', action='store_true',
                         help='keep strong entries only (no word of the application can remain)')
    auditor = commands.add_parser('audit', help='list differences from the usual values that no property explains')
    auditor.add_argument('project', type=Path)
    auditor.add_argument('--map', type=Path, default=DEFAULT_MAP)
    auditor.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    samples = collect(args.project)
    if args.command == 'learn':
        fieldmap = learn_validated(samples, dossier_truth(args.dossier), args.folds)
        if args.shareable:
            fieldmap = shareable(fieldmap)
        else:
            fieldmap = merge_maps(load_map(args.base), fieldmap)
        args.out.write_text(json.dumps({'format_version': 1, 'variants': fieldmap}, indent=1, ensure_ascii=False),
                            encoding='utf-8')
        entries = [e for frames in fieldmap.values() for props in frames.values() for n, e in props.items()
                   if not n.startswith('field:')]
        print(json.dumps({'variants': len(fieldmap), 'properties': len(entries),
                          'strong': sum(e['confidence'] == 'strong' for e in entries)}))
    else:
        summary, findings = audit(samples, load_map(args.map))
        args.out.write_text(json.dumps({'summary': summary, 'elements': findings}, indent=1), encoding='utf-8')
        print(json.dumps({'chunks': sum(v['elements'] for v in summary.values()),
                          'without_unexplained_difference': sum(v['without_unexplained_difference'] for v in summary.values())}))


if __name__ == '__main__':
    main()
