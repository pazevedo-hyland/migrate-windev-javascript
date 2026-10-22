import csv
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/status.py')

PARITY = '''id,kind,element,evidence,confidence,status,ticket,context,event
A1,window,WIN_Order,a.wdw:1-2,verified,verified,MIG-1,WIN_Order/BTN_Save,851977
A2,window,WIN_Order,a.wdw:3-4,inferred,specified,MIG-1,,
A3,window,WIN_Order,a.wdw:5-6,unresolved,unmapped,,,
B1,report,RPT_Invoice,b.wde:1-9,unresolved,unmapped,,,
C1,table,ORDERS,s.xdd,verified,excluded,,,
'''

ROADMAP = '''# ROADMAP

| # | Phase | Slice | Status |
|---|---|---|---|
| 0 | Framing | Mapping | Done |
| 1 | Slice | Orders | In progress |
| 2 | Slice | Invoices | Blocked |

Statuses: To do / Done.
'''


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / 'parity.csv').write_text(PARITY, encoding='utf-8')
        (self.root / 'ROADMAP.md').write_text(ROADMAP, encoding='utf-8')

    def tearDown(self):
        self.directory.cleanup()

    def test_summary_by_element_and_roadmap(self):
        rows = module.read_parity(self.root / 'parity.csv')
        summary = module.summarize(rows, module.read_roadmap(self.root / 'ROADMAP.md'))
        self.assertEqual(summary['complete_percent'], 40.0)
        self.assertEqual(summary['unresolved_legacy_behavior'], 2)
        order = next(e for e in summary['elements'] if e['element'] == 'WIN_Order')
        self.assertEqual((order['rows'], order['complete_percent'], order['tickets']), (3, 33.3, ['MIG-1']))
        self.assertEqual(summary['roadmap']['statuses'], {'Done': 1, 'In progress': 1, 'Blocked': 1})
        self.assertEqual([o['slice'] for o in summary['roadmap']['open']], ['Orders', 'Invoices'])
        text = module.markdown(summary)
        self.assertIn('**Parity: 40.0% complete**', text)
        self.assertIn('| report | RPT_Invoice | 1 | 1 |', text)

    def test_work_items_only_for_untracked_open_rows(self):
        items = module.work_items(module.read_parity(self.root / 'parity.csv'), 'windev-migration')
        self.assertEqual([i['Parity IDs'] for i in items], ['B1', 'A3'])
        module.write_work_items(items, self.root / 'items.csv')
        with (self.root / 'items.csv').open(encoding='utf-8') as handle:
            table = list(csv.reader(handle))
        self.assertEqual(table[0], ['Summary', 'Issue Type', 'Description', 'Labels', 'Labels', 'Parity IDs'])
        self.assertEqual(table[1][3:5], ['windev-migration', 'report'])
        self.assertIn('B1 [unmapped]', table[1][2])


if __name__ == '__main__':
    unittest.main()
