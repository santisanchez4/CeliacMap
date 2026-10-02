"""Regenerate the favicon PNGs from assets/icons/favicon.svg.

Run from the repo root:

    python scripts/gen_favicons.py

Produces, in assets/icons/:
    favicon-48.png       48x48   transparent   (Google's minimum for search)
    favicon-96.png       96x96   transparent   (crisper tab / search icon)
    apple-touch-icon.png 180x180 white ground  (iOS home screen)
    icon-192.png         192x192 transparent   (PWA manifest, "any")
    icon-512.png         512x512 transparent   (PWA manifest, "any", splash)
    icon-maskable-512.png 512x512 off-white ground, pin inside the maskable
                         safe zone (PWA manifest, "maskable": Android crops it)

favicon.svg stays the source of truth; index.html lists the PNGs first
(Google Search recommends PNG as the primary favicon format — SVG support in
search results is inconsistent), then the SVG, then the Apple touch icon.

Rendering: cairosvg has no usable Windows build (cairocffi can't find
libcairo-2.dll and ships no cp314 wheel), so this uses svglib + reportlab's
renderPM via the rlPyCairo backend, which binds the self-contained pycairo
wheel. Install with:

    pip install svglib reportlab rlPyCairo pillow

Scaling is done purely through renderPM's `dpi` argument — a manual
Drawing.scale() fights svglib's own unit transform and displaces the inner
shapes. Each icon is rendered at 4x and Lanczos-downscaled.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from reportlab.lib.colors import Color
from svglib.svglib import svg2rlg

SRC = Path("assets/icons/favicon.svg")
OUT_DIR = Path("assets/icons")
TRANSPARENT = Color(1, 1, 1, alpha=0)
SUPERSAMPLE = 4

WHITE = (255, 255, 255, 255)
OFF_WHITE = (253, 250, 245, 255)  # #fdfaf5, the site's base background

# name -> (size, opaque background or None, fraction of the canvas the pin
# fills). iOS flattens transparency to black, so the Apple touch icon gets a
# solid white ground; the tab favicons stay transparent. The maskable icon's
# pin fits the central 80% circle Android keeps after cropping.
TARGETS = {
    "favicon-48.png": (48, None, 1.0),
    "favicon-96.png": (96, None, 1.0),
    "apple-touch-icon.png": (180, WHITE, 1.0),
    "icon-192.png": (192, None, 1.0),
    "icon-512.png": (512, None, 1.0),
    "icon-maskable-512.png": (512, OFF_WHITE, 0.6),
}


def render(size: int, bg, inner: float, dest: Path) -> None:
    drawing = svg2rlg(str(SRC))
    pin = round(size * inner)
    dpi = 72.0 * (pin * SUPERSAMPLE) / drawing.width
    im = renderPM.drawToPIL(drawing, dpi=dpi, bg=TRANSPARENT, backendFmt="RGBA")
    im = im.convert("RGBA").resize((pin, pin), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), bg or (0, 0, 0, 0))
    offset = (size - pin) // 2
    canvas.alpha_composite(im, (offset, offset))
    canvas.save(dest, "PNG")


def verify(dest: Path, size: int, bg, inner: float) -> None:
    opaque_bg = bg is not None
    with Image.open(dest) as im:
        assert im.size == (size, size), f"{dest.name}: wrong size {im.size}"
        assert im.mode == "RGBA", f"{dest.name}: wrong mode {im.mode}"
        px = im.load()
        pin = round(size * inner)
        offset = (size - pin) // 2
        dot = px[size // 2, offset + int(pin * 0.42)]     # the pin's white centre dot
        body = px[size // 2, offset + int(pin * 0.66)]    # lower pin body (green)
        corner = px[1, 1]
        opaque = sum(
            1 for y in range(size) for x in range(size) if px[x, y][3] > 10
        ) / (size * size)
        print(
            f"  {dest.name:22} {im.size[0]:>3}x{im.size[1]:<3}  "
            f"{dest.stat().st_size:>6} B  opaque={opaque:5.1%}  "
            f"dot={dot}  body={body}  corner={corner}"
        )
        if opaque_bg:
            assert corner == bg, f"{dest.name}: corner {corner}"
            assert opaque == 1.0, f"{dest.name}: not fully opaque ({opaque:.1%})"
        else:
            assert corner[3] == 0, f"{dest.name}: corner not transparent {corner}"
            assert 0.20 < opaque < 0.60, f"{dest.name}: opaque {opaque:.1%}"
        if inner < 1.0:
            radius = max(
                ((x - size / 2) ** 2 + (y - size / 2) ** 2) ** 0.5
                for y in range(size) for x in range(size)
                if px[x, y][:3] != bg[:3]
            )
            assert radius <= size * 0.4, f"{dest.name}: pin leaves the safe zone ({radius:.0f}px)"
        assert body[3] > 200 and body[1] > body[0] and body[1] > body[2], (
            f"{dest.name}: pin body not green: {body}"
        )
        assert dot[3] > 200 and min(dot[:3]) > 200, (
            f"{dest.name}: centre dot not white: {dot}"
        )


def main() -> int:
    if not SRC.exists():
        print(f"error: {SRC} not found — run from the repo root", file=sys.stderr)
        return 1
    print(f"favicon.svg -> {len(TARGETS)} PNGs")
    for name, (size, bg, inner) in TARGETS.items():
        dest = OUT_DIR / name
        render(size, bg, inner, dest)
        verify(dest, size, bg, inner)
    print("ok: all PNGs generated and verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
