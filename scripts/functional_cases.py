#!/usr/bin/env python3
"""Build docs/functional-acceptance.json from one executed test run and the parity matrix's test citations.

One case per screen/report (`FC-<unit>`): its witnesses are the tests cited (`file::title`) by the unit's `verified`
parity rows. A case is `verified` only when every one of those tests is in the run and passed; a failing or absent
cited test, or a unit whose verified rows cite none, keeps it `pending` with the reason. The run records OS, commit and
the commands actually executed; scripts/functional_acceptance.py then checks the file and re-checks that the
application and tests have not changed since that commit.

  python3 scripts/functional_cases.py --vitest vitest.json --playwright playwright.json \\
     --commit "$(git rev-parse HEAD)" --os "Windows 11 x64" \\
     --command "npx vitest run --reporter=json --outputFile=vitest.json" \\
     --command "npx playwright test --reporter=json > playwright.json"

Produce the reports from the same commit, with a clean worktree, in one run. Cases this tool did not generate (IDs not
starting with FC-) and `platform` entries already in the file are kept with the runs they cite. This derives cases
from parity citations: it does not decide the approved functional scope — review the requirements before relying on
them, and keep strict parity, source questions and platform evidence separate.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from functional_acceptance import check_key  # noqa: E402
from progress_dashboard import matrix_rows, summarize  # noqa: E402

PREFIX = 'FC-'


def relative(path, root):
    return os.path.relpath(Path(path).resolve(), root).replace('\\', '/')


def vitest_results(path, root):
    """{file::title: passed} from Vitest's JSON reporter; titles also with their describe blocks."""
    results = {}
    for file in json.loads(Path(path).read_text(encoding='utf-8'))['testResults']:
        name = relative(file['name'], root)
        for test in file['assertionResults']:
            passed = test['status'] == 'passed'
            ancestors = test.get('ancestorTitles', [])
            for title in {test['title'], ' > '.join([*ancestors, test['title']]), ' '.join([*ancestors, test['title']])}:
                results[f'{name}::{title}'] = results.get(f'{name}::{title}', True) and passed
    return results


def playwright_results(path, root):
    """{file::title: passed} from Playwright's JSON reporter (last retry counts); titles also with describe blocks."""
    data, results = json.loads(Path(path).read_text(encoding='utf-8')), {}
    base = Path(data.get('config', {}).get('rootDir') or root)

    def walk(suite, parents):
        for spec in suite.get('specs', []):
            file = relative(base / spec['file'], root)
            passed = bool(spec['tests']) and all(result['status'] == 'passed'
                                                 for test in spec['tests'] for result in test['results'][-1:])
            for title in {spec['title'], ' > '.join([*parents, spec['title']])}:
                results[f'{file}::{title}'] = results.get(f'{file}::{title}', True) and passed
        for child in suite.get('suites', []):
            title = child.get('title', '')
            walk(child, [*parents, title] if title and not title.endswith(('.ts', '.js', '.tsx', '.mjs')) else parents)

    for suite in data.get('suites', []):
        walk(suite, [])
    return results


def citations(row):
    return {t.strip() for t in (row.get('test') or '').split(';') if '::' in t}


def build(root, results, run, previous=None, kinds=('screen', 'report'), run_id='full-suite'):
    """Return the acceptance document; `results` maps file::title to passed."""
    root = Path(root).resolve()
    docs = root / 'docs'
    files = {p.name: p.read_text(encoding='utf-8') for p in (docs / 'parity').glob('*.csv')}
    rows = matrix_rows(files)
    units = [u for u in summarize(rows, docs) if u['kind'] in kinds]
    cases, executed = [], set()
    for unit in sorted(units, key=lambda u: u['name']):
        cited = sorted({t for r in rows if r.get('element') == unit['name'] and (r.get('status') or '').strip() == 'verified'
                        for t in citations(r)})
        known = [t for t in cited if t in results]
        failing = [t for t in known if not results[t]]
        checks = [t for t in known if results[t]]
        for key in checks:
            file, _, title = key.partition('::')
            check_key({'file': file, 'title': title})
        executed.update(checks)
        case = {'id': PREFIX + unit['name'], 'units': [unit['name']],
                'requirement': f'Normal workflows of {unit["name"]}: the behaviours of its verified parity rows pass '
                               f'through the real application path.',
                'checks': [{'file': t.split('::', 1)[0], 'title': t.split('::', 1)[1]} for t in checks]}
        missing = [t for t in cited if t not in results]
        if checks and not failing and not missing:
            case.update(status='verified', evidence=[{'run': run_id, 'os': run['os'], 'commit': run['commit']}])
        else:
            case.update(status='pending', evidence=[], gap='; '.join(filter(None, (
                f'{len(failing)} cited test(s) failed in the run' if failing else '',
                f'{len(missing)} cited test(s) absent from the run (renamed, skipped or not executed)' if missing else '',
                'no verified parity row of this unit cites a test yet' if not cited else ''))) + '.')
        cases.append(case)
    previous = previous or {}
    kept = [c for c in previous.get('cases', []) if not str(c.get('id', '')).startswith(PREFIX)]
    platform = previous.get('platform', [])
    cited_runs = {e.get('run') for item in kept + platform for e in item.get('evidence', [])}
    runs = {k: v for k, v in previous.get('runs', {}).items() if k in cited_runs and k != run_id}
    runs[run_id] = {**run, 'checks': sorted(executed),
                    'results': f'{sum(results.values())} passing and {sum(not v for v in results.values())} failing '
                               f'test titles in the reports.'}
    document = {'version': 1}
    for key in ('decision', 'scope'):
        if key in previous:
            document[key] = previous[key]
    document.update(runs=runs, cases=cases + kept, platform=platform)
    return document


def resolve_commit(root, commit):
    """The validator accepts only a full 40-hex SHA: a short one makes every case silently unassessed (0 %)."""
    if re.fullmatch(r'[0-9a-f]{40}', commit):
        return commit
    out = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', commit + '^{commit}'],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f'--commit {commit!r} is not a commit of {root}')
    return out.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='application repository (default: current folder)')
    parser.add_argument('--vitest', action='append', default=[], help='Vitest JSON report (repeatable)')
    parser.add_argument('--playwright', action='append', default=[], help='Playwright JSON report (repeatable)')
    parser.add_argument('--commit', required=True, help='tested commit (a short SHA or ref is resolved to the full SHA)')
    parser.add_argument('--os', required=True, help='e.g. "Windows 11 x64"')
    parser.add_argument('--command', action='append', required=True, help='a command that produced the reports (repeatable)')
    parser.add_argument('--run-id', default='full-suite')
    parser.add_argument('--out', type=Path, help='default: <root>/docs/functional-acceptance.json')
    args = parser.parse_args()
    if not args.vitest and not args.playwright:
        parser.error('give at least one --vitest or --playwright report')
    root = args.root.resolve()
    args.commit = resolve_commit(root, args.commit)
    results = {}
    for report in args.vitest:
        results.update(vitest_results(report, root))
    for report in args.playwright:
        results.update(playwright_results(report, root))
    out = args.out or root / 'docs' / 'functional-acceptance.json'
    previous = json.loads(out.read_text(encoding='utf-8')) if out.exists() else None
    run = {'os': args.os, 'commit': args.commit, 'date': datetime.date.today().isoformat(), 'commands': args.command}
    document = build(root, results, run, previous, run_id=args.run_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    generated = [c for c in document['cases'] if c['id'].startswith(PREFIX)]
    print(f'{sum(c["status"] == "verified" for c in generated)}/{len(generated)} generated cases verified -> {out}')


if __name__ == '__main__':
    main()
