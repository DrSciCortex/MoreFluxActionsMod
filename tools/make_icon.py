# SPDX-FileCopyrightText: 2026 DrSciCortex
#
# SPDX-License-Identifier: MIT

"""Make the mod's icons from the source art (a picture on a white background):

    python tools/make_icon.py [images/icon_source.png]

writes icon.png (256×256, the Thunderstore package's icon) and images/icon_512.png (the README's). The white
around the picture, including the gaps that reach its edge, becomes transparent: the white connected to the
border is found by a flood fill, and its antialiased rim is unblended from white so the edges stay soft on any
background. White inside the picture stays. The picture is then cropped square around its content.
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEAR_WHITE = 200            # every channel above this: background candidate
RIM_PX = 2                  # the antialiased edge, grown into from the background
OPACITY_GAIN = 1.1          # a little more opacity on the soft edge (keeps it from looking washed out)


def transparent(img):
    a = np.asarray(img.convert("RGB")).astype(np.float64)
    near = Image.fromarray(((a.min(axis=2) > NEAR_WHITE) * 255).astype(np.uint8)).copy()   # copy: writable
    h, w = near.height, near.width
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2), (w - 1, h // 2),
                 (w // 2, h - 1)]:
        if near.getpixel(seed) == 255:
            ImageDraw.floodfill(near, seed, 128)
    background = Image.fromarray(((np.asarray(near) == 128) * 255).astype(np.uint8))
    rim = np.asarray(background.filter(ImageFilter.MaxFilter(2 * RIM_PX + 1))) > 0
    # Unblend from white: alpha is how far a pixel is from white; its colour is what, over white, gives it.
    alpha = np.where(rim, np.clip((255.0 - a).max(axis=2) / 255.0 * OPACITY_GAIN, 0, 1), 1.0)
    rgb = np.where(rim[..., None], np.clip(255.0 - (255.0 - a) / np.maximum(alpha, 1e-3)[..., None], 0, 255), a)
    return Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA").copy()


def square_crop(img, margin=0.04):
    alpha = np.asarray(img)[..., 3]
    ys, xs = np.nonzero(alpha > 8)
    side = int(max(xs.max() - xs.min(), ys.max() - ys.min()) * (1 + margin))
    cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
    left, top = cx - side // 2, cy - side // 2
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(img.crop((left, top, left + side, top + side)), (0, 0))
    return out


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "images", "icon_source.png")
    icon = square_crop(transparent(Image.open(source)))
    for path, size in ((os.path.join(ROOT, "icon.png"), 256), (os.path.join(ROOT, "images", "icon_512.png"), 512)):
        icon.resize((size, size), Image.LANCZOS).save(path, optimize=True)
        print(f"wrote {os.path.relpath(path, ROOT)} ({size}×{size})")


if __name__ == "__main__":
    main()
