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
