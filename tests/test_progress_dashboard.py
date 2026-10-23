import csv
from pathlib import Path
import subprocess
import tempfile
import unittest

from helpers import load

module = load('scripts/progress_dashboard.py')
COLUMNS = ['id', 'kind', 'element', 'context', 'event', 'evidence', 'confidence', 'legacy_behavior',
           'target_behavior', 'implemented_in', 'test', 'decision', 'status']


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({c: r.get(c, '') for c in COLUMNS} for r in rows)


class ProgressDashboardTests(unittest.TestCase):
    def test_stages_counts_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = lambda *a: subprocess.run(['git', '-C', str(root), *a], check=True, capture_output=True)
            git('init', '-q')
            git('config', 'user.email', 't@t')
            git('config', 'user.name', 't')
            seed = [{'id': f'SRC-{i}', 'kind': k, 'element': e, 'status': 'unmapped'}
                    for i, (k, e) in enumerate([('window', 'WIN_A'), ('window', 'WIN_A'), ('window', 'WIN_B'),
                                                ('report', 'RPT_C'), ('table', 'Clientes')])]
            write(root / 'docs/parity/parity-seed.csv', seed)
            git('add', 'docs')
            git('commit', '-qm', 'seed')
            write(root / 'docs/parity/WIN_A.csv', [dict(seed[0], status='verified'), dict(seed[1], status='excluded')])
            write(root / 'docs/parity/WIN_B.csv', [dict(seed[2], status='implemented')])
            (root / 'docs/mapping').mkdir()
            (root / 'docs/mapping/RPT_C.md').write_text('U-RC-01 open\n', encoding='utf-8')
            (root / 'docs/evidence').mkdir()
            (root / 'docs/evidence/encoded-actions.md').write_text(
                '| A-1 | 3 (BTN_X) | WIN_A.BTN_X | closes | WINDEV | Ana |\n| A-2 | 1 (BTN_Y) | WIN_B.BTN_Y | | | |\n'
                '| Q-01 | Esc? | | | |\n', encoding='utf-8')
            git('add', 'docs')
            git('commit', '-qm', 'stage 1')
            page, units = module.build(root / 'docs', 'Test')
        stages = {u['name']: u['stage'] for u in units}
        self.assertEqual(stages, {'WIN_A': 'done', 'WIN_B': 'building', 'RPT_C': 'mapped', 'Clientes': 'not started'})
        self.assertIn('40.0%', page)  # 2 of 5 behaviors done
        self.assertIn('<div class="big">2</div><div>assumptions to confirm with the WINDEV expert (work does not wait)</div>', page)
        self.assertIn('<polyline', page)  # two commits touched the parity files
        self.assertIn('stage 1', page)


if __name__ == '__main__':
    unittest.main()
