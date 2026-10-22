import unittest

from helpers import load

module = load('scripts/dossier_extract.py')
SEP = '\x9b'


def page(*parts, body):
    return f'Part 3 {SEP} ' + f' {SEP} '.join(parts) + '\n22/10/2026 1789My_App\n' + body


class DossierExtractTests(unittest.TestCase):
    def test_window_properties_and_control_details(self):
        pages = [
            page('WINDEV window', 'WIN_Acesso', 'General information',
                 body='WIN_Acesso\nTitle PT: Acesso\nWindow type Free window\n'),
            page('WINDEV window', 'WIN_Acesso', 'Information on controls', body=(
                'Button : BTN_Confirmar\nCaption PT: Confirmar\nTab order 5\nImage PT: C:\\App\\Btn_OK.gif\n'
                'Image : BTN_Restore\nImage handling menu <No menu>\nInitial value PT: C:\\App\\Restore.gif\n'
                'Edit control : EDT_palavra_passe\nTab order 4\nInput size 15\nInput mask PT: 0\n'
                'Window : WIN_Acesso\n')),
        ]
        window = module.collect(pages)['WINDEV window']['WIN_Acesso']
        self.assertEqual(window['title'], {'PT': 'Acesso'})
        self.assertEqual(window['window_type'], 'Free window')
        controls = window['controls']
        self.assertEqual(controls['BTN_Confirmar']['caption'], {'PT': 'Confirmar'})
        self.assertEqual(controls['BTN_Confirmar']['tab_order'], 5)
        self.assertEqual(controls['EDT_palavra_passe']['input_size'], 15)
        self.assertNotIn('image', controls['BTN_Restore'])  # "Image handling menu" is another property
        self.assertEqual(controls['BTN_Restore']['initial_value'], {'PT': 'C:\\App\\Restore.gif'})

    def test_analysis_items_with_captions_types_and_defaults(self):
        pages = [page('Analysis', 'C:\\App\\App.wda', 'Files and items', 'artigos', 'Files and items', body=(
            'General information\nartigos artigos\nName on disk artigos.fic\nDescription\nGB: Products\nPT:\n'
            'artigos file items\nCaption Type\nSize\nDefault value\n'
            'artigosID Identifier of artigos Automatic identifier (8 bytes)\n'
            'Codigo Código String 30\npreco Preço 8-byte real 0\nstock stock Decimal 0\n'
            'Cliente Cliente Unsigned 8-byte integer\n 0\n'
            'inicio Data/hora inicio Date and Time \n(yyyymmddhhmmssccc)\nGB: Start\n'
            'numeromecanico numero + mecanico Composite key: numero+mecanico 9\n'))]
        analysis = module.collect(pages)['Analysis']['C:\\App\\App.wda']
        artigos = analysis['files']['artigos']
        self.assertEqual(artigos['description'], 'Products')
        items = {i['name']: i for i in artigos['items']}
        self.assertEqual(items['artigosID']['type'], 'Automatic identifier (8 bytes)')
        self.assertEqual((items['Codigo']['caption'], items['Codigo']['type'], items['Codigo']['size']), ('Código', 'String', 30))
        self.assertEqual((items['preco']['type'], items['preco']['size'], items['preco']['default']), ('8-byte real', None, '0'))
        self.assertEqual(items['stock']['type'], 'Decimal')
        self.assertEqual(items['inicio']['type'], 'Date and Time (yyyymmddhhmmssccc)')  # type wrapped onto two lines
        self.assertEqual((items['numeromecanico']['type'], items['numeromecanico']['components']),
                         ('Composite key', ['numero', 'mecanico']))
        self.assertEqual(items['Cliente']['default'], '0')

    def test_supercontrol_children_rows_and_reports(self):
        window = module.collect([page('WINDEV window', 'WIN_F', 'Information on controls', body=(
            'EDT_Codigo 14 31 158 25 0 Active Numeric\nEDT_Nome 14 62 300 25 0 Read-onl Text\n'
            'Supercontrol : SC_Form\nEdit control : SC_Form.EDT_Codigo\nTab order 2\n'
            'Combo Box : SC_Form.COMBO_Codigo\nCaption PT: Cliente\nTab order 3\n'
            'Code\nClick BTN_X\nTab order 9\n'))])['WINDEV window']['WIN_F']
        self.assertEqual((window['controls']['COMBO_Codigo']['kind'], window['controls']['COMBO_Codigo']['tab_order']),
                         ('Combo Box', 3))  # capitalised kind; code after "Code" is not a property
        code = window['controls']['EDT_Codigo']
        self.assertEqual((code['path'], code['tab_order'], code['input_type'], code['state']),
                         ('SC_Form.EDT_Codigo', 2, 'Numeric', 'Active'))
        self.assertEqual(window['controls']['EDT_Nome']['state'], 'Read-only')
        report = module.collect([
            page('Report', 'RPT_L', 'General information', body='Type Table\nData source type Embedded query\n'),
            page('Report', 'RPT_L', 'Information on controls', body=(
                'STC_Codigo Caption 0.00 0.00 6.09 14.66 0.10 Solid TBL-\n'
                'ITEM_Codigo Caption 0.00 0.00 6.20 14.66 0.10 Solid -BL-\nItem Codigo\n'))])['Report']['RPT_L']
        self.assertEqual((report['report_type'], report['data_source']), ('Table', 'Embedded query'))
        self.assertEqual(report['controls']['ITEM_Codigo']['item'], 'Codigo')
        self.assertEqual(report['controls']['STC_Codigo']['width_mm'], 14.66)

    def test_checkbox_values_from_drawn_check_marks(self):
        tick = lambda x, y: f'{x} {y} m {x + 2.84} {y - 2.83} l S\n{x + 2.84} {y - 2.83} m {x + 8.5} {y + 2.84} l S\n'
        content = (
            "BT 46.72 269.67 Td (Large font management)' ET\n" + tick(277.97, 272.77) +
            "BT 46.72 255.75 Td (Indep. HFSQL ctx.)' ET\n"
            "BT 46.72 240.00 Td (Opening mode)' ET\nBT 280.00 240.00 Td (Centered)' ET\n"
            "BT 46.72 230.00 Td (X position)' ET\nBT 198.16 231.21 Td (0)' ET\nBT 280.00 231.21 Td (0)' ET\n"
            "BT 46.72 220.00 Td (WIN_Login)' ET\n"  # the window's own name is not a property
            "BT 177.76 143.19 Td (X position)' ET\nBT 240.00 143.19 Td (Y position)' ET\n"
            "BT 359.44 143.19 Td (Visible)' ET\nBT 420.00 143.19 Td (Initial state)' ET\n"
            "BT 556.24 143.19 Td (Password)' ET\nBT 579.04 143.19 Td (Required input)' ET\n"
            # values are centred under their header, so "Active" starts left of "Initial state"
            "BT 46.72 137.56 Td (EDT_palavra_passe)' ET\nBT 198.00 137.56 Td (28)' ET\n"
            "BT 260.00 137.56 Td (40)' ET\nBT 415.00 137.56 Td (Active)' ET\n"
            + tick(360.0, 143.1) + tick(556.8, 143.1) +
            "BT 46.72 125.19 Td (EDT_utilizador)' ET\nBT 198.00 125.19 Td (28)' ET\nBT 260.00 125.19 Td (12)' ET\n"
            + tick(360.0, 130.7) +
            "BT 46.72 100.50 Td (Opacity)' ET\nBT 273.90 100.50 Td (100)' ET\n")  # a detail key, not a control
        properties, controls = module.checkboxes(content)
        self.assertEqual(properties, {'Large font management': True, 'Indep. HFSQL ctx.': False})
        self.assertEqual(controls['EDT_palavra_passe'], {'Visible': True, 'Password': True, 'Required input': False})
        self.assertEqual(controls['EDT_utilizador'], {'Visible': True, 'Password': False, 'Required input': False})
        self.assertNotIn('Opacity', controls)

    def test_analysis_key_flags(self):
        tick = lambda x, y: f'{x} {y} m {x + 2.84} {y - 2.83} l S\n{x + 2.84} {y - 2.83} m {x + 8.5} {y + 2.84} l S\n'
        content = (
            "BT 289.24 178.11 Td (Caption)' ET\nBT 485.44 178.11 Td (Type)' ET\n"
            "BT 623.08 178.11 Td (Unique Key)' ET\nBT 660.88 178.11 Td (Key with Duplicates)' ET\n"
            "BT 46.72 173.43 Td (ClientesID)' ET\nBT 425.20 173.43 Td (Automatic identifier)' ET\n" + tick(624.9, 177.8) +
            "BT 46.72 159.27 Td (Codigo)' ET\nBT 425.20 159.27 Td (8-byte integer)' ET\n" + tick(624.9, 163.6) +
            "BT 46.72 145.11 Td (Descricao)' ET\nBT 425.20 145.11 Td (String)' ET\n" + tick(662.8, 149.5) +
            "BT 46.72 131.00 Td (Morada1)' ET\nBT 425.20 131.00 Td (String)' ET\n")
        _, items = module.checkboxes(content)
        self.assertEqual(items['Codigo'], {'Unique Key': True, 'Key with Duplicates': False})
        self.assertEqual(items['Descricao'], {'Unique Key': False, 'Key with Duplicates': True})
        self.assertEqual(items['Morada1'], {'Unique Key': False, 'Key with Duplicates': False})

    def test_tables_continue_across_pages_and_skip_code(self):
        tick = lambda x, y: f'{x} {y} m {x + 2.84} {y - 2.83} l S\n{x + 2.84} {y - 2.83} m {x + 8.5} {y + 2.84} l S\n'
        first = ("BT 289.24 178.11 Td (Caption)' ET\nBT 623.08 178.11 Td (Unique Key)' ET\n"
                 "BT 660.88 178.11 Td (Key with Duplicates)' ET\n"
                 "BT 46.72 173.43 Td (ClientesID)' ET\nBT 425.20 173.43 Td (Automatic identifier)' ET\n" + tick(624.9, 177.8))
        # The next page has no header row: its rows continue the table above.
        second = ("BT 46.72 520.80 Td (artigo)' ET\nBT 425.20 520.70 Td (String)' ET\n" + tick(662.8, 525.2) +
                  "BT 46.72 500.00 Td (IF)' ET\nBT 52.00 500.00 Td ( )' ET\nBT 57.00 500.00 Td (Timer)' ET\n")
        carry = {}
        module.checkboxes(first, carry)
        _, items = module.checkboxes(second, carry)
        self.assertEqual(items, {'artigo': {'Unique Key': False, 'Key with Duplicates': True}})

    def test_coverage_warns_when_nothing_is_recognised(self):
        elements = {'WINDEV window': {'WIN_A': {'controls': {'BTN_X': {'kind': 'Button'}}},
                                      'WIN_B': {'controls': {}}}}
        coverage = module.parsed_coverage(elements)
        self.assertEqual(coverage['windows_with_flags'], '0/2')
        self.assertTrue(any('windows_with_flags' in w for w in coverage['warnings']))

    def test_query_sql_parameters_and_conditions(self):
        pages = [
            page('Query', 'QRY_cliente', 'Information on the result', body='Query parameters\nParamCodigo\n'),
            page('Query', 'QRY_cliente', 'Additional information',
                 body='Selection conditions Parameter used\nCodigo  is equal to ParamCodigo ParamCodigo\n'),
            page('Query', 'QRY_cliente', 'Code',
                 body='QRY_cliente\nCode\nSQL code of QRY_cliente\nSELECT Codigo\nFROM Clientes\nWHERE Codigo = {ParamCodigo}\n'),
        ]
        query = module.collect(pages)['Query']['QRY_cliente']
        self.assertEqual(query['sql'], 'SELECT Codigo\nFROM Clientes\nWHERE Codigo = {ParamCodigo}')
        self.assertEqual(query['parameters'], ['ParamCodigo'])
        self.assertEqual(query['conditions'], ['Codigo  is equal to ParamCodigo'])


if __name__ == '__main__':
    unittest.main()
