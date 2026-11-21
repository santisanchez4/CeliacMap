"""Build supabase/functions/chat/barrios_data.ts from the official barrio boundaries of Montevideo and CABA.

The chat finds places by barrio with these polygons (barrios.ts): Google's addresses in Montevideo and Buenos Aires do
not name the barrio, so `address ilike '%Ciudad Vieja%'` found 0 of the 2 places inside it (docs/DECISIONS.md, «Barrios
del chat por coordenadas»).

Sources (both downloaded as published, nothing edited by hand):
  Montevideo  «BARRIOS DE MONTEVIDEO segun INE», Servicio de Geomática, Intendencia de Montevideo (origin: INE, Censo
              2011). Metadata 1277c8cd-3e7a-4afd-8289-aeae893ce0db on geoweb.montevideo.gub.uy/geonetwork:
              «De uso libre según resolución 640/10 del Intendente Municipal de Montevideo de fecha 22/02/2010».
              UTM zone 21S (EPSG:32721), reprojected here to WGS 84 longitude / latitude.
  CABA        «Barrios», Gobierno de la Ciudad de Buenos Aires, data.buenosaires.gob.ar/dataset/barrios. Licence CC BY 2.5 AR.

Each ring is simplified with Douglas-Peucker at TOLERANCE_M (10 m: 0 of the 106 approved places of both cities changed
barrio against the full polygons, measured 2026-11-20) and rounded to 5 decimals (~1 m).

Usage:
  python scripts/build_barrios.py                       # downloads both sources
  python scripts/build_barrios.py --montevideo-zip X.zip --caba-geojson Y.geojson
  python scripts/build_barrios.py ... --places places.json
      places.json = the output of
        node_modules/.bin/supabase db query --linked "select name, region, lat, lng from places where status='approved'
          and region in ('Montevideo','Ciudad Autónoma de Buenos Aires') order by region, name"
      Fails if any place falls in a different barrio after simplification, and writes barrios_places_fixture.ts, which
      barrios.test.ts uses to pin that every place keeps its barrio.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DATA = ROOT / "supabase/functions/chat/barrios_data.ts"
OUT_FIXTURE = ROOT / "supabase/functions/chat/barrios_places_fixture.ts"

MONTEVIDEO_URL = (
    "https://montevideo.gub.uy/app/geoserver/ows?service=WFS&version=1.1.0&request=GetFeature"
    "&typeName=mapstore-tematicas%3Azon_v_sig_barrios&outputFormat=SHAPE-ZIP&format_options=charset%3AUTF-8"
)
CABA_URL = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/innovacion-transformacion-digital/barrios/barrios.geojson"
TOLERANCE_M = 10.0
REGION_KEY = {"Montevideo": "montevideo", "Ciudad Autónoma de Buenos Aires": "caba"}

Ring = list[tuple[float, float]]


def utm21s_to_lnglat(e: float, n: float) -> tuple[float, float]:
    """WGS 84 / UTM zone 21S -> (longitude, latitude), the standard series inverse (sub-metre at this latitude)."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x, y = e - 500000.0, n - 10000000.0
    mu = (y / k0) / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu) + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
         + (151 * e1**3 / 96) * math.sin(6 * mu) + (1097 * e1**4 / 512) * math.sin(8 * mu))
    c1 = ep2 * math.cos(p) ** 2
    t1 = math.tan(p) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(p) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(p) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = p - (n1 * math.tan(p) / r1) * (
        d**2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720)
    lng = (d - (1 + 2 * t1 + c1) * d**3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120) / math.cos(p)
    return math.degrees(lng) - 57.0, math.degrees(lat)


def read_dbf(data: bytes) -> list[dict[str, str]]:
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields, i = [], 32
    while data[i] != 0x0D:
        fields.append((data[i:i + 11].split(b"\0")[0].decode("ascii"), data[i + 16]))
        i += 32
    rows = []
    for r in range(count):
        offset, row = header_len + r * record_len + 1, {}
        for name, length in fields:
            row[name] = data[offset:offset + length].decode("utf-8").strip()
            offset += length
        rows.append(row)
    return rows


def read_shp_rings(data: bytes) -> list[list[Ring]]:
    """Every polygon record as its rings, in UTM metres."""
    offset, shapes = 100, []
    while offset < len(data):
        _, words = struct.unpack(">ii", data[offset:offset + 8])
        rec = data[offset + 8:offset + 8 + words * 2]
        offset += 8 + words * 2
        if struct.unpack("<i", rec[:4])[0] != 5:
            raise SystemExit("unexpected shape type: only polygons are expected")
        n_parts, n_points = struct.unpack("<ii", rec[36:44])
        parts = list(struct.unpack(f"<{n_parts}i", rec[44:44 + 4 * n_parts]))
        base = 44 + 4 * n_parts
        points = [struct.unpack("<dd", rec[base + 16 * k:base + 16 * k + 16]) for k in range(n_points)]
        bounds = parts[1:] + [n_points]
        shapes.append([points[s:e] for s, e in zip(parts, bounds)])
    return shapes


def montevideo_barrios(zip_bytes: bytes) -> list[tuple[str, list[Ring]]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        shp = z.read(next(n for n in names if n.endswith(".shp")))
        dbf = z.read(next(n for n in names if n.endswith(".dbf")))
        prj = z.read(next(n for n in names if n.endswith(".prj"))).decode("utf-8", "replace")
    if "UTM zone 21S" not in prj:
        raise SystemExit(f"unexpected projection for Montevideo: {prj[:80]}")
    rows, shapes = read_dbf(dbf), read_shp_rings(shp)
    if len(rows) != len(shapes):
        raise SystemExit("dbf and shp record counts differ")
    return [(row["barrio"] if "barrio" in row else row["BARRIO"],
             [[utm21s_to_lnglat(x, y) for x, y in ring] for ring in rings]) for row, rings in zip(rows, shapes)]


def caba_barrios(geojson: dict) -> list[tuple[str, list[Ring]]]:
    out = []
    for feature in geojson["features"]:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        out.append((feature["properties"]["nombre"],
                    [[(float(x), float(y)) for x, y, *_ in ring] for polygon in polygons for ring in polygon]))
    return out


def _dp_keep(points: list[tuple[float, float]], tol: float) -> list[bool]:
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = points[a], points[b]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        best, index = -1.0, None
        for i in range(a + 1, b):
            px, py = points[i]
            d = abs(dy * (px - ax) - dx * (py - ay)) / length if length else math.hypot(px - ax, py - ay)
            if d > best:
                best, index = d, i
        if index is not None and best > tol:
            keep[index] = True
            stack += [(a, index), (index, b)]
    return keep


def simplify_ring(ring: Ring, tol_m: float = TOLERANCE_M) -> Ring:
    """Douglas-Peucker in local metres. A closed ring is split at its farthest point so both halves keep a span."""
    if len(ring) < 5:
        return ring
    kx, ky = 111320 * math.cos(math.radians(ring[0][1])), 110570
    metres = [(x * kx, y * ky) for x, y in ring]
    far = max(range(len(metres)), key=lambda i: math.hypot(metres[i][0] - metres[0][0], metres[i][1] - metres[0][1]))
    keep = _dp_keep(metres[:far + 1], tol_m) + _dp_keep(metres[far:], tol_m)[1:]
    return [p for p, k in zip(ring, keep) if k]


def ring_contains(ring: Ring, x: float, y: float) -> bool:
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def barrio_of(layer: list[tuple[str, list[Ring]]], x: float, y: float) -> list[str]:
    return [name for name, rings in layer if sum(ring_contains(r, x, y) for r in rings) % 2 == 1]


def to_ts(layers: dict[str, list[tuple[str, list[Ring]]]]) -> str:
    lines = [
        "// GENERATED by scripts/build_barrios.py — do not edit by hand; re-run the script to refresh it.",
        "//",
        "// Official barrio boundaries, simplified (Douglas-Peucker, 10 m) and rounded to 5 decimals:",
        "//   montevideo  «BARRIOS DE MONTEVIDEO segun INE» — Servicio de Geomática, Intendencia de Montevideo; origin:",
        "//               Instituto Nacional de Estadística (Censo 2011). «De uso libre según resolución 640/10 del",
        "//               Intendente Municipal de Montevideo de fecha 22/02/2010» (metadata",
        "//               1277c8cd-3e7a-4afd-8289-aeae893ce0db, geoweb.montevideo.gub.uy/geonetwork). Reprojected from UTM 21S.",
        "//   caba        «Barrios» — Gobierno de la Ciudad Autónoma de Buenos Aires, data.buenosaires.gob.ar/dataset/barrios,",
        "//               licence CC BY 2.5 AR (https://creativecommons.org/licenses/by/2.5/ar/).",
        "// Changes: simplified and rounded; names kept as published (barrios.ts maps them to display names).",
        "// Each ring is a flat [lng, lat, lng, lat, ...] list; a point is inside a barrio when an odd number of its rings",
        "// contain it (holes and multipolygons).",
        "",
        "export interface BarrioShape {",
        "  name: string;",
        "  bbox: [number, number, number, number];",
        "  rings: number[][];",
        "}",
        "",
        "export const BARRIO_SHAPES: Record<\"montevideo\" | \"caba\", BarrioShape[]> = {",
    ]
    for key, layer in layers.items():
        lines.append(f"  {key}: [")
        for name, rings in sorted(layer, key=lambda item: item[0]):
            flat = [[round(v, 5) for point in ring for v in point] for ring in rings]
            xs = [v for ring in flat for v in ring[0::2]]
            ys = [v for ring in flat for v in ring[1::2]]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
            lines.append(f"    {{ name: {json.dumps(name, ensure_ascii=False)}, bbox: {json.dumps(bbox)}, "
                         f"rings: {json.dumps(flat, separators=(',', ':'))} }},")
        lines.append("  ],")
    lines += ["};", ""]
    return "\n".join(lines)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "CeliacMap build_barrios"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--montevideo-zip", type=Path)
    parser.add_argument("--caba-geojson", type=Path)
    parser.add_argument("--places", type=Path, help="supabase db query output with name, region, lat, lng")
    args = parser.parse_args(argv)

    mvd_zip = args.montevideo_zip.read_bytes() if args.montevideo_zip else fetch(MONTEVIDEO_URL)
    caba_json = json.loads(args.caba_geojson.read_text(encoding="utf-8") if args.caba_geojson else fetch(CABA_URL))
    full = {"montevideo": montevideo_barrios(mvd_zip), "caba": caba_barrios(caba_json)}
    if len(full["montevideo"]) != 62 or len(full["caba"]) != 48:
        raise SystemExit(f"unexpected barrio counts: {len(full['montevideo'])} / {len(full['caba'])} (62 / 48 expected)")
    simple = {k: [(n, [simplify_ring(r) for r in rings]) for n, rings in layer] for k, layer in full.items()}

    OUT_DATA.write_text(to_ts(simple), encoding="utf-8", newline="\n")
    before = sum(len(r) for layer in full.values() for _, rings in layer for r in rings)
    after = sum(len(r) for layer in simple.values() for _, rings in layer for r in rings)
    print(f"{OUT_DATA.relative_to(ROOT)}: {after} of {before} points, {OUT_DATA.stat().st_size // 1024} KB")

    if args.places:
        text = args.places.read_text(encoding="utf-8")
        rows = json.loads(text[text.index("{"):])["rows"]
        fixture, drift = [], []
        for row in rows:
            key = REGION_KEY[row["region"]]
            x, y = float(row["lng"]), float(row["lat"])
            want, got = barrio_of(full[key], x, y), barrio_of(simple[key], x, y)
            if want != got or len(want) > 1:
                drift.append((row["name"], want, got))
            fixture.append({"city": key, "lat": y, "lng": x, "barrio": want[0] if want else None})
        if drift:
            print("barrio changed after simplification:", drift, file=sys.stderr)
            return 1
        fixture.sort(key=lambda p: (p["city"], p["lat"], p["lng"]))
        OUT_FIXTURE.write_text(
            "// GENERATED by scripts/build_barrios.py --places: the approved places of Montevideo and CABA (public map\n"
            "// coordinates, no names) and the barrio the FULL official polygons put them in. barrios.test.ts checks the\n"
            "// simplified polygons give the same answer. null = outside every barrio of that city.\n"
            "export const BARRIO_PLACES_FIXTURE: { city: \"montevideo\" | \"caba\"; lat: number; lng: number; "
            "barrio: string | null }[] = "
            + json.dumps(fixture, ensure_ascii=False, indent=0).replace("\n", "") + ";\n",
            encoding="utf-8", newline="\n",
        )
        print(f"{OUT_FIXTURE.relative_to(ROOT)}: {len(fixture)} places, 0 changed barrio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
