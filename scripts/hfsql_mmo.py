#!/usr/bin/env python3
"""Read HFSQL Classic memo files (.mmo) directly: text memos and binary memos (images, PDFs, attachments).

Written from the observed file layout (WINDEV 28 data; see docs/hfsql-classic-format.md), not from PC SOFT
documentation. Standard library only; the .mmo is only read.

File: "PCS\\0" header; blocks from offset 0xD2 to the end of the file. Each block (little-endian):
  u8  size class    the block occupies 2**class bytes (header included)
  u8  role          0xF4 single-block memo, 0xE4 first block of a chain, 0xC4 middle, 0xD4 last, 0x00 free
  u32 payload length, u32 payload length (repeated)
  u8  flag
  u64 offset of the next block (0xFFFFFFFFFFFFFFFF = none)
  u16 unknown
  payload
A memo's content is the concatenation of the payloads along its chain:
  u32 item (unconfirmed: small values, probably the memo item's position), u8 type, then
  0x0C text     u32 record number, u32 0, u16 flags, u32 length, text (cp1252, sometimes UTF-16LE)
  0x0D binary   same header, then a small wrapper and the file bytes (found by their signature)
  0x00 binary   u32 Unix time, u16 len1, u16 len2, original full path + NUL, short path + NUL, then
                01 u32 size u32 crc u32 u32 u16(0x8001) u32 data length u16 width u16 height, data
                (no record number)

Linking memos to rows: a memo item in a .fic record holds a u64 file offset of the memo's FIRST block in the
.mmo (read_memo(path, offset)). Text and 0x0D memos also carry the record number in their header; 0x00 memos
can only be linked through that pointer. WDMap exports text memos inline but no binary memos, and its row
order is not the physical record order: never link binary memos by position.

  python3 scripts/hfsql_mmo.py C:\\data\\*.mmo                       # summary per file, by kind
  python3 scripts/hfsql_mmo.py C:\\data\\Table.mmo --out memos       # + binary memos as files, index.csv/json
  python3 scripts/hfsql_mmo.py C:\\data\\Table.mmo --offset 0x1d2    # one memo, from a .fic pointer
"""
import argparse
import csv
import glob
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

HEADER = 21
FIRST_BLOCK = 0xD2
NO_NEXT = 0xFFFFFFFFFFFFFFFF
ROLES = {0xF4: 'single', 0xE4: 'first', 0xC4: 'middle', 0xD4: 'last', 0x00: 'free'}
SIGNATURES = [(b'\x89PNG\r\n\x1a\n', 'png'), (b'\xff\xd8\xff', 'jpg'), (b'GIF8', 'gif'), (b'%PDF', 'pdf'),
              (b'PK\x03\x04', 'zip'), (b'\xd0\xcf\x11\xe0', 'ole'), (b'II*\x00', 'tif'), (b'MM\x00*', 'tif'),
              (b'RIFF', 'riff'), (b'BM', 'bmp')]


class Mmo:
    """An open .mmo file. Use as a context manager."""

    def __init__(self, path):
        self.path = str(path)
        self.file = open(path, 'rb')
        self.size = os.fstat(self.file.fileno()).st_size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.file.close()

    def block(self, offset):
        self.file.seek(offset)
        head = self.file.read(HEADER)
        if len(head) < HEADER:
            raise ValueError(f'short block header at {offset:#x}')
        size_class, role, length, repeated, flag, following, _ = struct.unpack('<BBIIBQH', head)
        return {'offset': offset, 'size_class': size_class, 'role': role, 'length': length,
                'repeated': repeated, 'flag': flag, 'next': following}

    def blocks(self):
        """Every block in file order; the walk must land exactly on the end of the file."""
        offset = FIRST_BLOCK
        while offset + HEADER <= self.size:
            block = self.block(offset)
            if not 4 <= block['size_class'] <= 40:
                raise ValueError(f'block walk broke at {offset:#x}: size class {block["size_class"]}')
            yield block
            offset += 1 << block['size_class']
        if offset != self.size:
            raise ValueError(f'block walk ended at {offset:#x}, file size {self.size:#x}')

    def first_blocks(self):
        """Offsets of every memo's first block (single or first-of-chain blocks with a payload)."""
        return [b['offset'] for b in self.blocks() if b['role'] in (0xF4, 0xE4) and b['length']]

    def content(self, offset):
        """Concatenated payloads of the memo whose first block is at `offset`."""
        out, seen = bytearray(), set()
        while offset != NO_NEXT:
            if offset in seen:
                raise ValueError(f'block chain loops at {offset:#x}')
            seen.add(offset)
            block = self.block(offset)
            if block['length'] != block['repeated'] or offset + HEADER + block['length'] > self.size:
                raise ValueError(f'bad block at {offset:#x}: {block}')
            if block['role'] not in ROLES:
                raise ValueError(f'unknown block role {block["role"]:#x} at {offset:#x}')
            self.file.seek(offset + HEADER)
            out += self.file.read(block['length'])
            offset = block['next']
        return bytes(out)


def sniff(data, window=64):
    """(extension, start) of the first known file signature in the first bytes, or ('bin', None)."""
    for signature, extension in SIGNATURES:
        start = data.find(signature, 0, window)
        if start >= 0:
            return extension, start
    return 'bin', None


def decode_text(raw):
    if len(raw) >= 4 and raw[1::2].count(0) > len(raw) * 0.4:  # UTF-16LE: NUL in most odd positions
        return raw.decode('utf-16-le', 'replace'), 'utf-16-le'
    return raw.decode('cp1252', 'replace'), 'cp1252'


def parse(content):
    """Decode one memo's content into a dict with `kind` 'text', 'binary' or 'unknown'."""
    if len(content) < 5:
        return {'kind': 'unknown', 'type': None, 'item': None, 'data': content}
    item, kind = struct.unpack_from('<IB', content, 0)
    if kind in (0x0C, 0x0D) and len(content) >= 19:
        record, _, flags, length = struct.unpack_from('<IIHI', content, 5)
        raw = content[19:19 + length]
        if kind == 0x0C:
            text, encoding = decode_text(raw)
            return {'kind': 'text', 'type': kind, 'item': item, 'record': record, 'flags': flags,
                    'text': text, 'encoding': encoding}
        extension, start = sniff(raw)
        return {'kind': 'binary', 'type': kind, 'item': item, 'record': record, 'flags': flags,
                'ext': extension, 'data': raw[start or 0:], 'names': ('', '')}
    if kind == 0x00 and len(content) >= 13:
        stamp, len1, len2 = struct.unpack_from('<IHH', content, 5)
        at = 13
        full = content[at:at + len1].decode('cp1252', 'replace')
        at += len1 + (1 if len1 else 0)
        short = content[at:at + len2].decode('cp1252', 'replace')
        at += len2 + (1 if len2 else 0)
        blob = content[at:]
        extension, start = sniff(blob)
        if start is None and len(blob) >= 27 and blob[0] == 1:
            length = struct.unpack_from('<I', blob, 19)[0]
            data = blob[27:27 + length]
            extension = sniff(data)[0]
        else:
            data = blob[start or 0:]
        return {'kind': 'binary', 'type': kind, 'item': item, 'record': None, 'time': stamp, 'ext': extension,
                'data': data, 'names': (full, short)}
    return {'kind': 'unknown', 'type': kind, 'item': item, 'data': content}


def read_memo(path, offset):
    """The memo a .fic record points to (`offset` = the u64 stored in the memo item)."""
    with Mmo(path) as memo:
        return parse(memo.content(offset))


def memos(path):
    """Yield (first block offset, parsed memo or the exception) for every memo of a file; a failed block walk
    yields ('', the exception) once."""
    with Mmo(path) as memo:
        try:
            heads = memo.first_blocks()
        except ValueError as error:
            yield '', error
            return
        for offset in heads:
            try:
                yield offset, parse(memo.content(offset))
            except (ValueError, struct.error) as error:
                yield offset, error


def label(memo):
    return memo['kind'] + ('/' + memo['ext'] if memo.get('ext') else '')


def extract(paths, out):
    """Write binary memos under out/<file>/ and an index of every memo; return the index rows."""
    out.mkdir(parents=True, exist_ok=False)
    index = []
    for path in paths:
        stem = Path(path).stem
        for offset, memo in memos(path):
            row = {'file': Path(path).name, 'offset': offset, 'kind': 'error', 'type': '', 'item': '', 'record': '',
                   'ext': '', 'bytes': '', 'sha256': '', 'original_name': '', 'path': '', 'error': ''}
            if isinstance(memo, Exception):
                row['error'] = str(memo)
                index.append(row)
                continue
            row.update(kind=memo['kind'], type=memo['type'], item=memo['item'], record=memo.get('record'),
                       ext=memo.get('ext', ''))
            if memo['kind'] == 'text':
                row['bytes'] = len(memo['text'])
            elif memo['kind'] == 'binary' and memo['data']:
                target = out / stem / f'{offset:x}.{memo["ext"]}'
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(memo['data'])
                row.update(bytes=len(memo['data']), sha256=hashlib.sha256(memo['data']).hexdigest(),
                           original_name=memo['names'][0] or memo['names'][1], path=target.relative_to(out).as_posix())
            index.append(row)
    with (out / 'index.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(index[0]) if index else ['file'])
        writer.writeheader()
        writer.writerows(index)
    (out / 'index.json').write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding='utf-8')
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mmo', nargs='+', help='.mmo files (wildcards accepted)')
    parser.add_argument('--out', type=Path, help='new directory: binary memos as files, index.csv and index.json')
    parser.add_argument('--offset', type=lambda v: int(v, 0), help='print the memo whose first block is here')
    args = parser.parse_args()
    paths = sorted({p for pattern in args.mmo for p in (glob.glob(pattern) or [pattern])})
    if args.offset is not None:
        memo = read_memo(paths[0], args.offset)
        shown = {k: v for k, v in memo.items() if k != 'data'}
        if 'data' in memo:
            shown['bytes'] = len(memo['data'])
        print(json.dumps(shown, indent=1, ensure_ascii=False))
        return
    errors = 0
    if args.out:
        index = extract(paths, args.out)
        errors = sum(row['kind'] == 'error' for row in index)
        print(f'{len(index)} memos, {errors} errors -> {args.out}')
    else:
        for path in paths:
            kinds, problems = {}, []
            for offset, memo in memos(path):
                if isinstance(memo, Exception):
                    problems.append(f'{offset:#x}: {memo}' if offset != '' else f'block walk: {memo}')
                    continue
                kinds[label(memo)] = kinds.get(label(memo), 0) + 1
            errors += len(problems)
            print(f'{Path(path).name}\t{os.path.getsize(path)} bytes\t{sum(kinds.values())} memos\t'
                  + ', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))
                  + ''.join(f'\n  error {p}' for p in problems[:5]))
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
