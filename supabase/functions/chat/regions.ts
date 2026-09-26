// Department / province search for the chatbot (docs/DECISIONS.md, "Búsqueda por departamento / provincia").
//
// `places.city` holds the town ("Melo"), never the department ("Cerro Largo"), so "lugares en Cerro Largo" found
// nothing. `places.region` (filled from Google's own address by the agents) holds it; this module decides WHEN a
// search should use it. Pure and import-free on purpose: index.ts depends on it, never the other way round.
//
// The two tables below are the canonical names the agents write (agents/clients/google_places.py,
// AR_REGION_NAMES / UY_REGION_NAMES); tests/test_region_lists_sync.py fails if the copies drift.

export type RegionCountry = "Argentina" | "Uruguay";

export interface RegionTarget {
  region: string;
  country: RegionCountry;
}

export const AR_REGIONS: Record<string, string> = {
  "buenos aires": "Buenos Aires", "catamarca": "Catamarca", "chaco": "Chaco", "chubut": "Chubut",
  "cordoba": "Córdoba", "corrientes": "Corrientes", "entre rios": "Entre Ríos", "formosa": "Formosa",
  "jujuy": "Jujuy", "la pampa": "La Pampa", "la rioja": "La Rioja", "mendoza": "Mendoza",
  "misiones": "Misiones", "neuquen": "Neuquén", "rio negro": "Río Negro", "salta": "Salta",
  "san juan": "San Juan", "san luis": "San Luis", "santa cruz": "Santa Cruz", "santa fe": "Santa Fe",
  "santiago del estero": "Santiago del Estero", "tierra del fuego": "Tierra del Fuego", "tucuman": "Tucumán",
};

export const UY_REGIONS: Record<string, string> = {
  "artigas": "Artigas", "canelones": "Canelones", "cerro largo": "Cerro Largo", "colonia": "Colonia",
  "durazno": "Durazno", "flores": "Flores", "florida": "Florida", "lavalleja": "Lavalleja",
  "maldonado": "Maldonado", "montevideo": "Montevideo", "paysandu": "Paysandú", "rio negro": "Río Negro",
  "rivera": "Rivera", "rocha": "Rocha", "salto": "Salto", "san jose": "San José", "soriano": "Soriano",
  "tacuarembo": "Tacuarembó", "treinta y tres": "Treinta y Tres",
};

// Names that are ALSO a barrio (Flores), a street (Av. Corrientes, Colonia 1779), a town in the other country
// (Salto, Rivera, Florida in Buenos Aires) or a region of both countries (Río Negro). Alone they are not a region:
// one needs router.pais to resolve it or an explicit "departamento de" / "provincia de". "Buenos Aires" is handled
// separately: bare it is CABA, the city, and the province only ever comes with its marker.
export const AMBIGUOUS_REGION_NAMES: ReadonlySet<string> = new Set([
  "flores", "florida", "colonia", "rivera", "corrientes", "misiones", "san jose", "salto", "rio negro",
  "santa cruz", "san juan", "san luis",
]);

export type RegionPlan =
  | { kind: "city" }
  // Search by region INSTEAD of by city. `prefer` = the normalized city the person named when the region name was
  // typed as a city ("Córdoba"), so that city's places rank first; null when the region was asked for outright.
  | { kind: "region"; target: RegionTarget; prefer: string | null; dropZona: boolean }
  // Search the city as today; if it gives nothing, tell the redactor how many places the region has.
  | { kind: "fallback"; target: RegionTarget; searched: string };

const CITY: RegionPlan = { kind: "city" };

export function normalizeText(value: string): string {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

const MARKER_WORDS = "(provincia|departamento|dpto|depto|province|department)";
const MARKER_LEAD_RE = new RegExp(`^${MARKER_WORDS}(?: de| del| of)? `);
const markerCountry = (word: string): RegionCountry =>
  word === "provincia" || word === "province" ? "Argentina" : "Uruguay";

/** "provincia de buenos aires" -> the name and the country the marker implies (a province is Argentine, a department Uruguayan). */
function splitMarker(normalized: string): { name: string; marker: RegionCountry | null } {
  const match = MARKER_LEAD_RE.exec(normalized);
  if (!match) return { name: normalized, marker: null };
  return { name: normalized.slice(match[0].length), marker: markerCountry(match[1]) };
}

const has = (table: Record<string, string>, name: string) => Object.prototype.hasOwnProperty.call(table, name);

/**
 * The region a normalized name stands for, given the country the router found and the one an explicit marker
 * implies. Null when the name is not a region, when a country contradicts it, or when it is ambiguous and nothing
 * resolves it (the caller then keeps the city filter, as before).
 */
function resolveRegion(name: string, pais: string | null, explicit: RegionCountry | null): RegionTarget | null {
  let candidates: RegionCountry[] = [
    ...(has(AR_REGIONS, name) ? (["Argentina"] as const) : []),
    ...(has(UY_REGIONS, name) ? (["Uruguay"] as const) : []),
  ];
  if (explicit) candidates = candidates.filter((c) => c === explicit);
  if (pais) candidates = candidates.filter((c) => c === pais);
  if (candidates.length !== 1) return null;
  if (!explicit && !pais && AMBIGUOUS_REGION_NAMES.has(name)) return null;
  if (!explicit && name === "buenos aires") return null;
  const country = candidates[0];
  return { region: (country === "Argentina" ? AR_REGIONS : UY_REGIONS)[name], country };
}

const ALL_NAMES = [...new Set([...Object.keys(AR_REGIONS), ...Object.keys(UY_REGIONS)])].sort((a, b) => b.length - a.length);
const MARKED_RES = ALL_NAMES.map((name) => ({ name, re: new RegExp(`\\b${MARKER_WORDS}(?: de| del| of)? ${name}\\b`) }));
const BARE_RES = ALL_NAMES.map((name) => ({ name, re: new RegExp(`\\b${name}\\b`) }));

/** The earliest "provincia de X" / "departamento de X" in a normalized message. */
function findMarkedRegion(message: string, pais: string | null): { name: string; target: RegionTarget } | null {
  let best: { index: number; name: string; target: RegionTarget } | null = null;
  for (const { name, re } of MARKED_RES) {
    const match = re.exec(message);
    if (!match || (best && match.index >= best.index)) continue;
    const target = resolveRegion(name, pais, markerCountry(match[1]));
    if (target) best = { index: match.index, name, target };
  }
  return best;
}

/** The earliest region named with no marker at all, skipping every ambiguous name (and a bare "Buenos Aires"). */
function findBareRegion(message: string, pais: string | null): RegionTarget | null {
  let best: { index: number; target: RegionTarget } | null = null;
  for (const { name, re } of BARE_RES) {
    if (AMBIGUOUS_REGION_NAMES.has(name)) continue;
    const match = re.exec(message);
    if (!match || (best && match.index >= best.index)) continue;
    const target = resolveRegion(name, pais, null);
    if (target) best = { index: match.index, target };
  }
  return best?.target ?? null;
}

export function planRegionSearch(
  input: { ciudad: string | null; zona: string | null; pais: string | null; message: string },
): RegionPlan {
  const { pais } = input;
  const ciudad = input.ciudad ? splitMarker(normalizeText(input.ciudad)) : null;
  const zona = input.zona ? splitMarker(normalizeText(input.zona)) : null;
  const message = normalizeText(input.message);
  const hasCiudad = ciudad !== null && ciudad.name !== "";
  const direct = (target: RegionTarget, prefer: string | null): RegionPlan => ({
    kind: "region",
    target,
    prefer,
    dropZona: zona !== null && zona.name === normalizeText(target.region),
  });

  // 1. An explicit marker (in the router's fields, else in the message) asks for the department / province
  //    outright, unless a different city was named: then the city comes first (below).
  let explicit: { name: string; target: RegionTarget } | null = null;
  for (const part of [ciudad, zona]) {
    if (!part?.marker) continue;
    const target = resolveRegion(part.name, pais, part.marker);
    if (target) {
      explicit = { name: part.name, target };
      break;
    }
  }
  explicit ??= findMarkedRegion(message, pais);
  if (explicit && (!hasCiudad || ciudad.name === explicit.name)) return direct(explicit.target, null);

  // 2. No city: a region in zona is the router's usual shape for "en la provincia de X".
  if (!hasCiudad) {
    const target = zona ? resolveRegion(zona.name, pais, zona.marker) : null;
    return target ? direct(target, null) : CITY;
  }

  // 3. The city IS a region name (Maldonado, Córdoba): search the region, its namesake city first.
  const own = resolveRegion(ciudad.name, pais, ciudad.marker);
  if (own) return direct(own, ciudad.marker ? null : ciudad.name);

  // 4. A real city: search it as today and, if it gives nothing, widen to the region named alongside.
  const widen = explicit?.target ?? (zona ? resolveRegion(zona.name, pais, zona.marker) : null) ?? findBareRegion(message, pais);
  return widen ? { kind: "fallback", target: widen, searched: input.ciudad as string } : CITY;
}

/** The requested city's places first (accent and case blind), then the rest of the region, cut at `limit`. Stable. */
export function orderRegionRows<T extends { city?: unknown }>(rows: T[], prefer: string | null, limit: number): T[] {
  if (!prefer) return rows.slice(0, limit);
  const first: T[] = [];
  const rest: T[] = [];
  for (const row of rows) (typeof row.city === "string" && normalizeText(row.city) === prefer ? first : rest).push(row);
  return [...first, ...rest].slice(0, limit);
}

/** What the redactor is told when a search widened: the region and the towns where its places are ("Cerro Largo (Melo)"). */
export function widenedLabel(region: string, rows: { city: string | null }[]): { city: string; count: number } {
  const counts = new Map<string, number>();
  for (const row of rows) if (row.city) counts.set(row.city, (counts.get(row.city) ?? 0) + 1);
  const cities = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([city]) => city);
  return { city: cities.length ? `${region} (${cities.join(", ")})` : region, count: rows.length };
}
