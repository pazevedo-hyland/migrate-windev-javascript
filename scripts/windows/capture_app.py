#!/usr/bin/env python3
"""Unattended screen capture of a WINDEV application on Windows (UI Automation).

Follows capture-plan.json from plan_capture.py: opens each window through a click path the
plan marks safe, saves a screenshot, the UI Automation control tree and the tab order, then
closes it. Runs only on a marked COPY of the application folder and stops as soon as any data
file changes. Requires: Windows, Python 3.10+, `pip install pywinauto pillow`.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata

MARKER = '.migration-capture-copy'
DATA_SUFFIXES = {'.fic', '.ndx', '.mmo', '.ftx', '.ini'}
PREFIXES = re.compile(r'^(MENU_OPT_|MENU_|OPT_|BTN_|BOUTON_|Btn_|CBOX_|TAB_|IMG_)', re.I)


# ---------- planning logic (platform independent, unit tested) ----------

def normalize(text):
    text = unicodedata.normalize('NFD', text or '')
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def caption_candidates(control):
    """Likely visible captions for a control name: BTN_Ordens_reparacao -> 'ordens reparacao'."""
    base = PREFIXES.sub('', control)
    base = re.sub(r'\d+$', '', base)
    words = normalize(base.replace('_', ' '))
    return [w for w in dict.fromkeys([words, words.replace(' de ', ' '), words.split(' ')[0] if words else ''])
            if w]


def match_score(control, caption, automation_id=''):
    """3 automation id = control name, 2 exact caption, 1 caption contains the phrase, 0.5 first word only."""
    if automation_id and automation_id.lower() == control.lower():
        return 3
    caption = normalize(caption.replace('&', ''))
    candidates = caption_candidates(control)
    if not caption or not candidates:
        return 0
    if caption in candidates[:-1] or caption == candidates[0]:
        return 2
    if any(c in caption for c in candidates[:-1] or candidates):
        return 1
    return 0.5 if caption.split(' ')[0] == candidates[-1] else 0


def best_match(control, elements):
    """elements: (element, caption, automation_id). Ambiguous best scores are refused, not guessed."""
    scored = sorted(((match_score(control, c, a), i) for i, (_, c, a) in enumerate(elements)), reverse=True)
    if not scored or scored[0][0] == 0 or (len(scored) > 1 and scored[1][0] == scored[0][0] and scored[0][0] < 3):
        return None
    return elements[scored[0][1]][0]


def menu_steps(path):
    """WIN_MENU/MENU__Menu/OPT_Tabelas/OPT_Clientes -> ['OPT_Tabelas', 'OPT_Clientes']."""
    parts = path.split('/')[1:]
    return [p for p in parts if p.upper().startswith(('OPT_', 'MENU_OPT_'))]


def routes(plan, main_window, allow_review=False, max_depth=2):
    """For each capturable window: the chain of (parent window, entry) clicks from the main window."""
    windows = {w['window'].lower(): w for w in plan['windows']}
    allowed = {'navigation', 'review'} if allow_review else {'navigation'}
    levels = {'auto'} | ({'auto-review'} if allow_review else set())
    chains = {main_window.lower(): []}
    for _ in range(max_depth):
        for key, window in windows.items():
            if key in chains or window['capture'] not in levels:
                continue
            options = sorted((e for e in window['entries'] if e['click'] in allowed and e['from'].lower() in chains
                              and e['from'].lower() != key and len(e['path'].split('/')) > 1),
                             key=lambda e: (e['click'] != 'navigation', len(chains[e['from'].lower()]),
                                            e['arguments'] != ''))
            if options:
                chains[key] = chains[options[0]['from'].lower()] + [options[0]]
    del chains[main_window.lower()]
    return {windows[k]['window']: v for k, v in sorted(chains.items())}


def data_files(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(folder).rglob('*')) if p.is_file() and p.suffix.lower() in DATA_SUFFIXES}


def changed(before, after):
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


# ---------- Windows UI Automation layer ----------

class Desktop:
    """Thin pywinauto wrapper; everything Windows-specific lives here."""

    def __init__(self, exe, work_dir, timeout):
        from pywinauto import Application  # imported lazily so the planner runs anywhere
        from pywinauto.keyboard import send_keys
        self.send_keys, self.timeout = send_keys, timeout
        self.app = Application(backend='uia').start(f'"{exe}"', work_dir=str(work_dir), timeout=timeout)

    def windows(self):
        return [w for w in self.app.windows() if w.is_visible()]

    def wait_new_window(self, known):
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            for w in self.windows():
                if w.handle not in known:
                    w.wait('ready', timeout=self.timeout)
                    return w
            time.sleep(0.3)
        return None

    def click(self, window, control):
        steps = [control] if not isinstance(control, list) else control
        if len(steps) > 1 or steps[0].upper().startswith(('OPT_', 'MENU_OPT_')):
            items = []
            for step in steps:
                scope = items[-1] if items else window
                item = best_match(step, [(d, d.window_text(), d.element_info.automation_id)
                                         for d in scope.descendants(control_type='MenuItem')])
                if item is None:
                    return f'menu item not found for {step}'
                item.select() if hasattr(item, 'select') else item.click_input()
                items.append(item)
                time.sleep(0.3)
            return None
        button = best_match(steps[0], [(d, d.window_text(), d.element_info.automation_id) for d in window.descendants()
                                       if d.element_info.control_type in ('Button', 'Image', 'Hyperlink', 'MenuItem')])
        if button is None:
            return f'control not found for {steps[0]}'
        try:
            button.invoke()
        except Exception:
            button.click_input()
        return None

    @staticmethod
    def tree(window):
        out = []
        for d in [window] + window.descendants():
            r = d.rectangle()
            info = d.element_info
            out.append({'type': info.control_type, 'name': d.window_text(), 'automation_id': info.automation_id,
                        'class': info.class_name, 'rect': [r.left, r.top, r.right, r.bottom],
                        'enabled': d.is_enabled(), 'visible': d.is_visible()})
        return out

    def tab_order(self, window, limit=80):
        window.set_focus()
        order, seen = [], set()
        for _ in range(limit):
            self.send_keys('{TAB}')
            time.sleep(0.15)
            from pywinauto.uia_element_info import UIAElementInfo
            from pywinauto.uia_defines import IUIA
            info = UIAElementInfo(IUIA().iuia.GetFocusedElement())
            key = (info.control_type, info.name, tuple(info.rectangle.__dict__.values()) if info.rectangle else None)
            if key in seen:
                break
            seen.add(key)
            order.append({'type': info.control_type, 'name': info.name, 'automation_id': info.automation_id})
        return order

    def close(self, window):
        window.close()

    def kill(self):
        self.app.kill()


def capture(desktop, window, folder, tabs):
    folder.mkdir(parents=True, exist_ok=True)
    window.capture_as_image().save(folder / 'screenshot.png')
    (folder / 'tree.json').write_text(json.dumps(Desktop.tree(window), indent=1, ensure_ascii=False), encoding='utf-8')
    if tabs:
        (folder / 'tab-order.json').write_text(json.dumps(desktop.tab_order(window), indent=1, ensure_ascii=False),
                                               encoding='utf-8')
    return window.window_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--app-dir', type=Path, required=True, help=f'COPY of the installed app, containing {MARKER}')
    parser.add_argument('--exe', required=True, help='executable name inside --app-dir')
    parser.add_argument('--plan', type=Path, required=True, help='capture-plan.json from plan_capture.py')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--main-window', default='WIN_MENU', help='window shown after startup/login')
    parser.add_argument('--data-dir', type=Path, help='data folder if not inside --app-dir (must also be a copy)')
    parser.add_argument('--allow-review', action='store_true', help='also follow auto-review paths')
    parser.add_argument('--no-tab-order', action='store_true', help='skip tab-order capture (Tab can fire exit events)')
    parser.add_argument('--login', action='store_true',
                        help='type MIGRATION_APP_USER / MIGRATION_APP_PASSWORD into the first window, then Enter')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--dry-run', action='store_true', help='print the routes and exit')
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    chains = routes(plan, args.main_window, args.allow_review)
    if args.dry_run:
        for window, chain in chains.items():
            print(window, '<=', ' -> '.join(f"{e['from']}:{e['control']}" for e in chain))
        print(f'{len(chains)} windows routable of {len(plan["windows"])}')
        return
    if sys.platform != 'win32':
        parser.exit(2, 'capture_app.py runs on Windows; use --dry-run elsewhere\n')
    data_dir = args.data_dir or args.app_dir
    for folder in {args.app_dir, data_dir}:
        if not (folder / MARKER).exists():
            parser.exit(2, f'{folder} has no {MARKER}: run only on a copy of the application and its data\n')
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'windows': {}, 'stopped': None}

    def start():
        desktop = Desktop(args.app_dir / args.exe, args.app_dir, args.timeout)
        first = desktop.wait_new_window(set())
        if args.login and first is not None:
            capture(desktop, first, args.out / '_startup', not args.no_tab_order)
            first.set_focus()
            desktop.send_keys(os.environ.get('MIGRATION_APP_USER', ''), with_spaces=True)
            desktop.send_keys('{TAB}')
            desktop.send_keys(os.environ.get('MIGRATION_APP_PASSWORD', ''), with_spaces=True)
            desktop.send_keys('{ENTER}')
            first = desktop.wait_new_window({first.handle})
        return desktop, first

    desktop, main_window = start()
    if main_window is None:
        parser.exit(1, 'main window did not appear\n')
    capture(desktop, main_window, args.out / args.main_window, False)
    baseline = data_files(data_dir)  # after startup: first-run setup writes are not the crawler's
    for target, chain in chains.items():
        status = {'route': [f"{e['from']}:{e['control']}" for e in chain]}
        try:
            current, opened = main_window, []
            for entry in chain:
                known = {w.handle for w in desktop.windows()}
                steps = menu_steps(entry['path']) or [entry['control']]
                problem = desktop.click(current, steps)
                if problem:
                    raise LookupError(problem)
                current = desktop.wait_new_window(known)
                if current is None:
                    raise TimeoutError('no new window after click')
                opened.append(current)
            status['title'] = capture(desktop, current, args.out / target, not args.no_tab_order)
            status['result'] = 'captured'
            for window in reversed(opened):
                known = {w.handle for w in desktop.windows()}
                desktop.close(window)
                time.sleep(0.5)
                surprise = [w for w in desktop.windows() if w.handle not in known]
                if surprise:  # a confirmation on close: record it, then restart cleanly
                    capture(desktop, surprise[0], args.out / target / '_on_close', False)
                    raise RuntimeError('dialog on close; restarted')
        except Exception as error:
            status.setdefault('result', 'failed')
            status['error'] = f'{type(error).__name__}: {error}'
            desktop.kill()
            time.sleep(1)
            desktop, main_window = start()
        now = data_files(data_dir)
        if changed(baseline, now):
            status['data_changed'] = changed(baseline, now)
            report['windows'][target] = status
            report['stopped'] = f'data files changed after {target}: restore the copy before continuing'
            break
        report['windows'][target] = status
        (args.out / 'capture-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    desktop.kill()
    report['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    (args.out / 'capture-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    done = sum(1 for s in report['windows'].values() if s.get('result') == 'captured')
    print(f'captured {done} of {len(chains)} routable windows; stopped: {report["stopped"]}')


if __name__ == '__main__':
    main()
