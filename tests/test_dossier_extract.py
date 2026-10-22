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
            'Cliente Cliente Unsigned 8-byte integer\n 0\n'))]
        analysis = module.collect(pages)['Analysis']['C:\\App\\App.wda']
        artigos = analysis['files']['artigos']
        self.assertEqual(artigos['description'], 'Products')
        items = {i['name']: i for i in artigos['items']}
        self.assertEqual(items['artigosID']['type'], 'Automatic identifier (8 bytes)')
        self.assertEqual((items['Codigo']['caption'], items['Codigo']['type'], items['Codigo']['size']), ('Código', 'String', 30))
        self.assertEqual((items['preco']['type'], items['preco']['size'], items['preco']['default']), ('8-byte real', None, '0'))
        self.assertEqual(items['stock']['type'], 'Decimal')
        self.assertEqual(items['Cliente']['default'], '0')

    def test_supercontrol_children_rows_and_reports(self):
        window = module.collect([page('WINDEV window', 'WIN_F', 'Information on controls', body=(
            'EDT_Codigo 14 31 158 25 0 Active Numeric\nEDT_Nome 14 62 300 25 0 Read-onl Text\n'
            'Supercontrol : SC_Form\nEdit control : SC_Form.EDT_Codigo\nTab order 2\n'))])['WINDEV window']['WIN_F']
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
