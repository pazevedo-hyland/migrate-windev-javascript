import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from helpers import load

module = load('scripts/hfsql_read.py')
decoder = module.decoder


def chunk(kind, body):
    return struct.pack('<4I', 12, kind, 1, len(body) + 4) + body


def analysis_item(number, table, name, code, size, position, caption='', key=0, parts=(), default=None, deleted=False,
                  digits=b'\0\0'):
    head = bytearray(13)
    head[3], head[6], head[8], head[9] = code, key, bool(parts), 1
    tail = struct.pack('<HHBB', position, 20 - position, not deleted, 5 if key and code == 2 else 0) + b'\0' * 12
    for part in parts:
        tail += struct.pack('<4I', 12, 1, 1, 13) + struct.pack('<II', part, 0) + b'\5'
    if default is not None:
        value = default.encode() + b'\0'
        tail += struct.pack('<4I', 12, 2, 1, len(value) + 8) + b'\0' * 4 + value
    body = (struct.pack('<4I', number, 0, table, 0) + name.encode() + b'\0' + b'20240131\0' + digits + b'\0' * 4
            + b'ANA\0' + b'RUI\0' + b'\0' * 16 + struct.pack('<I', size) + b'\0\0' + caption.encode('utf-8') + b'\0'
            + bytes(head) + b'A' * 32 + b'\0' + tail)
    return chunk(5, body)


def analysis_block():
    """Two data files: Customers (every measured type, a deleted item, a composite key) and Notes."""
    described = lambda number, name, kept=True: chunk(6, (
        struct.pack('<II', number, 0) + name + b'\0\0' + name + b'\0fic\0' + b'\0' * 5 + struct.pack('<I', 3) + b'20240130\0'
        + struct.pack('<I', 70) + b'\0' * 30 + b'B' * 32 + b'\0' + b'C' * 32 + b'\0' + struct.pack('<4i', 10, -9, 170, 125)
        + bytes([kept]) + b'\0' * 20))
    customers, notes = described(1, b'Customers'), described(2, b'Notes')
    items = [
        analysis_item(1, 1, 'code', 2, 5, 0, 'Código', key=1),
        analysis_item(2, 1, 'since', 14, 8, 1),
        analysis_item(3, 1, 'old', 36, 1, 2, deleted=True),
        analysis_item(4, 1, 'opens', 11, 4, 2),
        analysis_item(5, 1, 'seen', 34, 8, 3),
        analysis_item(6, 1, 'worked', 35, 8, 4),
        analysis_item(7, 1, 'balance', 41, 7, 5, default='0', digits=b'\x06\x0a'),
        analysis_item(8, 1, 'active', 37, 1, 6, default='1'),
        analysis_item(9, 1, 'visits', 9, 2, 7, key=2),
        analysis_item(10, 1, 'delta', 5, 4, 8),
        analysis_item(11, 1, 'remark', 29, 8, 9),
        analysis_item(12, 1, 'codesince', 28, 13, 10, key=1, parts=(1, 2)),
        analysis_item(13, 2, 'id', 27, 8, 0, key=1),
    ]
    gone = described(3, b'Gone', kept=False) + analysis_item(14, 3, 'x', 2, 5, 0)
    return b'\0' * 24 + customers + b''.join(items[:12]) + notes + items[12] + gone


def data_file(length, records, deleted=0):
    """A `.fic`: header, the 44 bytes that end it, one unused slot, the records."""
    assert all(len(record) == length for record in records)
    return (b'PCS\0' + b'\x55' * 300 + struct.pack('<4I', 7, len(records) - deleted, 0, deleted) + b'\0' * 20
            + b'\xff' * 8 + b'\xaa' * length + b''.join(records))


def record(values, state=0x10, flags=b'\xff\xff'):
    return bytes([state]) + b'\x01\0' + b'\x11\x22\x33\x44' + b'\0' + flags + b''.join(values)


def memo_file(content, split=None):
    """A `.mmo` holding one memo at offset 100, in one block or two."""
    payload = struct.pack('<IBQHI', 22, 12, 1, 0, len(content)) + content
    first = payload if split is None else payload[:split]
    block = lambda mark, data, following: (bytes([7, mark]) + struct.pack('<II', len(data), len(data)) + b'\0'
                                           + following + b'\0\0' + data)
    if split is None:
        return b'PCS\0' + b'\0' * 96 + block(0xf4, first, b'\xff' * 8)
    second = 100 + 21 + len(first) + 5
    return (b'PCS\0' + b'\0' * 96 + block(0xe4, first, struct.pack('<Q', second)) + b'\0' * 5
            + block(0xd4, payload[split:], b'\xff' * 8))


CUSTOMER = [b'AB\0\0\0\0', b'20240229\0', b'0930\0', struct.pack('<BBHI', 6, 3, 2023, 37189091),
            struct.pack('<q', 1800000), (93500000).to_bytes(7, 'little', signed=True), b'\1', struct.pack('<H', 513),
            struct.pack('<i', -2), struct.pack('<Q', 100)]
EMPTY = [b'\0' * 6, b'\0' * 9, b'\0' * 5, b'\0' * 8, b'\0' * 8, (-1500000).to_bytes(7, 'little', signed=True), b'\0',
         b'\0\0', b'\0' * 4, b'\xff' * 8]


class AnalysisFile(unittest.TestCase):
    def test_tables_items_keys_defaults_and_deleted_items(self):
        tables = decoder.analysis_schema(analysis_block())
        self.assertEqual([(t['name'], len(t['items']), t['created'], t.get('deleted')) for t in tables],
                         [('Customers', 12, '20240130', None), ('Notes', 1, '20240130', None), ('Gone', 1, '20240130', True)])
        items = {item['name']: item for item in tables[0]['items']}
        self.assertEqual((items['code']['caption'], items['code']['type_code'], items['code']['size'], items['code']['key']),
                         ('Código', 2, 5, 'unique'))
        self.assertEqual((items['balance']['decimals'], items['balance']['integer_digits'], items['balance']['default']), (6, 10, '0'))
        self.assertEqual((items['visits']['key'], items['old'].get('deleted'), items['code'].get('deleted')), ('duplicates', True, None))
        self.assertEqual((items['codesince']['parts'], items['codesince']['key']), (['code', 'since'], 'unique'))
        self.assertEqual((items['code']['created'], items['code']['created_by'], items['code']['changed_by']), ('20240131', 'ANA', 'RUI'))
        self.assertEqual((items['since']['position'], items['since']['order']), (1, 19))
        self.assertEqual((items['code']['key_options_code'], items['code']['key_compares'], 'key_compares' in items['visits']),
                         (5, 'ignores case and accents', False))

    def test_decode_project_saves_the_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            (project / 'App.ana').mkdir(parents=True)
            (project / 'App.ana' / 'App.wda').write_bytes(b'PCS\0' + b'\x14\0\0\0' + decoder.pack(analysis_block()))
            index = decoder.decode_project(project, Path(folder, 'out'))
            saved = json.loads(Path(folder, 'out/analysis.json').read_text(encoding='utf-8'))
        self.assertEqual([t['name'] for t in saved['tables']], ['Customers', 'Notes', 'Gone'])
        self.assertEqual((index['coverage']['analysis_tables'], index['coverage']['analysis_items']), (2, 12))


class DataFiles(unittest.TestCase):
    def setUp(self):
        self.tables = decoder.analysis_schema(analysis_block())
        self.length = module.record_length(module.stored_items(self.tables[0]))

    def test_record_layout_leaves_out_deleted_items_and_composite_keys(self):
        items = module.stored_items(self.tables[0])
        self.assertEqual([item['name'] for item in items],
                         ['code', 'since', 'opens', 'seen', 'worked', 'balance', 'active', 'visits', 'delta', 'remark'])
        self.assertEqual(self.length, 8 + 2 + 6 + 9 + 5 + 8 + 8 + 7 + 1 + 2 + 4 + 8)

    def test_values_of_every_measured_type(self):
        data = data_file(self.length, [record(CUSTOMER), record(EMPTY, state=0x80), record(EMPTY)], deleted=1)
        items, rows, deleted = module.read_table(data, self.tables[0], memo_file('café'.encode('cp1252')))
        self.assertEqual(rows[0], ['AB', '2024-02-29', '09:30:00', '2023-03-06T10:19:49.091', '1800000', '93.5', '1', '513',
                                   '-2', 'café'])
        self.assertEqual(rows[1], ['', '', '', '', '0', '-1.5', '0', '0', '0', ''])
        self.assertEqual((len(rows), deleted), (2, 1))

    def test_memo_in_two_blocks_and_item_without_value(self):
        data = data_file(self.length, [record(CUSTOMER, flags=b'\xfd\xff')])
        _, rows, _ = module.read_table(data, self.tables[0], memo_file(b'first half, second half', split=30))
        self.assertEqual((rows[0][1], rows[0][9]), (None, 'first half, second half'))

    def test_a_file_of_another_record_length_is_refused(self):
        data = data_file(self.length + 3, [record(CUSTOMER) + b'\0\0\0'])
        with self.assertRaisesRegex(module.Unreadable, 'not the 68 bytes the analysis gives for 10 items'):
            module.read_table(data, self.tables[0], memo_file(b'x'))
        with self.assertRaisesRegex(module.Unreadable, 'memo block not found'):
            module.read_table(data_file(self.length, [record(CUSTOMER)]), self.tables[0], b'PCS\0' + b'\0' * 300)
        with self.assertRaisesRegex(module.Unreadable, 'without its .mmo'):
            module.read_table(data_file(self.length, [record(CUSTOMER)]), self.tables[0])

    def test_measured_record_length_and_integers_stored_wider(self):
        table = {'name': 'Links', 'items': [
            {'name': 'station', 'type_code': 5, 'size': 4, 'position': 0, 'key': None},
            {'name': 'worker', 'type_code': 36, 'size': 1, 'position': 1, 'key': None}]}
        rows = [record([struct.pack('<i', 1), struct.pack('<I', 13)], flags=b'\xff'),
                record([struct.pack('<i', 2), struct.pack('<I', 8)], flags=b'\xff')]
        data = data_file(17, rows)
        self.assertEqual(module.measured_lengths(data), [17])
        with self.assertRaisesRegex(module.Unreadable, r'not the 14 bytes the analysis gives for 2 items \(the file fits records of 17'):
            module.read_table(data, table)
        items, read, _ = module.read_table(data, table, fit_integers=True)
        self.assertEqual((read, items[1]['stored_size'], 'stored_size' in items[0]), ([['1', '13'], ['2', '8']], 4, False))
        too_big = data_file(17, [record([struct.pack('<i', 1), struct.pack('<I', 300)], flags=b'\xff')])
        with self.assertRaisesRegex(module.Unreadable, 'worker: 300 does not fit the 1 bytes'):
            module.read_table(too_big, table, fit_integers=True)
        two_ways = {'name': 'Links', 'items': [dict(table['items'][1], name='a', position=0), table['items'][1]]}
        with self.assertRaisesRegex(module.Unreadable, '2 ways of widening its integers'):
            module.read_table(data_file(14, [record([b'\1\0\0\0', b'\2'], flags=b'\xff')]), two_ways, fit_integers=True)

    def test_export_writes_sqlite_csv_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder, 'data'), Path(folder, 'out')
            source.mkdir()
            out.mkdir()
            (source / 'customers.FIC').write_bytes(data_file(self.length, [record(CUSTOMER), record(EMPTY)]))
            (source / 'customers.mmo').write_bytes(memo_file(b'note'))
            (source / 'Notes.fic').write_bytes(data_file(20, [b'\x10' + b'\0' * 19]))       # 17 bytes expected
            (source / 'Other.fic').write_bytes(b'PCS\0' + b'\0' * 400)
            (source / 'Gone.fic').write_bytes(b'PCS\0' + b'\0' * 400)                       # deleted from the analysis
            manifest = module.export(source, self.tables, out)
            copy = sqlite3.connect(out / 'data.sqlite')
            rows = copy.execute('SELECT code, balance, remark FROM Customers').fetchall()
            copy.close()
            csv_text = (out / 'Customers.csv').read_text(encoding='utf-8')
        self.assertEqual(rows, [('AB', '93.5', 'note'), ('', '-1.5', '')])
        self.assertIn('AB,2024-02-29,09:30:00,2023-03-06T10:19:49.091,1800000,93.5,1,513,-2,note', csv_text)
        table = manifest['tables']['Customers']
        self.assertEqual((table['rows'], table['count'], table['columns'][5]), (2, 2, {'name': 'balance', 'type_code': 41,
                                                                                    'size': 7, 'scale': 6, 'nulls': 0}))
        self.assertEqual(sorted(manifest['not_read']), ['Gone.fic', 'Notes.fic', 'Other.fic'])
        self.assertIn('no data file of this name', manifest['not_read']['Other.fic'])


if __name__ == '__main__':
    unittest.main()
