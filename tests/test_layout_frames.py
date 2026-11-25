import unittest

from helpers import load

frames = load('scripts/layout_frames.py')

SOURCE = """window :
 controls :
  -
    name : TAB_Principal
    tabs :
     -
       internal_properties : x
       controls :
        -
          name : TABLE_Lin
     -
       internal_properties : y
       controls :
        -
          name : EDT_Obs
"""


def element(owner, parents, line, *texts, name='', type_=None, fields=None):
    return {'owner': owner, 'name': name, 'type': type_, 'parents': parents, 'line': line, 'fields': fields or {},
            'chunks': [{'strings': [{'text': text} for text in texts]}]}


PROPERTIES = {'elements': [
    element('controls', ['WIN_X'], 1, name='TAB_Principal', type_='16', fields={'pane_top': 26}),
    element('tabs', ['WIN_X', 'TAB_Principal'], 2, '<REPGABARIT>\\WD\\140 iStyle\\iStyle_Tab_Top.gif', '[ &1 ] - Linhas'),
    element('tabs', ['WIN_X', 'TAB_Principal'], 3, '    [ &2 ] - Cabeçalho    '),
    element('options', ['WIN_X', 'CBOX_Corta'], 4, 'Corta papel'),
    element('options', ['WIN_X', 'CBOX_Modelo'], 5, 'TPLC_Ribbon.CBOX_Modelo'),
    element('options', ['WIN_X', 'RADIO_Ordem'], 6, 'Código'),
    element('options', ['WIN_X', 'RADIO_Ordem'], 7, 'Descrição'),
]}


def layout():
    return {'window': {'name': 'WIN_X'}, 'controls': [
        {'name': 'TAB_Principal', 'path': 'TAB_Principal', 'kind': 'Tab', 'x': 6, 'y': 173},
        {'name': 'TABLE_Lin', 'path': 'TAB_Principal.TABLE_Lin', 'kind': 'Table', 'x': 12, 'y': 179},
        {'name': 'EDT_Obs', 'path': 'TAB_Principal.EDT_Obs', 'kind': 'Edit control', 'x': 12, 'y': 190},
        {'name': 'CBOX_Corta', 'path': 'CBOX_Corta', 'kind': 'Check Box', 'caption': 'Corta papel?', 'x': 0, 'y': 0},
        {'name': 'CBOX_Modelo', 'path': 'CBOX_Modelo', 'kind': 'Check Box', 'x': 0, 'y': 0},
        {'name': 'RADIO_Ordem', 'path': 'RADIO_Ordem', 'kind': 'Radio Button', 'x': 0, 'y': 0},
    ]}


class LayoutFramesTests(unittest.TestCase):
    def test_pane_controls_move_below_the_strip_and_keep_their_pane(self):
        result = layout()
        frames.enrich(result, PROPERTIES, SOURCE)
        tab, table, obs = result['controls'][:3]
        self.assertEqual((tab['pane_top'], tab['pane_captions']), (26, ['[ &1 ] - Linhas', '    [ &2 ] - Cabeçalho    ']))
        self.assertEqual((table['y'], table['tab_panes'], table['pane_offset']), (205, {'TAB_Principal': 1}, 26))
        self.assertEqual((obs['y'], obs['tab_panes']), (216, {'TAB_Principal': 2}))

    def test_enrichment_is_idempotent(self):
        result = layout()
        frames.enrich(result, PROPERTIES, SOURCE)
        self.assertEqual(frames.enrich(result, PROPERTIES, SOURCE), 0)
        self.assertEqual(result['controls'][1]['y'], 205)

    def test_option_captions_replace_the_control_caption_but_never_a_template_path(self):
        result = layout()
        frames.enrich(result, PROPERTIES, SOURCE)
        corta, modelo, ordem = result['controls'][3:]
        self.assertEqual(corta['caption'], 'Corta papel')
        self.assertNotIn('caption', modelo)
        self.assertEqual(ordem['option_captions'], ['Código', 'Descrição'])

    def test_single_pane_tabs_are_members_too(self):
        source = SOURCE.split('     -\n       internal_properties : y')[0]
        self.assertEqual(frames.tab_panes_of(source), {'TAB_Principal': [['TABLE_Lin']]})


if __name__ == '__main__':
    unittest.main()
