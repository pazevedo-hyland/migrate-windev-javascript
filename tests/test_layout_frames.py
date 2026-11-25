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


def window_head(width, height, client_width, client_height, xy=''):
    lines = ['window :', ' name : WIN_X', ' identifier : 0x1', ' internal_properties : abc', ' properties :']
    lines += ([f'  x : {xy[0]}', f'  y : {xy[1]}'] if xy else [])
    lines += [f'  width : {width}', f'  height : {height}', f'  widthClient : {client_width}',
              f'  heightClient : {client_height}', ' controls :', '']
    return '\r\n'.join(lines)


class WindowFrameTests(unittest.TestCase):
    def test_a_window_without_title_bar_and_one_with(self):
        self.assertEqual(frames.window_frame(window_head(538, 216, 532, 210)),
                         {'client': {'width': 532, 'height': 210}, 'border': 3, 'title_bar': 0})
        self.assertEqual(frames.window_frame(window_head(430, 292, 428, 260, (6, 6)))['title_bar'], 30)

    def test_enrich_sets_the_client_and_the_title_bar_flag(self):
        result = layout()
        frames.enrich(result, PROPERTIES, window_head(538, 216, 532, 210) + SOURCE)
        window = result['window']
        self.assertEqual((window['client'], window['flags']['Title bar']), ({'width': 532, 'height': 210}, False))


class EditMaskTests(unittest.TestCase):
    def test_numeric_masks_right_align_and_dates_do_not(self):
        props = {'elements': [
            element('controls', ['WIN_X'], 1, '140 iStyle.SAI_Simple', 'MoneySystemMask', name='EDT_Valor', type_='2'),
            element('controls', ['WIN_X'], 2, 'AAAAMMJJ', name='EDT_Data', type_='2'),
            element('controls', ['WIN_X'], 3, '999,99%%', name='EDT_Taxa', type_='2'),
        ]}
        result = {'controls': [{'name': n, 'path': n, 'kind': 'Edit control', 'x': 0, 'y': 0} for n in ('EDT_Valor', 'EDT_Data', 'EDT_Taxa')]}
        result['controls'].append({'name': 'EDT_Fixo', 'path': 'EDT_Fixo', 'kind': 'Edit control', 'h_align': 'Left', 'x': 0, 'y': 0})
        frames.enrich(result, props)
        valor, data, taxa, _ = result['controls']
        self.assertEqual((valor['display_mask'], valor['h_align']), ('MoneySystemMask', 'Right'))
        self.assertEqual((data['display_mask'], data.get('h_align')), ('AAAAMMJJ', None))
        self.assertEqual(taxa['h_align'], 'Right')


if __name__ == '__main__':
    unittest.main()
