#!/usr/bin/env python3
"""Assess declared functional checks; never change source confidence or strict parity."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

# A docs/report-only commit retains business evidence. Changed application/tests need a new run.
CODE_PATHS = ('src', 'packages', 'apps', 'src-tauri', 'ui-check', 'package.json',
              'package-lock.json', 'vite.config.ts', 'vitest.config.ts', 'rust-toolchain.toml',
              'public', 'ui-check.config.json', 'tsconfig.json', 'tsconfig.tools.json',
              'setup/requirements.txt', ':(glob)scripts/native*.mjs', 'docs/golden',
              'docs/evidence/message-proposals.json', 'docs/evidence/ui-inputs.json')


def compatible_commit(root, commit, test_files=()):
    def git(*args):
        return subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    paths = (*CODE_PATHS, *test_files)
    untracked = git('ls-files', '--others', '--exclude-standard', '--', *paths)
    return (bool(re.fullmatch(r'[0-9a-f]{40}', commit or ''))
            and git('cat-file', '-e', commit + '^{commit}').returncode == 0
            and git('merge-base', '--is-ancestor', commit, 'HEAD').returncode == 0
            and git('diff', '--quiet', commit, '--', *paths).returncode == 0
            and untracked.returncode == 0 and not untracked.stdout.strip())


def check_key(check):
    file, title = check.get('file', ''), check.get('title', '')
    path = PurePosixPath(file)
    if (not file or path.is_absolute() or '..' in path.parts or '\\' in file
            or not isinstance(title, str) or not title.strip()):
        raise ValueError('Each test needs a repository-relative file and exact executed title')
    return file + '::' + title


def assess_data(data, names, root, compatible=compatible_commit):
    """Validate evidence, derive effective results, and retain omitted units in the denominator."""
    if data.get('version') != 1:
        raise ValueError('Unsupported functional acceptance version')
    names, root = set(names), Path(root).resolve()
    runs = data.get('runs', {})
    valid = {}
    for ident, run in runs.items():
        if not run.get('os') or not run.get('commit') or not run.get('commands'):
            raise ValueError(f'{ident}: run requires OS, commit and executed commands')
        keys = run.get('checks', [])
        if not isinstance(keys, list) or len(keys) != len(set(keys)):
            raise ValueError(f'{ident}: duplicate or malformed executed checks')
        test_files = []
        for key in keys:
            file, separator, title = key.partition('::')
            if not separator:
                raise ValueError(f'{ident}: executed checks require file::title')
            check_key({'file': file, 'title': title})
            test_files.append(file)
        valid[ident] = compatible(root, run['commit'], test_files)

    ids, records = set(), []
    def assess_item(item, platform=False):
        ident = item.get('id')
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError(f'Duplicate or missing acceptance ID: {ident}')
        ids.add(ident)
        units = item.get('units', [])
        if len(set(units)) != len(units) or not set(units) <= names or (not units and not platform):
            raise ValueError(f'{ident}: unknown, duplicate or missing units')
        if not item.get('requirement') or item.get('status') not in {'verified', 'pending'}:
            raise ValueError(f'{ident}: requirement and verified/pending status are required')
        if platform and not item.get('os'):
            raise ValueError(f'{ident}: platform capability requires an OS')
        checks = [check_key(c) for c in item.get('checks', [])]
        if len(checks) != len(set(checks)):
            raise ValueError(f'{ident}: duplicate test witness')
        for check in item.get('checks', []):
            file = (root / check['file']).resolve()
            if not file.is_relative_to(root) or not file.is_file():
                raise ValueError(f'{ident}: test file is missing or outside the repository')
        covered, environments, stale = set(), set(), False
        for evidence in item.get('evidence', []):
            run_id = evidence.get('run')
            if run_id not in runs:
                raise ValueError(f'{ident}: unknown evidence run {run_id}')
            run = runs[run_id]
            if evidence.get('os') != run['os'] or evidence.get('commit') != run['commit']:
                raise ValueError(f'{ident}: witness OS/commit differs from its executed run')
            if platform and run['os'] != item['os']:
                raise ValueError(f'{ident}: another host cannot prove this platform capability')
            if valid[run_id]:
                covered.update(run['checks'])
                environments.add(run['os'])
            else:
                stale = True
        status, reason = item['status'], item.get('gap', '')
        if status == 'verified':
            if not checks or not item.get('evidence'):
                raise ValueError(f'{ident}: verified requires real test witnesses and run evidence')
            declared = {key for e in item['evidence'] for key in runs[e['run']]['checks']}
            if not set(checks) <= declared:
                raise ValueError(f'{ident}: cited test was not attested as executed')
            if not set(checks) <= covered:
                status, reason = 'pending', 'Application/test files changed since the cited run; rerun these checks.'
        elif not reason:
            raise ValueError(f'{ident}: pending requires a concrete remaining obligation')
        return {**item, 'status': status, 'gap': reason, 'environments': sorted(environments), 'stale': stale}

    for item in data.get('cases', []):
        records.append(assess_item(item))
    covered_units = {name for item in records for name in item['units']}
    for name in sorted(names - covered_units):
        records.append({'id': 'unassessed:' + name, 'units': [name],
                        'requirement': 'Declare and verify the normal functional acceptance scope.',
                        'status': 'pending', 'gap': 'Functional acceptance has not been scoped for this unit.',
                        'checks': [], 'evidence': [], 'environments': [], 'stale': False})
    platform = [assess_item(item, platform=True) for item in data.get('platform', [])]
    by_unit = {}
    for name in sorted(names):
        cases = [r for r in records if name in r['units']]
        passed = sum(r['status'] == 'verified' for r in cases)
        by_unit[name] = {'passed': passed, 'total': len(cases),
                         'status': 'verified' if cases and passed == len(cases) else 'pending',
                         'cases': [r['id'] for r in cases]}
    passed = sum(r['status'] == 'verified' for r in records)
    return {'assessed': bool(data.get('cases')), 'passed': passed, 'total': len(records),
            'percent': round(100 * passed / len(records), 1) if records else 0.0,
            'environments': sorted({env for r in records for env in r['environments']}),
            'units': by_unit, 'cases': records, 'platform': platform}


def assess(docs, units, root=None):
    docs = Path(docs)
    names = [u['name'] for u in units if u['kind'] in {'screen', 'report'}]
    file = docs / 'functional-acceptance.json'
    data = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {'version': 1}
    return assess_data(data, names, root or docs.parent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docs', type=Path, default=Path('docs'))
    parser.add_argument('--check', action='store_true', help='validate scope/evidence without changing any results')
    parser.add_argument('--require-complete', action='store_true', help='fail until every required functional case passes')
    args = parser.parse_args()
    from progress_dashboard import matrix_rows, summarize
    files = {p.name: p.read_text(encoding='utf-8') for p in (args.docs / 'parity').glob('*.csv')}
    try:
        result = assess(args.docs, summarize(matrix_rows(files), args.docs))
    except (ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'cases', 'platform', 'units'}}, indent=2))
    if args.require_complete and (not result['assessed'] or result['passed'] != result['total']):
        parser.exit(1, 'Required functional acceptance checks remain pending.\n')


if __name__ == '__main__':
    main()
