from pathlib import Path
import json
import re
import unittest

from helpers import ROOT

LINK = re.compile(r'\]\(([^)#\s]*)(#[^)]*)?\)')


def anchors(document):
    """GitHub-style heading slugs, ignoring fenced code."""
    slugs, fenced = set(), False
    for line in document.read_text(encoding='utf-8').splitlines():
        if line.startswith('```'):
            fenced = not fenced
        elif not fenced and line.startswith('#'):
            title = line.lstrip('#').strip().lower().replace('`', '')
            slugs.add(re.sub(r'[^\w\- ]', '', title).replace(' ', '-'))
    return slugs


class DocumentationTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        broken = []
        for document in ROOT.rglob('*.md'):
            if '.git' in document.parts:
                continue
            for target, anchor in LINK.findall(document.read_text(encoding='utf-8')):
                if re.match(r'^[a-z]+:', target):
                    continue
                path = document.parent / target if target else document
                if not path.exists():
                    broken.append(f'{document.relative_to(ROOT)} -> {target}')
                elif anchor and path.suffix == '.md' and anchor[1:] not in anchors(path):
                    broken.append(f'{document.relative_to(ROOT)} -> {target}{anchor}')
        self.assertEqual(broken, [])

    def test_parity_template_matches_checker_columns(self):
        header = (ROOT / 'templates/parity.template.csv').read_text(encoding='utf-8').splitlines()[0]
        from helpers import load
        self.assertEqual(header.split(','), load('scripts/inspect_windev.py').SEED_COLUMNS)

    def test_functional_acceptance_template_is_valid_pending_scope(self):
        from helpers import load
        data = json.loads((ROOT / 'templates/functional-acceptance.template.json').read_text(encoding='utf-8'))
        result = load('scripts/functional_acceptance.py').assess_data(data, ['WIN_Example'], ROOT)
        self.assertEqual((result['passed'], result['total']), (0, 1))
        self.assertEqual(result['units']['WIN_Example']['status'], 'pending')
        self.assertEqual(result['environments'], [])


class MergeMarkerTests(unittest.TestCase):
    def test_no_unresolved_merge_conflicts(self):
        marker = re.compile(r'^(<<<<<<< |>>>>>>> )', re.M)
        found = [str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.suffix in ('.md', '.py', '.ts', '.tsx', '.json', '.csv')
                 and '.git' not in p.parts and marker.search(p.read_text(encoding='utf-8', errors='replace'))]
        self.assertEqual(found, [])


class GitignoreTests(unittest.TestCase):
    def test_evidence_ignores_are_anchored_to_the_root(self):
        # An unanchored "legacy/" also ignores application folders such as src/ui/legacy/ (pilot incident).
        lines = Path(__file__).resolve().parents[1].joinpath('.gitignore').read_text(encoding='utf-8').splitlines()
        for name in ('legacy', 'analysis-local', 'origine'):
            self.assertNotIn(f'{name}/', lines)
            self.assertIn(f'/{name}/', lines)


if __name__ == '__main__':
    unittest.main()
