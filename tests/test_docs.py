from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
