"""Read-only capture of a running WINDEV application: for every window of the process (the main frame, each MDI
child, each dialog) an image drawn by the window itself (PrintWindow, also when covered) and its controls as UI
Automation reports them (caption, class, type, control id, box relative to the window's client area, visible).
Nothing is clicked or typed (with --activate each MDI child is brought forward with WM_MDIACTIVATE, as clicking its tab does, and the active one is restored). Output (ignored folder: it can show real data):
  <out>/<n>-<title>.png and <out>/<n>-<title>.json

  py -3 scripts/live_parity/windev_live_capture.py <pid> <out folder> [--activate]
"""
import ctypes
import json
import re
import sys
import warnings
from ctypes import wintypes
from pathlib import Path

warnings.filterwarnings('ignore')
from PIL import Image  # noqa: E402
from pywinauto import Desktop  # noqa: E402

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
user32.SetProcessDPIAware()
PW_RENDERFULLCONTENT = 2


def snapshot(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]

    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory_dc)
    user32.ReleaseDC(hwnd, window_dc)
    return Image.frombuffer('RGBA', (width, height), buffer, 'raw', 'BGRA', 0, 1).convert('RGB')


def client_origin(hwnd):
    point = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    return point.x, point.y, rect.right, rect.bottom


def controls_of(window, origin):
    out = []

    def walk(element, level):
        info = element.element_info
        rect = info.rectangle
        out.append({'level': level, 'name': info.name, 'class': info.class_name, 'type': info.control_type,
                    'id': info.automation_id, 'x': rect.left - origin[0], 'y': rect.top - origin[1],
                    'width': rect.width(), 'height': rect.height(), 'visible': bool(info.visible),
                    'enabled': bool(info.enabled)})
        # another window (an MDI child, a dialog) is captured on its own
        for child in element.children():
            if child.element_info.class_name == 'WinDevObject' and child.element_info.control_type == 'Window':
                continue
            walk(child, level + 1)

    walk(window, 0)
    return out


def windows_of(pid):
    desk = Desktop(backend='uia')
    found = []
    for top in desk.windows():
        if top.process_id() != pid:
            continue
        found.append(top)
        stack = [top]
        while stack:
            for child in stack.pop().children():
                info = child.element_info
                if info.class_name == 'WinDevObject' and info.control_type == 'Window':
                    found.append(child)
                if info.control_type in ('Pane', 'Window'):
                    stack.append(child)
    return found


WM_MDIACTIVATE, WM_MDIGETACTIVE = 0x0222, 0x0229


def main():
    pid, out = int(sys.argv[1]), Path(sys.argv[2])
    activate = '--activate' in sys.argv
    out.mkdir(parents=True, exist_ok=True)
    windows = windows_of(pid)
    mdi = {w.element_info.handle: user32.GetParent(w.element_info.handle) for w in windows[1:]}
    client = next(iter(mdi.values()), None)
    was_active = user32.SendMessageW(client, WM_MDIGETACTIVE, 0, 0) if client else None
    for index, window in enumerate(windows):
        hwnd = window.element_info.handle
        if activate and hwnd in mdi:
            # bring the MDI child forward (what clicking its tab does) so that it draws itself
            user32.SendMessageW(mdi[hwnd], WM_MDIACTIVATE, hwnd, 0)
            import time
            time.sleep(0.6)
        title = window.window_text()
        slug = re.sub(r'[^\w-]+', '_', title)[:60] or 'window'
        origin = client_origin(hwnd)
        image = snapshot(hwnd)
        if image:
            image.save(out / f'{index}-{slug}.png')
        rect = window.element_info.rectangle
        record = {'title': title, 'hwnd': hwnd, 'window': [rect.left, rect.top, rect.width(), rect.height()],
                  'client': {'x': origin[0] - rect.left, 'y': origin[1] - rect.top, 'width': origin[2], 'height': origin[3]},
                  'controls': controls_of(window, origin)}
        (out / f'{index}-{slug}.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
        print(index, repr(title), record['window'], 'client', record['client'], len(record['controls']), 'controls')
    if activate and was_active:
        user32.SendMessageW(client, WM_MDIACTIVATE, was_active, 0)


if __name__ == '__main__':
    main()
