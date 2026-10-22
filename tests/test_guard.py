import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from helpers import load

module = load('templates/agent/guard.py')


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        migrations = self.root / 'src-tauri/migrations'
        migrations.mkdir(parents=True)
        (migrations / '0001_init.sql').write_text('CREATE TABLE a (id INTEGER);')
        subprocess.run(['git', 'add', 'src-tauri/migrations/0001_init.sql'], cwd=self.root, check=True)

    def tearDown(self):
        self.directory.cleanup()

    def decide(self, tool, **data):
        return module.decide({'tool_name': tool, 'tool_input': data}, self.root)

    def test_blocks_forbidden_actions(self):
        cases = [
            self.decide('Edit', file_path=str(self.root / 'legacy/WIN_A.wdw'), new_string='x'),
            self.decide('Write', file_path='src-tauri/migrations/0001_init.sql', content='x'),
            self.decide('Write', file_path='src-tauri/migrations/0002_x.sql', content='DROP TABLE a;'),
            self.decide('Write', file_path='src/bindings/commands.ts', content='x'),
            self.decide('Write', file_path='src/config.ts', content='const k = "ghp_' + 'a' * 36 + '"'),
            self.decide('Bash', command='git push --force origin main'),
            self.decide('Bash', command='git add -A'),
            self.decide('Bash', command='git commit -am "wip"'),
            self.decide('Bash', command='rm -rf legacy'),
            self.decide('Bash', command='git commit --no-verify -m x'),
        ]
        self.assertTrue(all(cases), cases)

    def test_allows_normal_work(self):
        cases = [
            self.decide('Write', file_path='src-tauri/migrations/0002_add.sql', content='ALTER TABLE a ADD b TEXT;'),
            self.decide('Edit', file_path='src/domain/order.ts', new_string='const password = input.password;'),
            self.decide('Bash', command='git add src/domain/order.ts && git commit -m "Add order totals"'),
            self.decide('Bash', command='git commit --amend --no-edit'),
            self.decide('Read', file_path='legacy/WIN_A.wdw'),
        ]
        self.assertEqual(cases, [None] * len(cases))


    def git(self, *args):
        subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

    def test_staged_mode_reports_every_violation(self):
        self.git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init')
        (self.root / 'legacy').mkdir()
        (self.root / 'legacy/WIN_A.wdw').write_text('x')
        (self.root / 'ORDERS.FIC').write_bytes(b'data')
        (self.root / '.env.local').write_text('A=1')
        (self.root / '.env.example').write_text('A=')
        (self.root / 'src-tauri/migrations/0001_init.sql').write_text('CREATE TABLE b (id INTEGER);')
        (self.root / 'src-tauri/migrations/0002_drop.sql').write_text('DROP TABLE a;')
        (self.root / 'config.ts').write_text('const c = "Server=x;Password=hunter22;"')
        self.git('add', '-f', 'legacy/WIN_A.wdw', 'ORDERS.FIC', '.env.local', '.env.example',
                 'src-tauri/migrations', 'config.ts')
        problems = '\n'.join(module.check_staged(self.root))
        for expected in ('legacy/WIN_A.wdw is private', 'ORDERS.FIC must not', '.env.local must not',
                         '0001_init.sql is an existing migration', '0002_drop.sql contains destructive',
                         'config.ts adds content'):
            self.assertIn(expected, problems)
        self.assertNotIn('.env.example', problems)

    def test_staged_mode_allows_clean_commit(self):
        (self.root / 'src').mkdir()
        (self.root / 'src/order.ts').write_text('export const total = 1;')
        self.git('add', 'src/order.ts')
        self.assertEqual(module.check_staged(self.root), [])

    def test_cli_modes(self):
        script = str(Path(module.__file__))
        run = lambda *a, **k: subprocess.run([sys.executable, script, *a], cwd=self.root,
                                              capture_output=True, text=True, **k).returncode
        self.assertEqual(run('--command', 'git push --force'), 2)
        self.assertEqual(run('--command', 'npm test'), 0)
        self.assertEqual(run('--write', 'legacy/x.wdw', input='x'), 2)
        self.assertEqual(run('--hook', input=json.dumps({'tool_name': 'Bash', 'cwd': str(self.root),
                                                         'tool_input': {'command': 'git add .'}})), 2)
        self.assertEqual(run('--staged'), 0)


if __name__ == '__main__':
    unittest.main()
