"""Regenerate the favicon PNGs from assets/icons/favicon.svg.

Run from the repo root:

    python scripts/gen_favicons.py

Produces, in assets/icons/:
    favicon-48.png       48x48   transparent   (Google's minimum for search)
    favicon-96.png       96x96   transparent   (crisper tab / search icon)
    apple-touch-icon.png 180x180 cream ground  (iOS home screen)
    icon-192.png         192x192 transparent   (PWA manifest, "any")
    icon-512.png         512x512 transparent   (PWA manifest, "any", splash)
    icon-maskable-512.png 512x512 cream ground, pin and check badge inside the
                         maskable safe zone (PWA manifest, "maskable": Android crops it)

favicon.svg is the header's brand mark (pin + check badge) with fixed colors
(#2d6a4f and white) and stays the source of truth; index.html lists the PNGs first
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

CREAM = (253, 250, 245, 255)  # #fdfaf5, the site's base background
VIEWBOX = 24
# Bounding box of the mark in favicon.svg units (pin 4..20 x 2..22.3, badge
# reaching 22.45 with its stroke). A padded icon centres this box, not the
# viewBox, so the mark sits in the middle of the maskable circle.
MARK_BOX = (4.0, 2.0, 22.45, 22.3)

# Probe points in favicon.svg units: (x, y, expected colour).
PROBES = {
    "pin body": (8.0, 12.5, "green"),
    "pin centre dot": (12.0, 10.0, "white"),
    "badge inside": (15.0, 14.5, "white"),
    "check mark": (17.85, 15.75, "green"),
}

# name -> (size, opaque background or None, fraction of the canvas the mark
# fills). iOS flattens transparency to black, so the Apple touch icon gets a
# solid cream ground; the tab favicons stay transparent. The maskable icon's
# mark fits the central 80% circle Android keeps after cropping.
TARGETS = {
    "favicon-48.png": (48, None, 1.0),
    "favicon-96.png": (96, None, 1.0),
    "apple-touch-icon.png": (180, CREAM, 1.0),
    "icon-192.png": (192, None, 1.0),
    "icon-512.png": (512, None, 1.0),
    "icon-maskable-512.png": (512, CREAM, 0.6),
}


def placement(size: int, inner: float) -> tuple[int, int, int]:
    pin = round(size * inner)
    ox = oy = (size - pin) // 2
    if inner < 1.0:
        x0, y0, x1, y1 = MARK_BOX
        ox += round(pin * (VIEWBOX / 2 - (x0 + x1) / 2) / VIEWBOX)
        oy += round(pin * (VIEWBOX / 2 - (y0 + y1) / 2) / VIEWBOX)
    return pin, ox, oy


def render(size: int, bg, inner: float, dest: Path) -> None:
    drawing = svg2rlg(str(SRC))
    pin, ox, oy = placement(size, inner)
    dpi = 72.0 * (pin * SUPERSAMPLE) / drawing.width
    im = renderPM.drawToPIL(drawing, dpi=dpi, bg=TRANSPARENT, backendFmt="RGBA")
    im = im.convert("RGBA").resize((pin, pin), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), bg or (0, 0, 0, 0))
    canvas.alpha_composite(im, (ox, oy))
    canvas.save(dest, "PNG")


def verify(dest: Path, size: int, bg, inner: float) -> None:
    opaque_bg = bg is not None
    with Image.open(dest) as im:
        assert im.size == (size, size), f"{dest.name}: wrong size {im.size}"
        assert im.mode == "RGBA", f"{dest.name}: wrong mode {im.mode}"
        px = im.load()
        pin, ox, oy = placement(size, inner)
        probes = {
            label: (px[ox + int(pin * x / VIEWBOX), oy + int(pin * y / VIEWBOX)], colour)
            for label, (x, y, colour) in PROBES.items()
        }
        corner = px[1, 1]
        opaque = sum(
            1 for y in range(size) for x in range(size) if px[x, y][3] > 10
        ) / (size * size)
        print(
            f"  {dest.name:22} {im.size[0]:>3}x{im.size[1]:<3}  "
            f"{dest.stat().st_size:>6} B  opaque={opaque:5.1%}  "
            f"corner={corner}"
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
            print(f"    mark reaches {radius:.0f}px from the centre; safe zone {size * 0.4:.0f}px")
            assert radius <= size * 0.4, f"{dest.name}: mark leaves the safe zone ({radius:.0f}px)"
        for label, (pixel, colour) in probes.items():
            if colour == "green":
                ok = pixel[3] > 200 and pixel[1] > pixel[0] and pixel[1] > pixel[2] and min(pixel[:3]) < 160
            else:
                ok = pixel[3] > 200 and min(pixel[:3]) > 200
            assert ok, f"{dest.name}: {label} not {colour}: {pixel}"


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
