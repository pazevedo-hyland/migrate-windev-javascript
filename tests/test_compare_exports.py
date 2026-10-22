import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, load

module = load('scripts/compare_exports.py')


class CompareExportsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / 'legacy').mkdir()
        (self.root / 'target').mkdir()
        self.config = {
            'legacy': {'delimiter': ';', 'encoding': 'cp1252'},
            'tables': {'ORDERS': {
                'key': ['id'], 'rename': {'IDCommande': 'id', 'Montant': 'total', 'Client': 'customer'},
                'ignore': ['Horodatage'],
                'columns': {'total': {'decimal': True, 'decimal_places': 2},
                            'ordered_on': {'date_formats': ['%d/%m/%Y', '%Y-%m-%d']}}}}}

    def tearDown(self):
        self.directory.cleanup()

    def write(self, side, text, encoding='utf-8'):
        (self.root / side / 'ORDERS.csv').write_text(text, encoding=encoding)

    def test_equal_after_declared_normalization(self):
        self.write('legacy', 'IDCommande;Montant;Client;ordered_on;Horodatage\n1;12,5;Hélène;02/01/2026;x\n', 'cp1252')
        self.write('target', 'id,total,customer,ordered_on\n1,12.50,Hélène,2026-01-02\n')
        report = module.compare(self.config, self.root / 'legacy', self.root / 'target')
        self.assertTrue(report['equal'], report)

    def test_reports_missing_extra_and_mismatch(self):
        self.write('legacy', 'IDCommande;Montant;Client;ordered_on\n1;12,5;Ana;02/01/2026\n2;3;Rui;02/01/2026\n', 'cp1252')
        self.write('target', 'id,total,customer,ordered_on\n1,12.51,ana,2026-01-02\n3,1,Eva,2026-01-02\n')
        table = module.compare(self.config, self.root / 'legacy', self.root / 'target')['tables']['ORDERS']
        self.assertEqual((table['missing_in_target'], table['extra_in_target']), (1, 1))
        self.assertEqual(sorted(m['column'] for m in table['samples']['mismatches']), ['customer', 'total'])
        self.assertFalse(table['equal'])

    def test_cli_exit_code(self):
        self.write('legacy', 'IDCommande;Montant;Client;ordered_on\n1;1;A;02/01/2026\n', 'cp1252')
        self.write('target', 'id,total,customer,ordered_on\n1,2,A,2026-01-02\n')
        (self.root / 'config.json').write_text(json.dumps(self.config), encoding='utf-8')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/compare_exports.py'), '--config',
                                 str(self.root / 'config.json'), '--legacy', str(self.root / 'legacy'),
                                 '--target', str(self.root / 'target')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)


if __name__ == '__main__':
    unittest.main()
