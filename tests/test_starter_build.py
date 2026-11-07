import json
import unittest

from helpers import ROOT

STARTER = ROOT / 'templates/starter'


class StarterBuildTests(unittest.TestCase):
    def test_production_build_never_inlines_assets_and_verify_smokes_it(self):
        # Inlined data: URLs are refused by the skin resolver: the packaged app of a real migration opened blank.
        self.assertRegex((STARTER / 'vite.config.ts').read_text(encoding='utf-8'), r'assetsInlineLimit:\s*0\b')
        scripts = json.loads((STARTER / 'package.json').read_text(encoding='utf-8'))['scripts']
        self.assertIn('playwright.prod.config.ts', scripts['smoke:prod'])
        self.assertIn('npm run smoke:prod', scripts['verify'])
        self.assertLess(scripts['verify'].index('npm run build'), scripts['verify'].index('npm run smoke:prod'))
        self.assertTrue((STARTER / 'ui-check/prod.smoke.spec.ts').is_file())
        self.assertIn('prod.smoke.spec.ts', (STARTER / 'playwright.config.ts').read_text(encoding='utf-8'))  # testIgnore


if __name__ == '__main__':
    unittest.main()
