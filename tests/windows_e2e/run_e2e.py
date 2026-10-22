"""Windows end-to-end check: inspector -> planner -> crawler against FakeApp.exe.

Run on Windows after compiling FakeApp.cs: python tests/windows_e2e/run_e2e.py <FakeApp.exe> <work dir>
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def control(name, code=None, event='18', children=(), indent=2):
    pad = ' ' * indent
    lines = [f'{pad}-', f'{pad}  name : {name}']
    if code is not None:
        body = '\n'.join(f'{pad}       {line}' for line in code.splitlines())
        lines += [f'{pad}  code_elements :', f'{pad}   p_codes :', f'{pad}    -', f'{pad}      code : |1-', body,
                  f'{pad}      type : {event}']
    if children:
        lines.append(f'{pad}  controls :')
        lines += [c(indent + 3) for c in children]
    return '\n'.join(lines)


def node(name, code=None, event='18', children=()):
    return lambda indent: control(name, code, event, children, indent)


def window(name, controls=(), declarations='PROCEDURE MyWindow()'):
    text = [f'window :', f' name : {name}', ' controls :'] + [c(2) for c in controls]
    text += [' code_elements :', '  p_codes :', '   -', '     code : |1-', f'      {declarations}']
    return '\n'.join(text) + '\n'


SOURCES = {
    'WIN_MENU.wdw': window('WIN_MENU', [
        node('MENU__Menu', children=[
            node('OPT_Tabelas', children=[node('OPT_Clientes', 'Open(WIN_Clientes)', '32')]),
            node('OPT_Utilitários', children=[node('OPT_Reconstrução_de_Stocks', 'HModify(stock)', '32')])]),
        node('BTN_Viaturas', 'Open(WIN_Viaturas)')]),
    'WIN_Clientes.wdw': window('WIN_Clientes', [node('Btn_New', 'HReset(Clientes)\nOpen(WIN_Ficha)')]),
    'WIN_Ficha.wdw': window('WIN_Ficha'),
    'WIN_Viaturas.wdw': window('WIN_Viaturas'),
    'WIN_Acesso.wdw': window('WIN_Acesso'),
}


def run(*args, check=True):
    print('>', ' '.join(str(a) for a in args), flush=True)
    result = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding='utf-8')
    print(result.stdout, result.stderr, flush=True)
    if check and result.returncode:
        raise SystemExit(f'command failed: {result.returncode}')
    return result


def fresh_copy(exe, work, name):
    folder = work / name
    folder.mkdir()
    shutil.copy(exe, folder / 'FakeApp.exe')
    (folder / 'Clientes.fic').write_bytes(b'original')
    (folder / '.migration-capture-copy').write_text('')
    return folder


def main():
    exe, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    work.mkdir(parents=True, exist_ok=False)
    sources = work / 'sources'
    sources.mkdir()
    for name, text in SOURCES.items():
        (sources / name).write_text(text, encoding='utf-8')
    run(ROOT / 'scripts/inspect_windev.py', sources, '--out', work / 'inspect')
    run(ROOT / 'scripts/plan_capture.py', work / 'inspect', '--out', work / 'plan.json')
    levels = {w['window']: w['capture'] for w in json.loads((work / 'plan.json').read_text(encoding='utf-8'))['windows']}
    failures = []
    expect = {'WIN_Clientes': 'auto', 'WIN_Viaturas': 'auto', 'WIN_Ficha': 'auto-review'}
    for window_name, level in expect.items():
        if levels.get(window_name) != level:
            failures.append(f'plan: {window_name} is {levels.get(window_name)}, expected {level}')

    os.environ.update(MIGRATION_APP_USER='tester', MIGRATION_APP_PASSWORD='not-a-secret', FAKE_EXPECTED_USER='tester')
    crawler = ROOT / 'scripts/windows/capture_app.py'
    common = ['--exe', 'FakeApp.exe', '--plan', work / 'plan.json', '--login', '--timeout', '10']

    probe_dir = fresh_copy(exe, work, 'probe-copy')
    run(crawler, '--app-dir', probe_dir, '--out', work / 'probe', '--probe', '--allow-review', *common)
    verdict = json.loads((work / 'probe' / 'probe.json').read_text(encoding='utf-8'))
    if not verdict['verdict'].startswith('go'):
        failures.append(f'probe: {verdict}')

    first = fresh_copy(exe, work, 'copy-1')
    run(crawler, '--app-dir', first, '--out', work / 'pass-1', *common, check=False)
    report = json.loads((work / 'pass-1' / 'capture-report.json').read_text(encoding='utf-8'))
    clientes = report['windows'].get('WIN_Clientes', {})
    if clientes.get('result') != 'captured':
        failures.append(f'pass 1: WIN_Clientes not captured: {clientes}')
    for artifact in ('screenshot.png', 'tree.json', 'tab-order.json'):
        if not (work / 'pass-1' / 'WIN_Clientes' / artifact).exists():
            failures.append(f'pass 1: missing WIN_Clientes/{artifact}')
    tab_order = work / 'pass-1' / 'WIN_Clientes' / 'tab-order.json'
    if tab_order.exists() and len(json.loads(tab_order.read_text(encoding='utf-8'))) < 3:
        failures.append('pass 1: tab order has fewer than 3 stops')
    if 'Clientes.fic' not in report['windows'].get('WIN_Viaturas', {}).get('data_changed', []) or not report['stopped']:
        failures.append(f'pass 1: data guard did not stop after WIN_Viaturas: {report}')

    second = fresh_copy(exe, work, 'copy-2')
    run(crawler, '--app-dir', second, '--out', work / 'pass-2', '--allow-review', *common, check=False)
    report = json.loads((work / 'pass-2' / 'capture-report.json').read_text(encoding='utf-8'))
    ficha = report['windows'].get('WIN_Ficha', {})
    if ficha.get('result') != 'captured' or not (work / 'pass-2' / 'WIN_Ficha' / '_on_close' / 'screenshot.png').exists():
        failures.append(f'pass 2: WIN_Ficha or its close dialog not captured: {ficha}')
    if report['windows'].get('WIN_Clientes', {}).get('result') != 'captured':
        failures.append('pass 2: WIN_Clientes not captured after restart')

    print('\n'.join(failures) or 'end-to-end OK')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
