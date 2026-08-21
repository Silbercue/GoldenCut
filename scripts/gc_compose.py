#!/usr/bin/env python3
"""gc_compose — Beweisbild: vorher | nachher | Differenz nebeneinander.

Aufruf: gc_compose.py before.png after.png out.png [--title "Leitner-Kachel"] [--index-before 54 --index-after 91]
"""

import argparse
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GUT = 24
BAND = 44
BG = (246, 244, 240)
INK = (40, 40, 40)


def load(p):
    return Image.open(p).convert("RGB")


def font(size):
    for name in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def diff_image(a, b):
    h = max(a.height, b.height); w = max(a.width, b.width)
    A = np.full((h, w, 3), 255, np.uint8); B = A.copy()
    A[:a.height, :a.width] = np.asarray(a); B[:b.height, :b.width] = np.asarray(b)
    d = np.abs(A.astype(int) - B.astype(int)).sum(axis=2)
    mask = d > 40
    out = (A.astype(float) * 0.25 + 255 * 0.75).astype(np.uint8)  # Vorher stark aufgehellt
    out[mask] = (220, 40, 40)
    return Image.fromarray(out), float(mask.mean() * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before"); ap.add_argument("after"); ap.add_argument("out")
    ap.add_argument("--title", default="goldencut")
    ap.add_argument("--index-before", type=float, default=None)
    ap.add_argument("--index-after", type=float, default=None)
    args = ap.parse_args()

    a, b = load(args.before), load(args.after)
    d, pct = diff_image(a, b)
    panels = [("vorher" + (f"  ·  Index {args.index_before:.0f} %" if args.index_before is not None else ""), a),
              ("nachher" + (f"  ·  Index {args.index_after:.0f} %" if args.index_after is not None else ""), b),
              (f"Differenz  ·  {pct:.1f} % der Pixel", d)]
    h = max(p.height for _, p in panels)
    w = sum(p.width for _, p in panels) + GUT * (len(panels) + 1)
    canvas = Image.new("RGB", (w, h + BAND * 2 + GUT), BG)
    dr = ImageDraw.Draw(canvas)
    f_title, f_lab = font(22), font(18)
    dr.text((GUT, 12), args.title, fill=INK, font=f_title)
    x = GUT
    for lab, img in panels:
        dr.text((x, BAND + 8), lab, fill=INK, font=f_lab)
        canvas.paste(img, (x, BAND * 2))
        x += img.width + GUT
    canvas.save(args.out)
    print(f"{args.out}  (Differenz {pct:.1f} % der Pixel)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
