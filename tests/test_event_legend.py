from pathlib import Path
import tempfile
import unittest

from helpers import load

module = load('scripts/event_legend.py')

WINDOW = '''window :
 name : WIN_A
 controls :
  -
    name : BTN_Save
    code_elements :
     p_codes :
      -
        code : |1-
         Save()
        type : 18
  -
    name : EDT_Name
    code_elements :
     p_codes :
      -
        code : |1-
         Check()
        type : 16
 code_elements :
  p_codes :
   -
     code : |1-
      PROCEDURE MyWindow()
   -
     code : |1-
      Init()
     type : 34
   -
     code : |1-
      PROCEDURE Helper()
     type : 458752
'''


def compiled(*labels):
    return b'PCS\x00\x01\x01' + b'\x00\x01'.join(label.encode('utf-16-le') for label in labels)


class EventLegendTests(unittest.TestCase):
    def test_compiled_labels_of_optional_and_nested_events(self):
        data = b''.join(s.encode('utf-16-le') + b'\x00\x00' for s in (
            'Left button down on EDT_Senha (WM_LBUTTONDOWN)', 'Initialization of BTN_X ( SC_Bar )', 'Exit from EDT_Nome'))
        labels = module.compiled_labels(data)
        self.assertEqual((labels['EDT_Senha'], labels['BTN_X'], labels['EDT_Nome']),
                         ({'Left button down'}, {'Initialization'}, {'Exit'}))

    def test_legend_from_compiled_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            (root / 'src/WIN_A.wdw').write_text(WINDOW, encoding='utf-8')
            (root / 'cpl/user').mkdir(parents=True)
            (root / 'cpl/user/WIN_A.1234ABCD.wdw.wcw').write_bytes(compiled(
                'Global declarations of WIN_A', 'End of initialization of WIN_A', 'Initialization of BTN_Save',
                'Click BTN_Save', 'Initialization of EDT_Name', 'Exit from EDT_Name'))
            data = module.legend(root / 'src', root / 'cpl')
        events = {code: item['event'] for code, item in data['codes'].items()}
        self.assertEqual(events, {'18': 'Click', '16': 'Exit', 'none': 'Global declarations', '34': 'End of initialization',
                                  '458752': 'Local procedure'})  # proven by the procedure's own PROCEDURE line
        self.assertIn('| 18 | Click | 1 | — |', module.markdown(data))

    def test_elimination_pairs_what_is_left(self):
        # WIN_B codes Click and Close on itself: ambiguous alone, settled once WIN_A proves 18 = Click.
        window_b = '''window :
 name : WIN_B
 code_elements :
  p_codes :
   -
     code : |1-
      Ok()
     type : 18
   -
     code : |1-
      Bye()
     type : 2
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            (root / 'src/WIN_A.wdw').write_text(WINDOW, encoding='utf-8')
            (root / 'src/WIN_B.wdw').write_text(window_b, encoding='utf-8')
            (root / 'cpl').mkdir()
            (root / 'cpl/WIN_A.1.wdw.wcw').write_bytes(compiled('Click BTN_Save', 'Exit from EDT_Name'))
            (root / 'cpl/WIN_B.1.wdw.wcw').write_bytes(compiled('Click WIN_B', 'Close WIN_B'))
            data = module.legend(root / 'src', root / 'cpl')
        self.assertEqual(data['codes']['2']['event'], 'Close')
        self.assertEqual(data['codes']['18']['conflicts'], {})


if __name__ == '__main__':
    unittest.main()
