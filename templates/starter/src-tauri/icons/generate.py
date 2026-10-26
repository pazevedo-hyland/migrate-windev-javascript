#!/usr/bin/env python3
"""Recreate the original PNG/ICO starter icon with the Python standard library.

Geometry and colors match icon.svg. The ICO embeds a 256px PNG; no graphics tool,
font, third-party image, or platform-specific binary is needed.
"""
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parent


def rounded(x, y, left, top, width, height, radius):
    if not (left <= x < left + width and top <= y < top + height):
        return False
    cx = max(left + radius, min(x, left + width - radius))
    cy = max(top + radius, min(y, top + height - radius))
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2


def polygon(x, y, points):
    inside = False
    previous = points[-1]
    for point in points:
        ax, ay = previous
        bx, by = point
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
        previous = point
    return inside


def sample(x, y):
    color = (0, 0, 0, 0)
    if rounded(x, y, 2, 2, 60, 60, 13):
        color = (32, 51, 76, 255)
    panel = rounded(x, y, 12, 14, 40, 36, 4)
    if panel:
        color = (246, 249, 252, 255)
    if panel and y < 23:
        color = (118, 185, 239, 255)
    if rounded(x, y, 17, 29, 12, 4, 1) or rounded(x, y, 17, 38, 12, 4, 1):
        color = (157, 174, 193, 255)
    if polygon(x, y, [(34, 34), (43, 34), (43, 29), (52, 36), (43, 43), (43, 38), (34, 38)]):
        color = (48, 109, 167, 255)
    return color


def png(size):
    pixels = bytearray()
    for py in range(size):
        pixels.append(0)  # PNG row filter: none.
        for px in range(size):
            samples = [sample((px + (sx + .5) / 4) * 64 / size, (py + (sy + .5) / 4) * 64 / size)
                       for sy in range(4) for sx in range(4)]
            alpha = sum(pixel[3] for pixel in samples)
            # Average premultiplied colors so transparent corners have clean edges.
            rgb = [round(sum(pixel[channel] * pixel[3] for pixel in samples) / alpha) if alpha else 0 for channel in range(3)]
            pixels.extend([*rgb, round(alpha / 16)])
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(pixels), 9)) + chunk(b'IEND', b'')


def main():
    (ROOT / 'icon.png').write_bytes(png(128))
    image = png(256)
    # ICONDIR + ICONDIRENTRY; zero width/height encode 256 pixels.
    ico = struct.pack('<3H', 0, 1, 1) + struct.pack('<4B2H2I', 0, 0, 0, 0, 1, 32, len(image), 22) + image
    (ROOT / 'icon.ico').write_bytes(ico)


if __name__ == '__main__':
    main()
