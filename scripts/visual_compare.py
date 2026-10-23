#!/usr/bin/env python3
"""How close a new screen looks to the legacy one: two scores and a side-by-side image for the human.

  pixel similarity  colors and skin: 100 − mean absolute difference (grey levels, lightly blurred), in %
  edge overlap      layout: share of edges (box borders, text, lines) found at the same place within 2 px (F1), in %

Both images are compared at the legacy image's size; the new screenshot must show the same area (the whole window,
title bar included when the legacy image has one). Requires Pillow (`python3 -m pip install pillow`). The scores
rank screens and show progress; a human approves the final look from the side-by-side image.
"""
import argparse
from datetime import date
import json
import os
from pathlib import Path


def compare(legacy_path, new_path, out=None):
    from PIL import Image, ImageChops, ImageFilter, ImageStat
    legacy = Image.open(legacy_path).convert('RGB')
    new = Image.open(new_path).convert('RGB').resize(legacy.size, Image.LANCZOS)
    grey = lambda im: im.convert('L').filter(ImageFilter.GaussianBlur(1))
    difference = ImageChops.difference(grey(legacy), grey(new))
    pixel = 100 * (1 - ImageStat.Stat(difference).mean[0] / 255)
    inner = (2, 2, legacy.width - 2, legacy.height - 2)  # the edge filter marks the image's own border: drop it
    edges = lambda im: im.convert('L').filter(ImageFilter.FIND_EDGES).crop(inner).point(lambda v: 255 if v > 40 else 0)
    a, b = edges(legacy), edges(new)
    near = lambda im: im.filter(ImageFilter.MaxFilter(5))  # within 2 px
    count = lambda im: sum(1 for v in im.getdata() if v)
    hits_a = count(ImageChops.multiply(a, near(b)))
    hits_b = count(ImageChops.multiply(b, near(a)))
    total_a, total_b = count(a), count(b)
    recall = hits_a / total_a if total_a else 1.0
    precision = hits_b / total_b if total_b else 1.0
    edge = 100 * (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    if out:
        heat = difference.point(lambda v: min(255, v * 4)).convert('RGB')
        heat = ImageChops.multiply(heat, Image.new('RGB', heat.size, (255, 60, 60)))
        sheet = Image.new('RGB', (legacy.width * 3 + 20, legacy.height), (255, 255, 255))
        for index, image in enumerate((legacy, new, heat)):
            sheet.paste(image, (index * (legacy.width + 10), 0))
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out)
    return {'pixel_similarity': round(pixel, 1), 'edge_overlap': round(edge, 1), 'size': list(legacy.size)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('legacy', type=Path, help='legacy image, e.g. docs/evidence/images/WIN_X.jpg')
    parser.add_argument('new', type=Path, help='screenshot of the new screen, same area')
    parser.add_argument('--out', type=Path, help='side-by-side image: legacy | new | differences')
    parser.add_argument('--record', type=Path, help='save the scores as JSON for the progress page, e.g. '
                                                    'docs/evidence/visual/<WINDOW>.json')
    args = parser.parse_args()
    result = compare(args.legacy, args.new, args.out)
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        here = lambda path: os.path.relpath(path) if path else None  # repository-relative: no machine paths
        args.record.write_text(json.dumps({**result, 'legacy': here(args.legacy), 'new': here(args.new),
                                           'side_by_side': here(args.out),
                                           'date': date.today().isoformat()}, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
