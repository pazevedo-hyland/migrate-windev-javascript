#!/usr/bin/env python3
"""Load WDMap XML exports (scripts/windows/wdmap_export.ps1) and, optionally, the memo files into one SQLite copy.

For HFSQL Classic data without its analysis (.wdd), where ODBC cannot open the files. Standard library only.
Output, in a new directory (like scripts/windows/export_odbc.py):
  data.sqlite
    <Table>        one table per <Table>.XML; `_row` = position in the export (NOT the physical record order),
                   then one TEXT column per item, in first-seen order. Values exactly as WDMap wrote them:
                   dates/times YYYYMMDDHHMMSSmmm (00000000000000000 = empty), booleans 0/1, text memos inline.
                   An empty element is '', an item missing from a row is NULL.
    __tables       per table: rows read, columns, export status and rows from the exporter's _log_worker*.tsv
                   (they must agree), .fic/.mmo bytes when --data-dir is given. Tables with a .fic but no XML
                   are listed with 0 rows (empty, or not exported: see the status).
    __memos        with --data-dir: every memo of every .mmo (scripts/hfsql_mmo.py): table, offset of the first
                   block (the pointer a .fic record holds), kind, record number when the memo carries one, text,
                   or binary data as BLOB with extension, original file name, size and SHA-256.
    __export       the manifest as JSON (also manifest.json next to it).
Tables named __* are skipped by scripts/data_profile.py, which profiles the data tables as they are.

WDMap writes an ISO-8859-1 header but Windows-1252 bytes, and values can hold control characters (password
items) that XML parsers reject: rows are cut with a tolerant reader. Bytes cp1252 leaves undefined are kept as
the Latin-1 character of the same code, so nothing is lost.

  python3 scripts/wdmap_xml_to_sqlite.py C:\\migration\\xml --data-dir C:\\data --out C:\\migration\\data
"""
import argparse
import codecs
import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hfsql_mmo  # noqa: E402

ITEM = re.compile(r'<([A-Za-z_][\w.-]*)(?:>(.*?)</\1>|\s*/>)', re.S)
CHUNK = 4 << 20
RESULTS = ('OK', 'EMPTY_OR_NO_EXPORT')


def _latin1(error):
    return error.object[error.start:error.end].decode('latin-1'), error.end


codecs.register_error('wdmap-latin1', _latin1)


def rows_of(path, table):
    """Yield each row of a WDMap XML export as a list of (item, value) pairs, in file order.

    A row is <Table> and </Table> each alone on its line (an item may share the table's name)."""
    opening = re.compile(rf'^[ \t]*<{re.escape(table)}>[ \t]*\r?\n', re.M)
    closing = re.compile(rf'\n[ \t]*</{re.escape(table)}>[ \t]*(?:\r?\n|$)')
    buffer, done = '', False
    with open(path, 'rb') as handle:
        while not done:
            chunk = handle.read(CHUNK)
            done = not chunk
            buffer += chunk.decode('cp1252', 'wdmap-latin1')  # one byte per character: chunks split safely
            at = 0
            while True:
                start = opening.search(buffer, at)
                if not start:
                    break
                end = closing.search(buffer, start.end() - 1)
                if not end or (end.end() == len(buffer) and not done):  # wait for the rest of the line
                    break
                body = buffer[start.end():end.start()]
                at = end.end()
                yield [(m.group(1), html.unescape(m.group(2) or '')) for m in ITEM.finditer(body)]
            buffer = buffer[at:]


def export_log(directory):
    """{table: (status, rows)} from wdmap_export.ps1 logs. Runs append to the logs; a result (OK or empty) wins
    over a failure in any log or order (retries), and a later skip never hides it."""
    found = {}
    for log in sorted(directory.glob('_log_worker*.tsv')):
        for line in log.read_text(encoding='utf-8-sig', errors='replace').splitlines():
            parts = line.split('	')
            if len(parts) < 4 or (parts[0] in found and (parts[2] == 'SKIPPED_EXISTS' or (
                    found[parts[0]][0] in RESULTS and parts[2] not in RESULTS))):
                continue
            found[parts[0]] = (parts[2], int(parts[3]) if parts[3].isdigit() else None)
    return found


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def load_table(db, table, xml):
    columns = []
    db.execute(f'CREATE TABLE {quote(table)} (_row INTEGER PRIMARY KEY)')
    batch, count = [], 0

    def flush():
        if batch:
            names = ', '.join(['_row'] + [quote(c) for c in columns])
            db.executemany(f'INSERT INTO {quote(table)} ({names}) VALUES ({", ".join("?" * (len(columns) + 1))})',
                           [row + [None] * (len(columns) + 1 - len(row)) for row in batch])
            batch.clear()

    for row in rows_of(xml, table):
        values = {}
        for column, value in row:
            if column not in columns:
                flush()  # rows already batched get NULL for the new column
                columns.append(column)
                db.execute(f'ALTER TABLE {quote(table)} ADD COLUMN {quote(column)} TEXT')
            values.setdefault(column, value)
        count += 1
        batch.append([count] + [values.get(c) for c in columns])
        if len(batch) >= 5000:
            flush()
    flush()
    return count, columns


def load_memos(db, table, mmo):
    counts = {}
    for offset, memo in hfsql_mmo.memos(mmo):
        if isinstance(memo, Exception):
            db.execute('INSERT INTO __memos (tbl, offset, kind, error) VALUES (?,?,?,?)',
                       (table, offset if offset != '' else None, 'error', str(memo)))
            counts['error'] = counts.get('error', 0) + 1
            continue
        data = memo.get('data') if memo['kind'] != 'text' else None
        names = memo.get('names') or ('', '')
        db.execute('INSERT INTO __memos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            table, offset, memo['kind'], memo['type'], memo['item'], memo.get('record'), memo.get('ext'),
            names[0] or names[1] or None, memo.get('text'), data, len(data) if data is not None else None,
            hashlib.sha256(data).hexdigest() if data else None, None))
        counts[memo['kind']] = counts.get(memo['kind'], 0) + 1
    return counts


def build(xml_dir, out, data_dir=None, memos=True, verbose=True):
    xml_dir = Path(xml_dir)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    log = export_log(xml_dir)
    xmls = {p.stem: p for p in sorted(xml_dir.iterdir()) if p.suffix.lower() == '.xml'}
    fics = {p.stem: p for p in sorted(Path(data_dir).iterdir()) if p.suffix.lower() == '.fic'} if data_dir else {}
    db = sqlite3.connect(out / 'data.sqlite')
    db.execute('CREATE TABLE __tables (name TEXT PRIMARY KEY, rows INTEGER, columns INTEGER, export_status TEXT, '
               'log_rows INTEGER, fic_bytes INTEGER, mmo_bytes INTEGER)')
    db.execute('CREATE TABLE __memos (tbl TEXT, offset INTEGER, kind TEXT, type INTEGER, item INTEGER, record INTEGER, '
               'ext TEXT, original_name TEXT, text TEXT, data BLOB, bytes INTEGER, sha256 TEXT, error TEXT)')
    manifest = {'exported': datetime.datetime.now().isoformat(timespec='seconds'), 'tool': 'wdmap_xml_to_sqlite.py',
                'source': 'WDMap XML export', 'encoding': 'cp1252 (header says ISO-8859-1)', 'tables': {}}
    mismatched = []
    for name in sorted(set(xmls) | set(fics), key=str.lower):
        rows, columns = load_table(db, name, xmls[name]) if name in xmls else (0, [])
        status, log_rows = log.get(name, ('exported' if name in xmls else 'not exported', None))
        fic = fics.get(name)
        mmo = next((p for p in (fic.with_suffix('.mmo'), fic.with_suffix('.MMO')) if p.exists()), None) if fic else None
        entry = {'rows': rows, 'columns': columns, 'export_status': status, 'log_rows': log_rows}
        if log_rows is not None and log_rows != rows:
            mismatched.append(name)
        if memos and mmo and mmo.stat().st_size > hfsql_mmo.FIRST_BLOCK:
            entry['memos'] = load_memos(db, name, mmo)
        db.execute('INSERT INTO __tables VALUES (?,?,?,?,?,?,?)', (name, rows, len(columns), status, log_rows,
                   fic.stat().st_size if fic else None, mmo.stat().st_size if mmo else None))
        db.commit()
        manifest['tables'][name] = entry
        if verbose:
            print(f'{name}: {rows} rows, {len(columns)} columns, {status}'
                  + (f', memos {entry["memos"]}' if entry.get('memos') else ''), flush=True)
    manifest['mismatched_rows'] = mismatched
    db.execute('CREATE TABLE __export (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    db.execute("INSERT INTO __export VALUES ('manifest', ?)", (json.dumps(manifest, ensure_ascii=False),))
    db.commit()
    db.close()
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('xml_dir', type=Path, help='folder of <Table>.XML files (and _log_worker*.tsv)')
    parser.add_argument('--data-dir', type=Path, help='copy of the data folder: lists every .fic, reads the .mmo files')
    parser.add_argument('--out', type=Path, required=True, help='new directory for data.sqlite and manifest.json')
    parser.add_argument('--no-memos', action='store_true', help='do not read .mmo files')
    args = parser.parse_args()
    manifest = build(args.xml_dir, args.out, args.data_dir, not args.no_memos)
    if manifest['mismatched_rows']:  # the export log counted other rows: the XML is incomplete or unreadable
        raise SystemExit(f'rows read differ from the export log in: {", ".join(manifest["mismatched_rows"])}')


if __name__ == '__main__':
    main()
