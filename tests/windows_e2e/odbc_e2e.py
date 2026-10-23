"""Windows check of export_odbc.py against a real ODBC driver, with accents, decimals, dates and NULLs.

Uses the SQLite ODBC driver when installed, otherwise SQL Server LocalDB (present on GitHub's Windows images).
"""
import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pyodbc

ROOT = Path(__file__).resolve().parents[2]
ROWS = [(1, 'Oficina São João', '12.50', '2026-01-02'), (2, None, None, None), (3, '', '0.00', '2026-01-03')]


def sqlserver_localdb():
    driver = next(d for d in pyodbc.drivers() if d.startswith('ODBC Driver') and 'SQL Server' in d)
    subprocess.run(['sqllocaldb', 'start', 'MSSQLLocalDB'], check=True)
    server = f'Driver={{{driver}}};Server=(localdb)\\MSSQLLocalDB;Trusted_Connection=yes;TrustServerCertificate=yes'
    with pyodbc.connect(server, autocommit=True) as db:
        db.execute("IF DB_ID('migtest') IS NOT NULL DROP DATABASE migtest")
        db.execute('CREATE DATABASE migtest')
    target = server + ';Database=migtest'
    with pyodbc.connect(target, autocommit=True) as db:
        db.execute('CREATE TABLE Clientes (ClientesID INT PRIMARY KEY, Descricao NVARCHAR(100), Saldo NUMERIC(10,2), Criado DATE)')
        db.cursor().executemany('INSERT INTO Clientes VALUES (?, ?, ?, ?)', ROWS)
        db.execute('CREATE TABLE unidades (id INT PRIMARY KEY, nome NVARCHAR(20))')
        db.execute("INSERT INTO unidades VALUES (1, N'Peça')")
    return target


def main():
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=False)
    print('ODBC drivers:', pyodbc.drivers())
    connection = sqlserver_localdb()
    out = work / 'export'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/windows/export_odbc.py'), '--connection-string',
                             connection, '--out', str(out), '--table', 'Clientes', '--table', 'unidades'],
                            capture_output=True, text=True, encoding='utf-8')
    print(result.stdout, result.stderr)
    failures = [] if result.returncode == 0 else [f'exit {result.returncode}']
    if not failures:
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        if {t: (v['rows'], v['count']) for t, v in manifest['tables'].items()} != {'Clientes': (3, 3), 'unidades': (1, 1)}:
            failures.append(f'row counts: {manifest}')
        copy = sqlite3.connect(out / 'data.sqlite')
        names = [r[0] for r in copy.execute('SELECT Descricao FROM Clientes ORDER BY ClientesID')]
        copy.close()
        if names != ['Oficina São João', None, '']:  # the SQLite copy keeps NULL and '' apart
            failures.append(f'sqlite values: {names}')
        with (out / 'Clientes.csv').open(encoding='utf-8') as handle:
            rows = list(csv.reader(handle))
        if rows[1] != ['1', 'Oficina São João', '12.50', '2026-01-02'] or rows[2] != ['2', '', '', '']:
            failures.append(f'values: {rows}')
        with (out / 'unidades.csv').open(encoding='utf-8') as handle:
            if list(csv.reader(handle))[1] != ['1', 'Peça']:
                failures.append('unidades value')
    print('\n'.join(failures) or 'ODBC export OK')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
