"""Render the CeliacMap header brand mark (pin + check badge) as a square
Instagram profile-photo PNG: solid background (IG crops the avatar into a
circle, so no transparency), generous padding so the mark isn't clipped by
that circular crop, at 1080x1080 (Instagram's own recommended size, well
above the 500x500 floor).

Reuses this repo's existing favicon toolchain (scripts/gen_favicons.py):
svglib + reportlab's renderPM via the rlPyCairo backend, supersampled 4x and
Lanczos-downscaled.

Run from the repo root:
    python outputs/gen_instagram_logo.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from reportlab.lib.colors import Color
from svglib.svglib import svg2rlg

SRC = Path("outputs/brand-mark-standalone.svg")
DEST = Path("outputs/celiacmap-instagram-logo.png")
CANVAS = 1080
MARK_FRACTION = 0.62  # mark occupies this fraction of the canvas, centered
BG = (253, 250, 245, 255)  # --color-bg, the site's warm off-white
TRANSPARENT = Color(1, 1, 1, alpha=0)
SUPERSAMPLE = 4


def main() -> int:
    mark_size = round(CANVAS * MARK_FRACTION)
    drawing = svg2rlg(str(SRC))
    dpi = 72.0 * (mark_size * SUPERSAMPLE) / drawing.width
    mark = renderPM.drawToPIL(drawing, dpi=dpi, bg=TRANSPARENT, backendFmt="RGBA")
    mark = mark.convert("RGBA").resize((mark_size, mark_size), Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS, CANVAS), BG)
    offset = ((CANVAS - mark_size) // 2, (CANVAS - mark_size) // 2)
    canvas.alpha_composite(mark, offset)
    canvas = canvas.convert("RGB")  # drop alpha entirely: fully solid, no transparency anywhere
    canvas.save(DEST, "PNG")

    with Image.open(DEST) as im:
        assert im.size == (CANVAS, CANVAS)
        assert im.mode == "RGB"
        corner = im.getpixel((2, 2))
        assert corner == BG[:3], f"corner not solid bg: {corner}"
    print(f"ok: {DEST} {CANVAS}x{CANVAS} solid background, mark {mark_size}px centered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
