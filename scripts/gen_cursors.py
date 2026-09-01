"""Regenerate the map drag-cursor PNGs embedded in css/styles.css.

Run from the repo root:

    python scripts/gen_cursors.py

Prints the two `cursor:` declarations (base64 PNG data URIs) to paste into the
`#cm-map.leaflet-grab` / `.leaflet-dragging #cm-map` rules in css/styles.css.

Why PNG and not an inline SVG cursor: Chrome re-rasterises an SVG `cursor:`
image every time the cursor value changes — grab<->grabbing on every drag, and
grab<->pointer whenever the pointer skims a marker — and paints the native
fallback hand for those frames, which reads as a flicker on fast mouse
movement. A pre-rasterised 32px PNG is decoded once and cached by URL, so the
switch is instant. (Same reason index.html ships PNG favicons.)

Rendering matches scripts/gen_favicons.py: svglib + reportlab renderPM (the
rlPyCairo backend), 4x supersample, Pillow Lanczos downscale. Install with:

    pip install svglib reportlab rlPyCairo pillow

Hand shapes are the Lucide "hand" (open) and "grab" (curled) icons, ISC
license — white fill + dark-green #1a3a2a outline + a white halo so they stay
legible over darker basemap tiles and labels.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from reportlab.lib.colors import Color
from svglib.svglib import svg2rlg

TRANSPARENT = Color(1, 1, 1, alpha=0)
SUPERSAMPLE = 4
SIZE = 32
HOTSPOT = "13 12"

# Lucide icon paths (24x24 viewBox).
HAND = (
    "<path d='M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2'/>"
    "<path d='M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2'/>"
    "<path d='M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8'/>"
    "<path d='M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34"
    "l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15'/>"
)
GRAB = (
    "<path d='M18 11.5V9a2 2 0 0 0-2-2a2 2 0 0 0-2 2v1.4'/>"
    "<path d='M14 10V8a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2'/>"
    "<path d='M10 9.9V9a2 2 0 0 0-2-2a2 2 0 0 0-2 2v5'/>"
    "<path d='M6 14a2 2 0 0 0-2-2a2 2 0 0 0-2 2'/>"
    "<path d='M18 11a2 2 0 1 1 4 0v3a8 8 0 0 1-8 8h-4a8 8 0 0 1-8-8 2 2 0 1 1 4 0'/>"
)


def svg(paths: str) -> str:
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' "
        "viewBox='0 0 24 24' stroke-linecap='round' stroke-linejoin='round'>"
        f"<g fill='none' stroke='#ffffff' stroke-width='3.5'>{paths}</g>"
        f"<g fill='#ffffff' stroke='#1a3a2a' stroke-width='2'>{paths}</g>"
        "</svg>"
    )


def data_uri(paths: str) -> str:
    tmp = Path("_cursor_tmp.svg")
    tmp.write_text(svg(paths), encoding="utf-8")
    try:
        drawing = svg2rlg(str(tmp))
        dpi = 72.0 * (SIZE * SUPERSAMPLE) / drawing.width
        im = renderPM.drawToPIL(drawing, dpi=dpi, bg=TRANSPARENT, backendFmt="RGBA")
        im = im.convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
        # 2 ink colours + antialiasing -> an octree palette is lossless enough
        # and cuts the data URI to ~1 KB (a 32-bit PNG is ~3x bigger).
        im = im.quantize(colors=64, method=Image.FASTOCTREE, dither=Image.NONE)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
    finally:
        tmp.unlink(missing_ok=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def main() -> None:
    grab = data_uri(HAND)
    grabbing = data_uri(GRAB)
    print(f"/* {SIZE}px PNG, ~{len(grab)}/{len(grabbing)} B - see scripts/gen_cursors.py */")
    print("#cm-map.leaflet-grab {")
    print(f'  cursor: url("{grab}") {HOTSPOT}, grab;')
    print("}")
    print(".leaflet-dragging #cm-map,")
    print("#cm-map.leaflet-dragging {")
    print(f'  cursor: url("{grabbing}") {HOTSPOT}, grabbing;')
    print("}")


if __name__ == "__main__":
    main()
