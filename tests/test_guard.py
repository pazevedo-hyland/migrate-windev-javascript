from pathlib import Path
import subprocess
import tempfile
import unittest

from helpers import load

module = load('templates/claude/hooks/guard.py')


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


if __name__ == '__main__':
    unittest.main()
