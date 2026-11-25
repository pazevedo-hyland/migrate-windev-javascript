import unittest

from helpers import load

template = load('scripts/skin_template.py')

STYLES = {
    'LIB_Simple': {'fonts': [{'face': 'Trebuchet MS', 'height': -11, 'weight': 400, 'colour': '#2d2d2d'}]},
    'LIB_Titre_Fenetre': {'fonts': [{'face': 'Trebuchet MS', 'height': -13, 'weight': 700, 'colour': '#e5e5e5'}]},
    'BTN_Simple': {'fonts': [{'face': 'Trebuchet MS', 'height': -11, 'weight': 400, 'colour': '#2d2d2d', 'italic': True}]},
    'IMG_Vide': {'fonts': []},
}


class SkinTemplateTests(unittest.TestCase):
    def test_one_rule_per_style_with_the_first_font_and_its_colour(self):
        css = template.css_of(STYLES)
        self.assertIn('[data-wd-style="LIB_Titre_Fenetre"] { font: 700 13px "Trebuchet MS", sans-serif; color: #e5e5e5; }', css)
        self.assertIn('[data-wd-style="BTN_Simple"] { font: italic 400 11px "Trebuchet MS", sans-serif; color: #2d2d2d; }', css)
        self.assertNotIn('IMG_Vide', css)

    def test_a_measured_substitution_changes_only_the_matching_styles_and_size(self):
        rule = template.substitution('LIB_:Trebuchet MS 11px=Segoe UI 12px')
        self.assertEqual(rule, ('LIB_', ('Trebuchet MS', 11), ('Segoe UI', 12)))
        css = template.css_of(STYLES, [rule])
        self.assertIn('[data-wd-style="LIB_Simple"] { font: 400 12px "Segoe UI", sans-serif;', css)
        self.assertIn('[data-wd-style="LIB_Titre_Fenetre"] { font: 700 13px "Trebuchet MS"', css)  # 13 px: untouched
        self.assertIn('[data-wd-style="BTN_Simple"] { font: italic 400 11px "Trebuchet MS"', css)  # not LIB_


if __name__ == '__main__':
    unittest.main()
