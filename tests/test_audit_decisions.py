import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, load

module = load('scripts/audit_decisions.py')

AUDIT = {'summary': {}, 'elements': [
    {'unit': 'WIN_A', 'name': 'BTN_Save', 'line': 9, 'variant': 'wdw/controls/4/0.14', 'length': 100,
     'differences': [{'position': 128, 'value': '01', 'usual': '05'}, {'position': 300, 'value': 'ff0000', 'usual': '000000'}]},
    {'unit': 'WIN_A', 'name': 'BTN_Save', 'line': 9, 'variant': 'wdw/controls/4/1.0', 'length': 30,
     'differences': [{'position': 2, 'value': 'aa', 'usual': 'bb'}]},          # a link chunk: not a designer property
    {'unit': 'WIN_A', 'name': '', 'line': 40, 'variant': 'wdw/window//0.14', 'length': 10,
     'differences': [{'position': 1, 'value': '01', 'usual': '00'}]},          # unnamed: nothing to decide on
    {'unit': 'WIN_B', 'name': 'EDT_Name', 'line': 5, 'variant': 'wdw/controls/2/0.14', 'length': 100,
     'differences': [{'position': 7, 'value': '02', 'usual': '00'}]}]}


class AuditDecisions(unittest.TestCase):
    def run_tool(self, folder, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/audit_decisions.py'), '--audit', str(Path(folder, 'audit.json')),
                               '--decisions', str(Path(folder, 'decisions.csv')), *args], capture_output=True, text=True)

    def test_findings_keep_designer_chunks_of_named_elements(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'audit.json').write_text(json.dumps(AUDIT), encoding='utf-8')
            found = module.findings(Path(folder, 'audit.json'))
        self.assertEqual(found, {('WIN_A', 'BTN_Save'): '128:01/05 300:ff0000/000000', ('WIN_B', 'EDT_Name'): '7:02/00'})

    def test_init_decide_gate_and_stale_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'audit.json').write_text(json.dumps(AUDIT), encoding='utf-8')
            self.assertEqual(self.run_tool(folder, '--require-complete').returncode, 1)     # nothing decided yet
            first = self.run_tool(folder, '--init')
            self.assertEqual(json.loads(first.stdout.splitlines()[0]),
                             {'controls_with_differences': 2, 'decided': 0, 'undecided': 2, 'stale': 0})
            rows = module.read_rows(Path(folder, 'decisions.csv'))
            rows[0]['decision'] = 'image has one state, text is red: reproduced'
            with Path(folder, 'decisions.csv').open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=module.COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(self.run_tool(folder, '--require-complete', '--unit', 'WIN_A').returncode, 0)
            unit = self.run_tool(folder, '--require-complete', '--unit', 'win_b')
            self.assertEqual(unit.returncode, 1)
            self.assertIn('undecided: WIN_B/EDT_Name: 7:02/00', unit.stdout)
            # --init again keeps the decision and adds nothing.
            self.run_tool(folder, '--init')
            self.assertEqual(module.read_rows(Path(folder, 'decisions.csv')), rows)
            # The source changed: the decided control differs elsewhere now, so its decision no longer covers it.
            changed = json.loads(json.dumps(AUDIT))
            changed['elements'][0]['differences'].append({'position': 400, 'value': '09', 'usual': '00'})
            Path(folder, 'audit.json').write_text(json.dumps(changed), encoding='utf-8')
            stale = self.run_tool(folder, '--require-complete', '--unit', 'WIN_A')
            self.assertEqual(stale.returncode, 1)
            self.assertIn('stale: WIN_A/BTN_Save', stale.stdout)


if __name__ == '__main__':
    unittest.main()
