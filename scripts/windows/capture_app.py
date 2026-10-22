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


def match_layout(elements, layout, tolerance=3):
    """Pair UI Automation elements with legacy controls by position inside the window.

    elements: [(index, (left, top, right, bottom) relative to the window)]; layout: inspector items.
    Returns {index: legacy name}; each legacy control is used once, closest match first.
    """
    candidates = []
    for index, (left, top, right, bottom) in elements:
        for item in layout:
            if item.get('width') is None or item.get('height') is None:
                continue
            delta = max(abs(left - item['x']), abs(top - item['y']),
                        abs((right - left) - item['width']), abs((bottom - top) - item['height']))
            if delta <= tolerance:
                candidates.append((delta, index, item['name']))
    result, used = {}, set()
    for delta, index, name in sorted(candidates):
        if index not in result and name not in used:
            result[index] = name
            used.add(name)
    return result


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

    layouts = {}

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
                    # Wrappers cannot wait; a window specification for the same handle can.
                    self.app.window(handle=w.handle).wait('ready', timeout=self.timeout)
                    return w
            time.sleep(0.3)
        return None

    def elements(self, scopes, control_types):
        """(element, caption, automation id) for matching, de-duplicated across overlapping scopes."""
        found, seen = [], set()
        for scope in scopes:
            for d in scope.descendants():
                info = d.element_info
                key = tuple(info.runtime_id or ()) or id(d)
                if info.control_type in control_types and key not in seen:
                    seen.add(key)
                    found.append((d, d.window_text(), info.automation_id))
        return found

    @staticmethod
    def activate(element, leaf):
        for action in (('invoke',) if leaf else ('expand', 'invoke')) + ('click_input',):
            try:
                getattr(element, action)()
                return
            except Exception:
                continue

    def legacy_names(self, window, layout_name):
        """{element: legacy control name} for a window whose legacy layout is known."""
        layout = self.layouts.get((layout_name or '').lower())
        if not layout:
            return {}
        origin = window.rectangle()
        elements = [window] + window.descendants()
        positions = [(i, (r.left - origin.left, r.top - origin.top, r.right - origin.left, r.bottom - origin.top))
                     for i, r in ((i, e.rectangle()) for i, e in enumerate(elements))]
        return {elements[i]: name for i, name in match_layout(positions, layout).items()}

    def identify(self, window):
        """The legacy window whose layout matches the most elements (at least 3), or None."""
        best = max(((len(self.legacy_names(window, name)), name) for name in self.layouts), default=(0, None))
        return best[1] if best[0] >= 3 else None

    def find_window(self, legacy_name):
        """The visible window or owned dialog that is this legacy window, by layout."""
        for window in self.windows():
            for target in [window] + [c for c in window.children() if c.element_info.control_type == 'Window']:
                if self.identify(target) == legacy_name:
                    return target
        return None

    def run_steps(self, steps):
        """Scripted interaction by legacy names, e.g. a login: [{window, click|type, env|text}]."""
        for number, step in enumerate(steps, start=1):
            deadline, window = time.time() + self.timeout, None
            while window is None and time.time() < deadline:
                window = self.find_window(step['window'])
                time.sleep(0.3)
            if window is None:
                raise LookupError(f"step {number}: window {step['window']} not found")
            name = step.get('click') or step.get('type')
            element = self.by_position(window, name, step['window'])
            if element is None:
                raise LookupError(f"step {number}: {name} not found in {step['window']}")
            if 'click' in step:
                self.activate(element, True)
            else:
                value = os.environ.get(step['env'], '') if 'env' in step else step.get('text', '')
                try:
                    element.set_edit_text(value)
                except Exception:
                    element.set_focus()
                    self.send_keys('^a{DEL}')
                    self.send_keys(value, with_spaces=True)
            time.sleep(0.8)

    def by_position(self, window, control, layout_name):
        return next((e for e, name in self.legacy_names(window, layout_name).items()
                     if name.lower() == control.lower()), None)

    def click(self, window, control, layout_name=None):
        steps = [control] if not isinstance(control, list) else control
        if len(steps) > 1 or steps[0].upper().startswith(('OPT_', 'MENU_OPT_')):
            for number, step in enumerate(steps):
                # Submenus open as separate popup windows: search every window of the app after the first level.
                scopes = [window] if number == 0 else self.windows()
                item = best_match(step, self.elements(scopes, ('MenuItem',)))
                if item is None:
                    return f'menu item not found for {step}'
                self.activate(item, number == len(steps) - 1)
                time.sleep(0.4)
            return None
        button = best_match(steps[0], self.elements([window], ('Button', 'Image', 'Hyperlink', 'MenuItem')))
        if button is None:
            button = self.by_position(window, steps[0], layout_name)
        if button is None:
            return f'control not found for {steps[0]}'
        self.activate(button, True)
        return None

    def tree(self, window, layout_name=None):
        names = self.legacy_names(window, layout_name)
        origin = window.rectangle()
        out = []
        for d in [window] + window.descendants():
            r = d.rectangle()
            info = d.element_info
            out.append({'type': info.control_type, 'name': d.window_text(), 'automation_id': info.automation_id,
                        'legacy_name': names.get(d), 'class': info.class_name,
                        'rect': [r.left, r.top, r.right, r.bottom],
                        'rect_in_window': [r.left - origin.left, r.top - origin.top,
                                           r.right - origin.left, r.bottom - origin.top],
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
            r = info.rectangle
            key = (info.control_type, info.name, (r.left, r.top, r.right, r.bottom) if r else None)
            if key in seen:
                break
            seen.add(key)
            order.append({'type': info.control_type, 'name': info.name, 'automation_id': info.automation_id})
        return order

    def login(self, window, user, password):
        """Fill the first two edit fields through UI Automation, then confirm with Enter (the default button)."""
        edits = window.descendants(control_type='Edit')
        if len(edits) >= 2:
            for edit, value in ((edits[0], user), (edits[1], password)):
                try:
                    edit.set_edit_text(value)
                except Exception:
                    edit.set_focus()
                    self.send_keys('^a{DEL}')
                    self.send_keys(value, with_spaces=True)
            edits[1].set_focus()
        else:
            window.set_focus()
            self.send_keys(user, with_spaces=True)
            self.send_keys('{TAB}')
            self.send_keys(password, with_spaces=True)
        self.send_keys('{ENTER}')

    def close(self, window):
        """Close and wait until the window is gone; return a dialog that appeared instead, if any."""
        known = {w.handle for w in self.windows()}
        handle = window.handle
        window.close()
        deadline = time.time() + max(3, self.timeout / 2)
        while time.time() < deadline:
            surprise = [w for w in self.windows() if w.handle not in known]
            if surprise:
                return surprise[0]
            # UI Automation lists a dialog owned by the window as its child, not as a top-level window.
            try:
                owned = [c for c in window.children() if c.element_info.control_type == 'Window']
            except Exception:
                owned = []
            if owned:
                return owned[0]
            if not self.app.window(handle=handle).exists(timeout=0):
                return None
            time.sleep(0.3)
        raise RuntimeError('window did not close and no dialog appeared')

    def kill(self):
        self.app.kill()


def startup(args, desktop):
    """Observe only: capture each window (and owned dialog) that appears in the first seconds."""
    seen, captured = set(), []
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        for window in desktop.windows():
            for target in [window] + [c for c in window.children() if c.element_info.control_type == 'Window']:
                if target.handle in seen:
                    continue
                seen.add(target.handle)
                time.sleep(1)  # let the window finish drawing
                legacy = desktop.identify(target)
                name = f'{len(captured):02d}-' + (legacy or re.sub(r'[^\w-]+', '_', target.window_text() or 'untitled')[:40])
                capture(desktop, target, args.out / '_startup' / name, False, legacy)
                captured.append({'folder': name, 'title': target.window_text(), 'legacy_window': legacy,
                                 'controls': len(target.descendants())})
        time.sleep(0.5)
    desktop.kill()
    (args.out / 'startup-report.json').write_text(json.dumps(captured, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(captured, indent=2, ensure_ascii=False))


def probe(desktop, main_window, chains, main_name):
    """Go/no-go: does UI Automation expose the controls the first hop of each route needs?"""
    elements = [(d, d.window_text(), d.element_info.automation_id) for d in main_window.descendants()]
    menu_items = [e for e in elements if e[0].element_info.control_type == 'MenuItem']
    named = [e for e in elements if e[1] or e[2]]
    routes = {}
    for target, chain in chains.items():
        first = chain[0]
        if first['from'].lower() != main_name.lower():
            continue
        steps = menu_steps(first['path']) or [first['control']]
        pool = menu_items if steps[0].upper().startswith(('OPT_', 'MENU_OPT_')) else elements
        routes[target] = 'resolvable' if best_match(steps[0], pool) is not None else 'not found'
    found = sum(1 for v in routes.values() if v == 'resolvable')
    return {'controls': len(elements), 'named_controls': len(named), 'menu_items': len(menu_items),
            'first_hops_resolvable': f'{found}/{len(routes)}',
            'verdict': 'go' if routes and found >= len(routes) / 2 else 'no-go: inspect probe.json and tree.json',
            'routes': routes}


def capture(desktop, window, folder, tabs, layout_name=None):
    folder.mkdir(parents=True, exist_ok=True)
    window.capture_as_image().save(folder / 'screenshot.png')
    (folder / 'tree.json').write_text(json.dumps(desktop.tree(window, layout_name), indent=1, ensure_ascii=False),
                                      encoding='utf-8')
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
    parser.add_argument('--login-steps', type=Path,
                        help='JSON list of steps by legacy names, e.g. [{"window": "WIN_Acesso", "type": "EDT_x", '
                             '"env": "MIGRATION_APP_PASSWORD"}, {"window": "WIN_Acesso", "click": "BTN_OK"}]')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--dry-run', action='store_true', help='print the routes and exit')
    parser.add_argument('--startup-only', action='store_true',
                        help='launch, capture every window that appears (screenshot + tree) without clicking, exit')
    parser.add_argument('--probe', action='store_true',
                        help='start the app, check which first-hop routes UI Automation can resolve, then exit')
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    Desktop.layouts = {w['window'].lower(): w.get('layout', []) for w in plan['windows']}
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
        if args.login_steps and first is not None:
            capture(desktop, first, args.out / '_startup', False, desktop.identify(first))
            desktop.run_steps(json.loads(args.login_steps.read_text(encoding='utf-8')))
            deadline = time.time() + args.timeout
            while time.time() < deadline and desktop.find_window(args.main_window) is None:
                time.sleep(0.5)
            first = desktop.find_window(args.main_window)
        elif args.login and first is not None:
            # No tab-order capture here: moving focus before typing would put the user name in the wrong field.
            capture(desktop, first, args.out / '_startup', False)
            desktop.login(first, os.environ.get('MIGRATION_APP_USER', ''), os.environ.get('MIGRATION_APP_PASSWORD', ''))
            after = desktop.wait_new_window({first.handle})
            if after is not None and after.window_text() == first.window_text():
                parser.exit(1, 'login window still open after login\n')
            first = after
        return desktop, first

    if args.startup_only:
        startup(args, Desktop(args.app_dir / args.exe, args.app_dir, args.timeout))
        return
    desktop, main_window = start()
    if main_window is None:
        parser.exit(1, 'main window did not appear\n')
    capture(desktop, main_window, args.out / args.main_window, False, args.main_window)
    if args.probe:
        result = probe(desktop, main_window, chains, args.main_window)
        (args.out / 'probe.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        desktop.kill()
        print(json.dumps({k: v for k, v in result.items() if k != 'routes'}, indent=2, ensure_ascii=False))
        return
    baseline = data_files(data_dir)  # after startup: first-run setup writes are not the crawler's
    for target, chain in chains.items():
        status = {'route': [f"{e['from']}:{e['control']}" for e in chain]}
        try:
            current, opened = main_window, []
            for entry in chain:
                known = {w.handle for w in desktop.windows()}
                steps = menu_steps(entry['path']) or [entry['control']]
                problem = desktop.click(current, steps, entry['from'])
                if problem:
                    raise LookupError(problem)
                current = desktop.wait_new_window(known)
                if current is None:
                    raise TimeoutError('no new window after click')
                opened.append(current)
            status['title'] = capture(desktop, current, args.out / target, not args.no_tab_order, target)
            status['result'] = 'captured'
            for window in reversed(opened):
                surprise = desktop.close(window)
                if surprise is not None:  # a confirmation on close: record it, never answer it, restart cleanly
                    capture(desktop, surprise, args.out / target / '_on_close', False)
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
