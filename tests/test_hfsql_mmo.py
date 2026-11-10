import csv
import json
from pathlib import Path
import struct
import tempfile
import unittest

from helpers import load

mmo = load('scripts/hfsql_mmo.py')

PNG = b'\x89PNG\r\n\x1a\n' + bytes(range(90))  # longer than one 64-byte block: a three-block chain
JPEG = b'\xff\xd8\xff\xe0' + b'synthetic jpeg body'
TEXT = 'Olá, café\r\nsecond line'


def block(size_class, role, payload=b'', following=mmo.NO_NEXT):
    head = struct.pack('<BBIIBQH', size_class, role, len(payload), len(payload), 0, following, 0)
    assert len(head) + len(payload) <= 1 << size_class
    return (head + payload).ljust(1 << size_class, b'\x00')


def text_memo(item, record, text, encoding='cp1252'):
    raw = text.encode(encoding)
    return struct.pack('<IB', item, 0x0C) + struct.pack('<IIHI', record, 0, 0, len(raw)) + raw


def binary_memo(item, record, data):
    raw = b'\x01\x00\x00\x00' + data  # a small wrapper before the file bytes
    return struct.pack('<IB', item, 0x0D) + struct.pack('<IIHI', record, 0, 0, len(raw)) + raw


def named_memo(item, full, short, data):
    names = full.encode('cp1252') + b'\x00' + short.encode('cp1252') + b'\x00'
    wrapper = b'\x01' + struct.pack('<IIIIHIHH', len(data) + 8, 0x1234, 0, 0, 0x8001, len(data), 16, 16)
    return (struct.pack('<IB', item, 0x00) + struct.pack('<IHH', 1700000000, len(full), len(short))
            + names + wrapper + data)


def memo_file():
    """Synthetic .mmo bytes and the offsets of its memos' first blocks."""
    data = bytearray(b'PCS\x00'.ljust(mmo.FIRST_BLOCK, b'\x00'))
    offsets = {}
    offsets['text'] = len(data)
    data += block(7, 0xF4, text_memo(1, 42, TEXT))
    # A binary memo in three 64-byte blocks, with a free block inside the chain.
    content = binary_memo(2, 7, PNG)
    room = 64 - mmo.HEADER
    parts = [content[i:i + room] for i in range(0, len(content), room)]
    assert len(parts) == 3
    first = len(data)
    middle, free, last = first + 64, first + 128, first + 160
    offsets['png'], offsets['free'] = first, free
    data += block(6, 0xE4, parts[0], middle) + block(6, 0xC4, parts[1], last) + block(5, 0x00) + block(6, 0xD4, parts[2])
    offsets['named'] = len(data)
    data += block(7, 0xF4, named_memo(3, 'C:\\Images\\photo.jpg', 'photo.jpg', JPEG))
    offsets['utf16'] = len(data)
    data += block(7, 0xF4, text_memo(1, 43, 'Unicode ✓ text', 'utf-16-le'))
    return bytes(data), offsets


class HfsqlMmoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.bytes, self.offsets = memo_file()
        self.path = self.dir / 'Table.mmo'
        self.path.write_bytes(self.bytes)

    def tearDown(self):
        self.tmp.cleanup()

    def test_walk_finds_every_memo_and_skips_free_blocks(self):
        with mmo.Mmo(self.path) as memo:
            roles = [b['role'] for b in memo.blocks()]
            heads = memo.first_blocks()
        self.assertEqual(roles, [0xF4, 0xE4, 0xC4, 0x00, 0xD4, 0xF4, 0xF4])
        self.assertEqual(heads, [self.offsets[k] for k in ('text', 'png', 'named', 'utf16')])

    def test_text_memo_carries_record_number(self):
        memo = mmo.read_memo(self.path, self.offsets['text'])
        self.assertEqual((memo['kind'], memo['record'], memo['item'], memo['text'], memo['encoding']),
                         ('text', 42, 1, TEXT, 'cp1252'))
        self.assertEqual(mmo.read_memo(self.path, self.offsets['utf16'])['text'], 'Unicode ✓ text')

    def test_binary_chain_is_concatenated_and_unwrapped(self):
        memo = mmo.read_memo(self.path, self.offsets['png'])
        self.assertEqual((memo['kind'], memo['ext'], memo['record'], memo['data']), ('binary', 'png', 7, PNG))

    def test_named_binary_memo_keeps_original_path(self):
        memo = mmo.read_memo(self.path, self.offsets['named'])
        self.assertEqual((memo['ext'], memo['data'], memo['record']), ('jpg', JPEG, None))
        self.assertEqual(memo['names'], ('C:\\Images\\photo.jpg', 'photo.jpg'))

    def test_extract_writes_binary_files_and_index(self):
        out = self.dir / 'memos'
        index = mmo.extract([self.path], out)
        self.assertEqual([r['kind'] for r in index], ['text', 'binary', 'binary', 'text'])
        self.assertEqual((out / index[1]['path']).read_bytes(), PNG)
        self.assertEqual(index[2]['original_name'], 'C:\\Images\\photo.jpg')
        with (out / 'index.csv').open(encoding='utf-8') as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 4)
        self.assertEqual(len(json.loads((out / 'index.json').read_text(encoding='utf-8'))), 4)
        with self.assertRaises(FileExistsError):  # a new directory each time
            mmo.extract([self.path], out)

    def test_broken_walk_and_chain_are_reported(self):
        truncated = self.dir / 'Broken.mmo'
        truncated.write_bytes(self.bytes[:-10])
        found = list(mmo.memos(truncated))
        self.assertEqual(len(found), 1)
        self.assertIsInstance(found[0][1], ValueError)
        looped = bytearray(self.bytes)
        struct.pack_into('<Q', looped, self.offsets['png'] + 64 + 11, self.offsets['png'])  # middle -> first
        (self.dir / 'Loop.mmo').write_bytes(looped)
        with self.assertRaisesRegex(ValueError, 'loops'):
            mmo.read_memo(self.dir / 'Loop.mmo', self.offsets['png'])


if __name__ == '__main__':
    unittest.main()
