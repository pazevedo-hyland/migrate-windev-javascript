#!/usr/bin/env python3
"""Read HFSQL Classic data files (`.fic`, `.mmo`) directly: no ODBC driver, no WINDEV, any operating system.

The record layout comes from the project's analysis file (`<project>.ana/<project>.wda`, read by
windev_decode.py), the values from the data files. Output is what scripts/windows/export_odbc.py writes, so
data_profile.py, compare_exports.py and an importer take either:
  data.sqlite    every value as text (dates ISO 8601, decimals exact), NULL as NULL;
  <table>.csv    the same values;
  manifest.json  rows read and the file's own record count (they must agree), columns, deleted records skipped,
                 and every file that was NOT read, with the reason.

Reads a COPY of the data folder, never the live files. What it does not read is refused, not guessed: a file
whose records do not have the length the analysis gives (the file was not rebuilt after the analysis changed, or
it is compressed or encrypted), and item types this reader has not been measured on (their values are written as
`base64:` of the stored bytes and listed in the manifest). Measured against the HFSQL ODBC driver on one project:
see docs/windev-file-formats.md.

`--fit-integers` reads one kind of file the analysis no longer describes: records longer than expected, when
exactly one way of storing some integer items in a larger integer (1, 2, 4 or 8 bytes) gives the file's own record
length, and every value read that way fits the item's size in the analysis. The manifest names the items read so.

  python3 scripts/hfsql_read.py <copy of the data folder> --analysis <project>.ana/<project>.wda --out <new folder>
"""
import argparse
import base64
import csv
import datetime
import decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import windev_decode as decoder  # noqa: E402

COMPOSITE_KEY = 28
# Type code -> how the value is stored. `extra` is what the record holds beyond the analysis size (a final zero byte).
STRING, DATE, TIME, DATETIME, DURATION, DECIMAL, MEMO, BOOLEAN = 2, 14, 11, 34, 35, 41, 29, 37
TEXT_TYPES = {STRING: 1, DATE: 1, TIME: 1}
UNSIGNED = {9, 24, 26, 27, 36}
SIGNED = {5}
MEASURED = set(TEXT_TYPES) | UNSIGNED | SIGNED | {DATETIME, DURATION, DECIMAL, MEMO, BOOLEAN}
ACTIVE, DELETED, TRAILER, RECORD_HEAD, MEMO_BLOCK = 0x10, 0x80, 44, 8, 21
NO_MEMO = b'\xff' * 8


class Unreadable(Exception):
    """A data file this reader refuses: the message says why."""


def load_analysis(path):
    """The analysis as windev_decode.analysis_schema gives it, from a `.wda` or from a decoded folder."""
    path = Path(path)
    if path.is_dir():
        return json.loads((path / 'analysis.json').read_text(encoding='utf-8'))['tables']
    blocks = (decoder.analysis_schema(block) for *_, block in decoder.packed_blocks(path.read_bytes()))
    return max(blocks, key=lambda tables: sum(len(table['items']) for table in tables), default=[])


def stored_items(table):
    """Items in record order: deleted items and composite keys (kept in the index only) are not in the record."""
    items = [item for item in table['items'] if not item.get('deleted') and item['type_code'] != COMPOSITE_KEY]
    return sorted(items, key=lambda item: item['position'])


def width(item):
    return item.get('stored_size', item['size']) + TEXT_TYPES.get(item['type_code'], 0)


def widened(items, extra, limit=2000):
    """Every way to store integer items in a larger integer that adds `extra` bytes to the record:
    [{item index: stored size}]. Stops after `limit` steps (too many integer items to tell)."""
    integers = [index for index, item in enumerate(items) if item['type_code'] in UNSIGNED | SIGNED | {BOOLEAN}]
    found, steps = [], 0

    def search(position, left, chosen):
        nonlocal steps
        steps += 1
        if steps > limit:
            return
        if left == 0:
            found.append(dict(chosen))
            return
        for place in range(position, len(integers)):
            size = items[integers[place]]['size']
            for larger in (2, 4, 8):
                if larger > size and larger - size <= left:
                    search(place + 1, left - (larger - size), {**chosen, integers[place]: larger})

    search(0, extra, {})
    return [] if steps > limit else found


def record_length(items):
    """Eight bytes (state, two bytes, time of the last change, a zero), one bit per item, then the values."""
    return RECORD_HEAD + (len(items) + 7) // 8 + sum(width(item) for item in items)


def locate(data, length):
    """(offset of the first record, records, deleted records). The header's size is not read (part of it is
    enciphered): its last 44 bytes hold a counter, the record count, a zero and the deleted count, and are followed
    by one unused record slot and then the records up to the end of the file. The only position where the counts
    equal the slots that follow is taken; none means the records do not have this length."""
    found, slots = None, 0
    while True:
        start = len(data) - TRAILER - (slots + 1) * length
        if start < 0x5a:
            return found
        _, records, zero, deleted = struct.unpack('<4I', data[start:start + 16])
        if zero == 0 and records + deleted == slots and data[start + 16:start + 36] == b'\0' * 20:
            found = (start + TRAILER + length, records, deleted)
        slots += 1


def measured_lengths(data, limit=20_000_000):
    """Record lengths the file itself fits (the same test as `locate`, for every length, with every record slot
    opening on a known state byte): what to tell the reader when the analysis gives another length. Empty when the
    search would be too long or nothing fits."""
    found, work = [], 0
    for length in range(RECORD_HEAD + 2, min(65536, len(data))):
        for slots in range(1, (len(data) - TRAILER - 0x5a) // length):
            work += 1
            start = len(data) - TRAILER - (slots + 1) * length
            if data[start + 8:start + 12] != b'\0' * 4 or data[start + 16:start + 36] != b'\0' * 20:
                continue
            _, records, _, deleted = struct.unpack('<4I', data[start:start + 16])
            first = start + TRAILER + length
            if records + deleted == slots and all(data[first + n * length] in (ACTIVE, DELETED) and not data[first + n * length + 7]
                                                  for n in range(slots)):
                found.append(length)
        if work > limit:
            return []
    return found


def memo_text(memo, pointer, encoding):
    """A memo's content: the record holds the offset of a block in the `.mmo` file. A block is two bytes (the
    second ends in 4), its size twice, a byte, the offset of the next block (eight `ff` in the last one), two
    bytes, then `size` bytes. The blocks' bytes put together are 19 bytes (the content's length in the last
    four) and the content."""
    if memo is None:
        raise Unreadable('a memo item without its .mmo file')
    data, seen = b'', set()
    while True:
        if pointer in seen or pointer + MEMO_BLOCK > len(memo) or memo[pointer + 1] & 15 != 4:
            raise Unreadable(f'memo block not found at offset {pointer}')
        seen.add(pointer)
        size, used = struct.unpack('<2I', memo[pointer + 2:pointer + 10])
        if size != used or pointer + MEMO_BLOCK + size > len(memo):
            raise Unreadable(f'memo block at offset {pointer} is not whole')
        data += memo[pointer + MEMO_BLOCK:pointer + MEMO_BLOCK + size]
        if memo[pointer + 11:pointer + 19] == NO_MEMO:
            break
        pointer = int.from_bytes(memo[pointer + 11:pointer + 19], 'little')
    length = struct.unpack('<I', data[15:19])[0] if len(data) >= 19 else -1
    if length != len(data) - 19:
        raise Unreadable(f'memo of {len(data) - 19} bytes announces {length}')
    return data[19:].decode(encoding)


def iso_digits(text, pattern):
    """`yyyymmdd` or `hhmm` as ISO 8601 when it is a real date or time; the stored text otherwise (empty, zeros)."""
    try:
        if pattern == '%Y%m%d' and len(text) == 8:
            return datetime.datetime.strptime(text, pattern).date().isoformat()
        if pattern == '%H%M' and len(text) == 4:
            return datetime.datetime.strptime(text, pattern).time().isoformat()
    except ValueError:
        pass
    return text


def value(item, raw, memo, encoding):
    """One stored value as lossless text (None for an empty memo pointer)."""
    code = item['type_code']
    if code in TEXT_TYPES:
        text = raw.split(b'\0')[0].decode(encoding)
        return iso_digits(text, '%Y%m%d') if code == DATE else iso_digits(text, '%H%M') if code == TIME else text
    if code in UNSIGNED or code in SIGNED or code == BOOLEAN or code == DURATION:
        number = int.from_bytes(raw, 'little', signed=code in SIGNED or code == DURATION)
        if 'stored_size' in item and number.bit_length() > item['size'] * 8 - (code in SIGNED):
            raise Unreadable(f"{item['name']}: {number} does not fit the {item['size']} bytes the analysis gives it")
        return str(number)
    if code == DECIMAL:
        number = decimal.Decimal(int.from_bytes(raw, 'little', signed=True)).scaleb(-item['decimals'])
        return format(number.normalize(), 'f') if number else '0'
    if code == DATETIME:
        day, month, year, milliseconds = struct.unpack('<BBHI', raw)
        if not (day or month or year or milliseconds):
            return ''
        moment = datetime.datetime(year, month, day) + datetime.timedelta(milliseconds=milliseconds)
        return moment.isoformat(timespec='milliseconds')
    if code == MEMO:
        return '' if raw == NO_MEMO else memo_text(memo, int.from_bytes(raw, 'little'), encoding)
    return 'base64:' + base64.b64encode(raw).decode('ascii')


def read_table(data, table, memo=None, encoding='cp1252', fit_integers=False):
    """(items, rows, deleted records). Rows are lists of text values in record order. An item read in a larger
    integer than the analysis gives it (`fit_integers`) carries `stored_size`."""
    items = stored_items(table)
    length = record_length(items)
    if data[:4] != b'PCS\0':
        raise Unreadable('not an HFSQL Classic data file (no PCS header)')
    place = locate(data, length)
    if not place:
        real = measured_lengths(data)
        seen = f' (the file fits records of {real[0]} bytes)' if len(real) == 1 else ''
        ways = widened(items, real[0] - length) if fit_integers and len(real) == 1 and real[0] > length else []
        if len(ways) != 1:
            why = f'; {len(ways)} ways of widening its integers explain it, one is needed' if fit_integers and seen else ''
            raise Unreadable(f'its records are not the {length} bytes the analysis gives for {len(items)} items{seen}: the '
                             f'file follows another version of the analysis, or is compressed or encrypted{why}')
        items = [{**item, 'stored_size': ways[0][index]} if index in ways[0] else item for index, item in enumerate(items)]
        length = real[0]
        place = locate(data, length)
    first, records, deleted = place
    flags, rows = (len(items) + 7) // 8, []
    for slot in range(records + deleted):
        record = data[first + slot * length:first + (slot + 1) * length]
        if record[0] != ACTIVE:
            continue
        offset, row = RECORD_HEAD + flags, []
        for index, item in enumerate(items):
            raw = record[offset:offset + width(item)]
            offset += width(item)
            present = record[RECORD_HEAD + index // 8] >> (index % 8) & 1
            row.append(value(item, raw, memo, encoding) if present else None)
        rows.append(row)
    if len(rows) != records:
        raise Unreadable(f'{len(rows)} records in use, the header counts {records}')
    return items, rows, deleted


def sibling(path, suffix):
    return next((p for p in path.parent.iterdir() if p.stem == path.stem and p.suffix.lower() == suffix), None)


def export(folder, tables, out, only=None, encoding='cp1252', fit_integers=False):
    """Write data.sqlite, one CSV per table and manifest.json. Returns the manifest."""
    by_name = {table['name'].lower(): table for table in sorted(tables, key=lambda t: bool(t.get('deleted')), reverse=True)}
    manifest = {'exported': datetime.datetime.now().isoformat(timespec='seconds'), 'source': 'hfsql_read.py (direct read)',
                'encoding': encoding, 'tables': {}, 'not_read': {}}
    copy = sqlite3.connect(out / 'data.sqlite')
    for path in sorted(p for p in Path(folder).iterdir() if p.suffix.lower() == '.fic'):
        table = by_name.get(path.stem.lower())
        if only and path.stem.lower() not in only:
            continue
        if not table or table.get('deleted'):
            manifest['not_read'][path.name] = 'no data file of this name in the analysis'
            continue
        name = table['name']
        try:
            memo = sibling(path, '.mmo')
            items, rows, deleted = read_table(path.read_bytes(), table, memo.read_bytes() if memo else None, encoding,
                                              fit_integers)
        except (Unreadable, UnicodeDecodeError, ValueError, struct.error) as error:
            manifest['not_read'][path.name] = str(error)
            print(f'{name}: NOT READ — {error}')
            continue
        columns = [{'name': item['name'], 'type_code': item['type_code'], 'size': item['size'],
                    **({'scale': item['decimals']} if 'decimals' in item else {}),
                    **({'stored_size': item['stored_size']} if 'stored_size' in item else {}),
                    'nulls': sum(row[index] is None for row in rows)} for index, item in enumerate(items)]
        copy.execute(f'CREATE TABLE "{name}" (' + ', '.join(f'"{c["name"]}"' for c in columns) + ')')
        copy.executemany(f'INSERT INTO "{name}" VALUES ({", ".join("?" * len(columns))})', rows)
        digest = hashlib.sha256()
        with (out / f'{name}.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow([c['name'] for c in columns])
            for row in rows:
                line = ['' if v is None else v for v in row]
                writer.writerow(line)
                digest.update('\x1f'.join(line).encode('utf-8'))
        unmeasured = sorted({item['type_code'] for item in items} - MEASURED)
        fitted = [f"{item['name']} read in {item['stored_size']} bytes (the analysis gives {item['size']})"
                  for item in items if 'stored_size' in item]
        manifest['tables'][name] = {'rows': len(rows), 'count': len(rows), 'deleted_records': deleted, 'columns': columns,
                                    'sha256_rows': digest.hexdigest(),
                                    **({'unmeasured_type_codes': unmeasured} if unmeasured else {}),
                                    **({'assumed_layout': fitted} if fitted else {})}
        print(f'{name}: {len(rows)} rows' + (f', {deleted} deleted records skipped' if deleted else '')
              + (f' — ASSUMED: {"; ".join(fitted)}' if fitted else '')
              + (f' — type codes kept as stored bytes: {unmeasured}' if unmeasured else ''))
    copy.execute('CREATE TABLE __export (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    copy.execute("INSERT INTO __export VALUES ('manifest', ?)", (json.dumps(manifest, ensure_ascii=False),))
    copy.commit()
    copy.close()
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('folder', type=Path, help='a COPY of the folder holding the .fic and .mmo files')
    parser.add_argument('--analysis', type=Path, required=True, help='the .wda analysis file, or a windev_decode.py output folder')
    parser.add_argument('--out', type=Path, required=True, help='new directory for data.sqlite, CSV files and manifest.json')
    parser.add_argument('--table', action='append', help='read only these data files (repeatable)')
    parser.add_argument('--encoding', default='cp1252', help='code page of the text items (default cp1252)')
    parser.add_argument('--fit-integers', action='store_true',
                        help='read a file whose records are longer than the analysis says when exactly one widening of '
                             'integer items explains its record length (recorded in the manifest as assumed)')
    args = parser.parse_args()
    tables = load_analysis(args.analysis)
    if not tables:
        raise SystemExit(f'no data file description found in {args.analysis}')
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = export(args.folder, tables, args.out, {t.lower() for t in args.table or []}, args.encoding, args.fit_integers)
    if manifest['not_read']:
        raise SystemExit(f"not read: {', '.join(manifest['not_read'])} (reasons in manifest.json)")


if __name__ == '__main__':
    main()
