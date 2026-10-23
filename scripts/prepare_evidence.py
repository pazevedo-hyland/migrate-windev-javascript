#!/usr/bin/env python3
"""Run the whole evidence pipeline in the right order, with consistent paths: stage 0 in one command.

  inspect_windev.py   legacy/              -> analysis-local/inspect-<stamp>/   (code, layout, encoded slots, XDD, seed)
                                           -> docs/parity/parity-seed.csv      (committed copy, for the parity gate)
  dossier_extract.py  legacy/**/*Documentation*.pdf -> analysis-local/dossier-<stamp>/ (when a dossier exists)
  event_legend.py     legacy/**/<project>.cpl        -> docs/mapping/event-codes.md     (when the compile folder exists)
  evidence_report.py                       -> docs/evidence-report.md, docs/navigation.md
  schema_draft.py                          -> docs/schema/schema-draft.md, .sql
  render_layouts.py                        -> analysis-local/layouts-<stamp>/
  images                                   -> docs/evidence/images/  (dossier images + layout drawings, committed)

Every run writes fresh dated folders (the inspector refuses to reuse one) and records them in
analysis-local/latest.json, so prompts can say "the paths in latest.json". Generated docs are overwritten.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def run(script, *args):
    command = [sys.executable, str(HERE / script), *map(str, args)]
    print('$', ' '.join(command[1:]), flush=True)
    result = subprocess.run(command, capture_output=True, text=True)
    sys.stderr.write(result.stderr)
    if result.returncode:
        sys.stdout.write(result.stdout)
        raise SystemExit(f'{script} failed (exit {result.returncode})')
    return result.stdout


def publish_images(dossier, layouts, target):
    """Copy the visual evidence specs cite into docs/ (committed), so agents on other machines see it: the dossier
    image of each window, report and query, and each window's layout drawing. Raw extracts stay in analysis-local/:
    they hold code and are regenerated from legacy/."""
    target.mkdir(parents=True, exist_ok=True)
    sources = list(Path(dossier, 'images').glob('*')) if dossier else []
    sources += [p for p in Path(layouts).glob('*.svg')]
    for source in sources:
        destination = target / source.name
        if not destination.exists() or destination.read_bytes() != source.read_bytes():
            shutil.copyfile(source, destination)
    return str(target)


def prepare(legacy, analysis, docs, dossier_pdf=None, compile_dir=None, language=None, images=True):
    legacy, analysis, docs = Path(legacy), Path(analysis), Path(docs)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    # The fixed layout first (00 §E), else anywhere under legacy/: the WINDEV project folder can be dropped in as is.
    find = lambda pattern, preferred: next(iter(sorted(preferred)), None) or next(iter(sorted(Path(legacy).rglob(pattern))), None)
    dossier_pdf = dossier_pdf or find('*[Dd]ocumentation*.pdf', Path(legacy, 'docs').glob('*[Dd]ocumentation*.pdf'))
    compile_dir = compile_dir or next(iter(sorted(p for p in [*Path(legacy, 'code').glob('*.cpl'), *Path(legacy).rglob('*.cpl')]
                                                   if p.is_dir())), None)
    paths = {'stamp': stamp, 'legacy': str(legacy), 'inspect': str(analysis / f'inspect-{stamp}')}
    (docs / 'mapping').mkdir(parents=True, exist_ok=True)
    (docs / 'schema').mkdir(parents=True, exist_ok=True)
    run('inspect_windev.py', legacy, '--out', paths['inspect'])
    # A committed copy of the seed: the parity gate runs in CI and on machines without analysis-local/.
    (docs / 'parity').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(paths['inspect'], 'parity-seed.csv'), docs / 'parity/parity-seed.csv')
    paths['seed'] = str(docs / 'parity/parity-seed.csv')
    dossier = None
    if dossier_pdf:
        try:
            import pypdf  # noqa: F401  (only dossier_extract.py needs it)
        except ImportError:
            raise SystemExit('the dossier PDF needs pypdf: python3 -m pip install pypdf')
        dossier = paths['dossier'] = str(analysis / f'dossier-{stamp}')
        run('dossier_extract.py', dossier_pdf, '--out', dossier, *([] if images else ['--no-images']))
        paths['coverage'] = json.loads(Path(dossier, 'index.json').read_text(encoding='utf-8'))['coverage']
    else:
        print('no *Documentation*.pdf under legacy/: captions, tab order, masks and checkbox properties stay unknown')
    if compile_dir:
        run('event_legend.py', Path(compile_dir).parent, '--compile-dir', compile_dir, '--out', docs / 'mapping/event-codes.md')
        paths['event_legend'] = str(docs / 'mapping/event-codes.md')
    else:
        print('no <project>.cpl compile folder under legacy/: event codes stay inferred')
    report = run('evidence_report.py', paths['inspect'], *(['--dossier', dossier] if dossier else []),
                 *(['--compiled', docs / 'mapping/event-codes.json'] if compile_dir else []),
                 '--out', docs / 'evidence-report.md', *(['--language', language] if language else []))
    paths.update(evidence_report=str(docs / 'evidence-report.md'), navigation=str(docs / 'navigation.md'))
    if any(Path(paths['inspect'], 'schema').rglob('*.json')):
        run('schema_draft.py', paths['inspect'], *(['--dossier', dossier] if dossier else []),
            '--out', docs / 'schema/schema-draft.md')
        paths['schema_draft'] = str(docs / 'schema/schema-draft.md')
    else:
        print('no .xdd in legacy/: no schema draft (export the analysis to legacy/schema/)')
    paths['layouts'] = str(analysis / f'layouts-{stamp}')
    run('render_layouts.py', paths['inspect'], '--out', paths['layouts'], *(['--dossier', dossier] if dossier else []))
    paths['images'] = publish_images(dossier, paths['layouts'], docs / 'evidence/images')
    paths['summary'] = report.strip().splitlines()[-1] if report.strip() else ''
    analysis.mkdir(parents=True, exist_ok=True)
    (analysis / 'latest.json').write_text(json.dumps(paths, indent=2), encoding='utf-8')
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--legacy', default='legacy', help='the legacy folder (code/, schema/, docs/…)')
    parser.add_argument('--analysis', default='analysis-local', help='where dated tool outputs go (not committed)')
    parser.add_argument('--docs', default='docs', help='where generated documents go')
    parser.add_argument('--dossier-pdf', type=Path, help='default: the first *Documentation*.pdf under legacy/')
    parser.add_argument('--compile-dir', type=Path, help='default: the first *.cpl folder under legacy/')
    parser.add_argument('--language', help="the application's language for dialog texts, as WINDEV names it (pt-PT, "
                                           "fr-FR…); default: the first language of each text")
    parser.add_argument('--no-images', action='store_true', help='skip dossier images (faster)')
    args = parser.parse_args()
    paths = prepare(args.legacy, args.analysis, args.docs, args.dossier_pdf, args.compile_dir, args.language,
                    not args.no_images)
    print(json.dumps(paths, indent=2))
    warnings = (paths.get('coverage') or {}).get('warnings', [])
    for warning in warnings:
        print(f'warning: {warning}', file=sys.stderr)


if __name__ == '__main__':
    main()
