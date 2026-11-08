import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from helpers import load
from test_hfsql_mmo import PNG, TEXT, memo_file

builder = load('scripts/wdmap_xml_to_sqlite.py')
profiler = load('scripts/data_profile.py')

HEADER = (b'<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>\r\n'
          b'<?xml-stylesheet href="{0}.xsl" type="text/xsl"?>\n<HF_DOCUMENT>\r\n')


def wdmap_xml(table, rows):
    """WDMap-style export: Windows-1252 bytes, one <Table> element per row, CR LF, tabs."""
    out = HEADER.replace(b'{0}', table.encode())
    for row in rows:
        out += b'\t<' + table.encode() + b'>\r\n'
        for item, value in row:
            out += b'\t\t<' + item.encode() + b'>' + value + b'</' + item.encode() + b'>\r\n'
        out += b'\t</' + table.encode() + b'>\r\n'
    return out + b'</HF_DOCUMENT>\r\n'


CUSTOMERS = [
    [('Code', b'1'), ('Name', 'José Conceição'.encode('cp1252')), ('Notes', b'line 1\r\nline 2'),
     ('Created', b'20200630134209799'), ('Active', b'1'), ('Secret', b'\x01\x81<x&amp;')],
    [('Code', b'2'), ('Name', b'A &amp; B'), ('Notes', b''), ('Created', b'00000000000000000'), ('Active', b'0'),
     ('Secret', b'')],
    [('Code', b'3'), ('Name', b'No secret item')],
]


class WdmapXmlToSqliteTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.xml, self.data, self.out = root / 'xml', root / 'data', root / 'out'
        self.xml.mkdir()
        self.data.mkdir()
        (self.xml / 'Customers.XML').write_bytes(wdmap_xml('Customers', CUSTOMERS))
        # A table with an item named like the table itself.
        (self.xml / 'Note.XML').write_bytes(wdmap_xml('Note', [[('Note', b'first'), ('Id', b'1')]]))
        (self.xml / '_log_worker0.tsv').write_text(
            'Customers\t4096\tOK\t3\t7\nEmpty\t1024\tEMPTY_OR_NO_EXPORT\t0\t5\nNote\t2048\tOK\t1\t6\nDONE\n',
            encoding='utf-8-sig')
        (self.xml / '_log_worker1.tsv').write_text('Customers\t4096\tSKIPPED_EXISTS\t3\t0\n', encoding='utf-8')
        for name in ('Customers', 'Empty', 'Note'):
            (self.data / f'{name}.fic').write_bytes(b'PCS\x00' + b'\x00' * 60)
        (self.data / 'Customers.mmo').write_bytes(memo_file()[0])

    def connect(self, path):
        connection = sqlite3.connect(path)
        self.addCleanup(connection.close)  # before the directory is removed (Windows locks open files)
        return connection

    def test_rows_values_and_manifest(self):
        manifest = builder.build(self.xml, self.out, self.data, verbose=False)
        db = self.connect(self.out / 'data.sqlite')
        rows = db.execute('SELECT _row, Code, Name, Notes, Created, Active, Secret FROM Customers ORDER BY _row').fetchall()
        self.assertEqual(rows[0], (1, '1', 'José Conceição', 'line 1\r\nline 2', '20200630134209799', '1', '\x01\x81<x&'))
        self.assertEqual(rows[1][2:4], ('A & B', ''))  # an empty element is '', not NULL
        self.assertEqual(rows[2][3:], (None, None, None, None))  # items missing from a row are NULL
        self.assertEqual(db.execute('SELECT Note, Id FROM Note').fetchall(), [('first', '1')])
        tables = {r[0]: r[1:] for r in db.execute('SELECT name, rows, columns, export_status, log_rows FROM __tables')}
        self.assertEqual(tables, {'Customers': (3, 6, 'OK', 3), 'Empty': (0, 0, 'EMPTY_OR_NO_EXPORT', 0),
                                  'Note': (1, 2, 'OK', 1)})
        self.assertEqual(manifest['mismatched_rows'], [])
        stored = json.loads(db.execute("SELECT value FROM __export WHERE key = 'manifest'").fetchone()[0])
        self.assertEqual(stored['tables']['Customers']['rows'], 3)
        self.assertTrue((self.out / 'manifest.json').exists())

    def test_memos_are_loaded_with_their_pointer(self):
        builder.build(self.xml, self.out, self.data, verbose=False)
        db = self.connect(self.out / 'data.sqlite')
        memos = db.execute('SELECT tbl, kind, ext, record, text, data FROM __memos ORDER BY offset').fetchall()
        self.assertEqual([m[1] for m in memos], ['text', 'binary', 'binary', 'text'])
        self.assertEqual(memos[0][3:5], (42, TEXT))
        self.assertEqual((memos[1][2], memos[1][5]), ('png', PNG))
        builder.build(self.xml, self.out.with_name('fast'), self.data, memos=False, verbose=False)
        fast = self.connect(self.out.with_name('fast') / 'data.sqlite')
        self.assertEqual(fast.execute('SELECT COUNT(*) FROM __memos').fetchone()[0], 0)

    def test_row_count_disagreeing_with_the_log_is_reported(self):
        (self.xml / '_log_worker0.tsv').write_text('Customers\t4096\tOK\t4\t7\n', encoding='utf-8')
        self.assertEqual(builder.build(self.xml, self.out, verbose=False)['mismatched_rows'], ['Customers'])

    def test_refuses_existing_output(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            builder.build(self.xml, self.out, verbose=False)

    def test_large_file_rows_cross_chunk_boundaries(self):
        rows = [[('Code', str(i).encode()), ('Name', b'x' * 37)] for i in range(500)]
        (self.xml / 'Big.XML').write_bytes(wdmap_xml('Big', rows))
        original, builder.CHUNK = builder.CHUNK, 100
        try:
            values = [dict(r)['Code'] for r in builder.rows_of(self.xml / 'Big.XML', 'Big')]
        finally:
            builder.CHUNK = original
        self.assertEqual(values, [str(i) for i in range(500)])

    def test_data_profile_reads_the_copy_without_a_schema(self):
        builder.build(self.xml, self.out, self.data, verbose=False)
        db = self.connect(self.out / 'data.sqlite')
        report = profiler.profile(db, [])
        self.assertEqual(sorted(report['tables']), ['Customers', 'Note'])  # no XML, no table: listed in __tables only
        self.assertEqual(report['tables']['Customers']['rows'], 3)


if __name__ == '__main__':
    unittest.main()
