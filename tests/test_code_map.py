import json
from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/code_map.py')
inspector = load('scripts/inspect_windev.py')

WINDOW = '''info :
 name : WIN_Order
window :
 name : WIN_Order
 controls :
  -
    name : BTN_Save
    code_elements :
     p_codes :
      -
        code : |1+
         // HDelete(Customer) in a comment is not a call
         Orders.Total = 10
         Orders.Date += 1
         IF Orders.Total == 10 THEN HModify(Orders)
         HReadSeekFirst(Customer, Code, EDT_Code)
         sText is string = "FROM Product is just a caption, HAdd(Product)"
         HExecuteSQLQuery(dsLines, hQueryDefault, "SELECT * FROM OrderLine, Product WHERE x = 1")
         HExecuteSQLQuery(dsOut, hQueryDefault, "DELETE FROM OrderLine WHERE o = 1")
         HExecuteSQLQuery(dsExt, hQueryDefault, "UPDATE Cab_Vendas SET a = 1")
         FOR EACH Customer
         END
         HExecuteQuery(QRY_Totals)
         nTotal = ComputeTotal(gnRate) + MAX_LINES
         Open(WIN_Customer)
         iPrintReport(RPT_Order)
         clTax is TaxRules
         HReadFirst({sTable}, "Code")
        type : 18
 code_elements :
  p_codes :
   -
     code : |1+
      PROCEDURE LocalHelper()
      HDelete(Orders)
'''
SET = '''info :
 name : GlobalProcedures
procedure_set :
 name : GlobalProcedures
 code_elements :
  p_codes :
   -
     code : |1+
      gnRate is int
      CONSTANT
      	MAX_LINES = 20
      END
   -
     code : |1+
      PROCEDURE ComputeTotal(n)
      HExecuteSQLQuery(ds, hQueryDefault, sSql)
      RESULT n
   -
     code : |1+
      PROCEDURE NeverCalled()
      RETURN
'''
SIMPLE = 'info :\n name : {0}\n{1} :\n name : {0}\n'
XDD = ('<?xml version="1.0" encoding="UTF-8"?><ANALYSE>' + ''.join(
    f'<FICHIER Nom="{name}"><RUBRIQUE Nom="Code"/></FICHIER>' for name in ('Orders', 'Customer', 'OrderLine', 'Product', 'Unused'))
       + '</ANALYSE>')


class CodeMap(unittest.TestCase):
    def build(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder, 'project')
            project.mkdir()
            (project / 'WIN_Order.wdw').write_text(WINDOW, encoding='utf-8')
            (project / 'GlobalProcedures.wdg').write_text(SET, encoding='utf-8')
            (project / 'WIN_Customer.wdw').write_text(SIMPLE.format('WIN_Customer', 'window'), encoding='utf-8')
            (project / 'RPT_Order.wde').write_text(SIMPLE.format('RPT_Order', 'report'), encoding='utf-8')
            (project / 'TaxRules.wdc').write_text(SIMPLE.format('TaxRules', 'class'), encoding='utf-8')
            (project / 'Schema.xdd').write_text(XDD, encoding='utf-8')
            inspector.inspect(project, Path(folder, 'inspect'))
            decoded = Path(folder, 'decoded')
            (decoded / 'properties').mkdir(parents=True)
            (decoded / 'queries.json').write_text(json.dumps({'QRY_Totals': 'SELECT\n Product.Code\nFROM\n Product'}), encoding='utf-8')
            (decoded / 'properties' / 'WIN_Order.wdw.json').write_text(json.dumps({'elements': [
                {'name': 'EDT_Code', 'fields': {'linked_item': 'Customer.Code'}},
                {'name': 'TABLE_A', 'properties': {'browsed_item': 'Product.Code'}}]}), encoding='utf-8')
            data = module.build(Path(folder, 'inspect'), decoded)
            return data, module.markdown(data)

    def test_tables_by_operation_with_sites(self):
        data, _ = self.build()
        tables = data['units']['WIN_Order']['tables']
        self.assertEqual(sorted(tables['Orders']), ['assign', 'delete', 'read', 'write'])
        self.assertEqual(tables['Orders']['assign'], ['WIN_Order.wdw:13', 'WIN_Order.wdw:14'])     # = and +=, not ==
        self.assertEqual(tables['Orders']['delete'], ['WIN_Order.wdw:35'])                           # the commented call is not one
        self.assertEqual(sorted(tables['Customer']), ['bound control', 'read'])
        self.assertEqual(tables['Customer']['bound control'], ['EDT_Code'])
        self.assertEqual(sorted(tables['OrderLine']), ['delete', 'read'])
        # A table named only inside an ordinary string is still reported (SQL is text): read, never write.
        self.assertEqual(sorted(tables['Product']), ['bound control', 'read', 'read (via QRY_Totals)'])
        self.assertEqual(data['tables']['Orders'], {'readers': ['WIN_Order'], 'writers': ['WIN_Order'], 'deleters': ['WIN_Order'], 'bound': []})
        self.assertEqual(data['tables_never_referenced'], ['Unused'])

    def test_queries_calls_navigation_globals_and_unknowns(self):
        data, text = self.build()
        unit = data['units']['WIN_Order']
        self.assertEqual(list(unit['queries']), ['QRY_Totals'])
        self.assertEqual(list(unit['calls']), ['ComputeTotal'])
        self.assertEqual((list(unit['opens']), list(unit['prints']), unit['classes']), (['WIN_Customer'], ['RPT_Order'], ['TaxRules']))
        self.assertEqual(unit['globals'], {'MAX_LINES': 1, 'gnRate': 1})
        self.assertEqual(list(unit['unknown_tables']), ['Cab_Vendas'])               # another database: listed, not dropped
        self.assertEqual(unit['dynamic'], ['WIN_Order.wdw:28'])                      # {sTable}: a name built at run time
        self.assertEqual(data['globals']['MAX_LINES'], {'declared_in': 'GlobalProcedures', 'kind': 'constant', 'used_by': ['WIN_Order']})
        self.assertEqual(data['procedures']['ComputeTotal']['callers'], {'WIN_Order': ['WIN_Order.wdw:24']})
        self.assertEqual(data['procedures']['NeverCalled']['callers'], {})
        # SQL run from a block that names no table: its text is built elsewhere.
        self.assertEqual(data['units']['GlobalProcedures']['dynamic'], ['GlobalProcedures.wdg:15'])
        self.assertIn('| Orders | WIN_Order | WIN_Order | WIN_Order |  |', text)
        self.assertIn('`NeverCalled` (GlobalProcedures)', text)
        self.assertIn('`Cab_Vendas` (1 units)', text)


if __name__ == '__main__':
    unittest.main()
