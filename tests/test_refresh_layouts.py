import unittest

from helpers import load

module = load('scripts/refresh_layouts.py')


class RefreshLayouts(unittest.TestCase):
    def setUp(self):
        self.layout = {'controls': [
            {'name': 'BTN_Ok', 'path': 'BTN_Ok', 'x': 5, 'caption': 'Repaired by hand'},
            {'name': 'TABLE_A', 'path': 'TABLE_A', 'columns': [
                {'name': 'COL_Name', 'path': 'TABLE_A.COL_Name', 'title': None, 'width': 90},
                {'name': 'COL_Code', 'path': 'TABLE_A.COL_Code', 'title': 'Code', 'width': 40}]},
            {'name': 'STC_Gone', 'path': 'STC_Gone'}]}
        self.fresh = {'controls': [
            {'name': 'BTN_Ok', 'path': 'BTN_Ok', 'x': 99, 'caption': 'OK', 'font': {'face': 'Tahoma', 'height': -11, 'weight': 700}},
            {'name': 'TABLE_A', 'path': 'TABLE_A', 'font': {'face': 'Arial', 'height': -11, 'weight': 400}, 'columns': [
                {'name': 'COL_Name', 'path': 'TABLE_A.COL_Name', 'title': 'Name', 'width': 10, 'input_type': 'Text'},
                {'name': 'COL_Code', 'path': 'TABLE_A.COL_Code', 'title': 'Code number', 'width': 10}]}]}

    def test_only_the_named_fields_move_and_repairs_stay(self):
        counts = module.refresh(self.layout, self.fresh, fields=['font'], column_fields=['title', 'input_type'], fill=True)
        button, table = self.layout['controls'][0], self.layout['controls'][1]
        self.assertEqual((button['x'], button['caption'], button['font']['face']), (5, 'Repaired by hand', 'Tahoma'))
        self.assertEqual([(c['title'], c['width'], c.get('input_type')) for c in table['columns']],
                         [('Name', 90, 'Text'), ('Code', 40, None)])         # an existing title is kept with --fill
        self.assertEqual(dict(counts), {'control.font added': 2, 'column.title added': 1, 'column.input_type added': 1,
                                        'controls not in the current evidence': 1})

    def test_without_fill_a_differing_value_is_replaced_and_counted(self):
        counts = module.refresh(self.layout, self.fresh, column_fields=['title'])
        self.assertEqual([c['title'] for c in self.layout['controls'][1]['columns']], ['Name', 'Code number'])
        self.assertEqual((counts['column.title added'], counts['column.title changed']), (1, 1))


if __name__ == '__main__':
    unittest.main()
