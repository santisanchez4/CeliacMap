"""Android launcher icons for the app, resized from the site's maskable icon.

    python apps/mobile/scripts/gen_android_icons.py      (from the repo root)

Source: assets/icons/icon-maskable-512.png (scripts/gen_favicons.py): cream ground, pin and check badge
inside the central 60%, which also fits the adaptive-icon safe zone (66 of 108 dp). No new artwork.
"""
from pathlib import Path

from PIL import Image, ImageDraw

SOURCE = Path("assets/icons/icon-maskable-512.png")
RES = Path("apps/mobile/android/app/src/main/res")
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def resized(size: int) -> Image.Image:
    return Image.open(SOURCE).convert("RGBA").resize((size, size), Image.LANCZOS)


def round_icon(size: int) -> Image.Image:
    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
    icon = resized(size)
    icon.putalpha(mask.resize((size, size), Image.LANCZOS))
    return icon


def main() -> int:
    for name, factor in DENSITIES.items():
        folder = RES / f"mipmap-{name}"
        legacy, adaptive = round(48 * factor), round(108 * factor)
        resized(legacy).save(folder / "ic_launcher.png")
        round_icon(legacy).save(folder / "ic_launcher_round.png")
        resized(adaptive).save(folder / "ic_launcher_foreground.png")
        print(f"mipmap-{name}: {legacy}px launcher + round, {adaptive}px adaptive foreground")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
