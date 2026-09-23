"""Same square/solid-background treatment as gen_instagram_logo.py, but using
the actual favicon.svg (pin + dot only, no check badge) instead of the
fuller header brand mark — for side-by-side comparison.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from reportlab.lib.colors import Color
from svglib.svglib import svg2rlg

SRC = Path("assets/icons/favicon.svg")
DEST = Path("outputs/celiacmap-instagram-logo-favicon-variant.png")
CANVAS = 1080
MARK_FRACTION = 0.62
BG = (253, 250, 245, 255)
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
    canvas = canvas.convert("RGB")
    canvas.save(DEST, "PNG")
    print(f"ok: {DEST} {CANVAS}x{CANVAS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
