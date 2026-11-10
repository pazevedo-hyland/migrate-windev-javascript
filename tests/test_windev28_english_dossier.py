"""Regressions found on a WINDEV 28 project with an English dossier and newer pypdf (GestaoDeProducao run)."""
import tempfile
import unittest
from pathlib import Path

from helpers import load

dossier = load('scripts/dossier_extract.py')
legend = load('scripts/event_legend.py')
layout = load('scripts/screen_layout.py')
prepare = load('scripts/prepare_evidence.py')
parity = load('scripts/parity_check.py')


def page(sep, *parts, body, trailing=''):
    return f'Part 3 {sep} ' + f' {sep} '.join(parts) + f'{trailing}\n31/10/2026 1482MyApp\n' + body


class EnglishDossierTests(unittest.TestCase):
    def test_u203a_breadcrumbs_and_trailing_spaces(self):
        pages = [
            page('\u203a', 'WINDEV window', 'WIN_X', 'Image', trailing=' ',
                 body='WIN_X \nTitle PT: Janela X \nWindow type Free window \nX position 0 Y position 0 Width 480 Height 160 \n'),
            page('\u203a', 'WINDEV window', 'WIN_X', 'General information', trailing=' ', body='Opacity 100 \n'),
        ]
        window = dossier.collect(pages)['WINDEV window']['WIN_X']
        self.assertEqual(window['title'], {'PT': 'Janela X'})
        self.assertEqual(window['size'], {'x': 0, 'y': 0, 'width': 480, 'height': 160})

    def test_abbreviated_analysis_header_continues_previous_element(self):
        pages = [
            page('\u203a', 'Analysis', 'C:\\App\\App.ana\\App.wda', 'Files and items', body='Files and items\n'),
            page('\u203a', '...', 'Files and items', 'Clientes', 'Files and items', body='Clientes\n'),
        ]
        analysis = dossier.collect(pages)['Analysis']
        self.assertEqual(list(analysis), ['C:\\App\\App.ana\\App.wda'])
        self.assertNotIn('...', dossier.collect(pages))


class EventLegendTests(unittest.TestCase):
    def test_initializing_label_is_the_always_present_initialization(self):
        data = 'Initializing BTN_Gravar'.encode('utf-16-le') + b'\0\0' + 'Click BTN_Gravar'.encode('utf-16-le')
        self.assertEqual(legend.compiled_labels(data)['BTN_Gravar'], {'Initialization', 'Click'})


class ScreenLayoutTests(unittest.TestCase):
    def test_dossier_geometry_when_the_source_keeps_positions_encoded(self):
        self.assertEqual(layout.geometry({'x': 0, 'y': 0}, {'x': 392, 'y': 38, 'width': 80, 'height': 24}),
                         {'x': 392, 'y': 38, 'width': 80, 'height': 24})
        self.assertEqual(layout.geometry({'x': 5, 'y': 6, 'width': 7, 'height': 8}, {'x': 1}),
                         {'x': 5, 'y': 6, 'width': 7, 'height': 8})

    def test_skin_file_names_wrapped_by_the_pdf(self):
        self.assertEqual(layout.basename('<REPGABARIT>\\WD\\170 AquaBlue\\AquaBlue_Btn_Std.pn g'), 'AquaBlue_Btn_Std.png')


class CompileFolderChoiceTests(unittest.TestCase):
    def test_project_cpl_beside_the_wdp_wins_over_analysis_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, 'legacy')
            history = root / 'App' / 'App.ana' / 'ANA00141' / 'Code' / 'App.cpl'
            own = root / 'App' / 'App.cpl'
            for folder in (history, own):
                folder.mkdir(parents=True)
            (root / 'App' / 'App.wdp').write_text('')
            self.assertEqual(prepare.find_compile_dir(root), own)


class ParityCaseTests(unittest.TestCase):
    def test_units_differing_only_by_case_stay_distinct(self):
        header = 'id,kind,element,context,event,evidence,confidence,legacy_behavior,target_behavior,implemented_in,test,decision,status\n'
        seed = header + 'SRC-1,class,etiquetas,,,docs/x.md,verified,,,,,,unmapped\nSRC-2,table,Etiquetas,,,docs/x.md,verified,,,,,,unmapped\n'
        matrix = header + 'SRC-1,class,etiquetas,,,docs/x.md,verified,,,,,,unmapped\n'
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'seed.csv').write_text(seed, encoding='utf-8')
            Path(tmp, 'unit.csv').write_text(matrix, encoding='utf-8')
            errors, _ = parity.check(str(Path(tmp, 'unit.csv')), str(Path(tmp, 'seed.csv')), element='etiquetas')
        self.assertEqual([e for e in errors if 'SRC-2' in e], [])


if __name__ == '__main__':
    unittest.main()
