"""Windows check of export_odbc.py against a real ODBC driver (SQLite ODBC), with accents, decimals, dates and NULLs."""
import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=False)
    database = work / 'sample.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE Clientes (ClientesID INTEGER PRIMARY KEY, Descricao TEXT, Saldo NUMERIC, Criado DATE)')
        db.executemany('INSERT INTO Clientes VALUES (?, ?, ?, ?)',
                       [(1, 'Oficina São João', '12.50', '2026-01-02'), (2, None, None, None)])
        db.execute('CREATE TABLE unidades (id INTEGER PRIMARY KEY, nome TEXT)')
        db.execute("INSERT INTO unidades VALUES (1, 'Peça')")
    out = work / 'export'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/windows/export_odbc.py'), '--connection-string',
                             f'Driver={{SQLite3 ODBC Driver}};Database={database}', '--out', str(out)],
                            capture_output=True, text=True, encoding='utf-8')
    print(result.stdout, result.stderr)
    failures = [] if result.returncode == 0 else [f'exit {result.returncode}']
    if not failures:
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        if {t: v['rows'] for t, v in manifest['tables'].items()} != {'Clientes': 2, 'unidades': 1}:
            failures.append(f'row counts: {manifest}')
        with (out / 'Clientes.csv').open(encoding='utf-8') as handle:
            rows = list(csv.reader(handle))
        if rows[1][1] != 'Oficina São João' or rows[2][1:] != ['', '', '']:
            failures.append(f'values: {rows}')
    print('\n'.join(failures) or 'ODBC export OK')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
