"""Dry-run re-evaluation of places that are already on the map: what would the CURRENT Validator say, with fresh evidence?

READ-ONLY by construction: this script has no ``--apply`` and never calls a write method. It prints, and saves a local JSON report
under ``db/checks/evidence-proposals/`` (git-ignored). A status on the map is only ever changed by the admin, afterwards.

For each place id:
1. Google Place Details (live): the listing's website when the row has none, the business status and the gluten-free review
   snippets the pipeline would enrich. Reviews are used in memory only (Google ToS: never stored from here).
2. The evidence finder (``agents/evidence_finder.py``, with the social-attribution rule): quotes about that business. Only
   attributable citations become evidence; "no atribuible" quotes are listed and never sent to the Validator.
3. ``ValidatorAgent.evaluate()`` with the current RUBRIC and gates, ``--runs`` times (the model is not deterministic), once per
   variant: "sin extra" and, when ``--extra-evidence`` has rows for the place, "con extra" (e.g. a municipal licence).

    python db/checks/reevaluate_dry_run.py --ids ID1 ID2 --extra-evidence db/checks/2026-10-13-reevaluate-extra-evidence.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.clients.google_places import GooglePlacesClient  # noqa: E402
from agents.clients.website_scraper import fetch_social_links, is_social_url  # noqa: E402
from agents.evidence_finder import EvidenceFinder  # noqa: E402
from agents.manual_overrides import manual_override_marker  # noqa: E402
from agents.validator_agent import MAX_EVIDENCE, ValidatorAgent  # noqa: E402

OUT_DIR = "db/checks/evidence-proposals"


def citation_rows(result: dict, limit: int) -> list[dict]:
    rows, seen = [], set()
    for cite in result.get("citations") or []:
        if cite["text"] in seen:
            continue
        seen.add(cite["text"])
        rows.append({"source": "social" if is_social_url(cite["url"]) else "web", "text": cite["text"], "url": cite["url"]})
        if len(rows) == limit:
            break
    return rows


def evaluate_place(db, places, finder, validator, place: dict, extra: list[dict], runs: int) -> dict:
    listing, snippets = {}, []
    if place.get("external_id") and place.get("geocode_method") != "address_only":
        result = places.place_details_with_reviews(place["external_id"]).get("result") or {}
        rich = GooglePlacesClient.extract_rich_fields(result)
        listing = {"business_status": result.get("business_status"), "website": rich.get("website"),
                   "social_url": rich.get("social_url")}
        snippets = GooglePlacesClient.extract_gf_snippets(result.get("reviews"))
    searched = {**place, "website": place.get("website") or listing.get("website"),
                "social_url": place.get("social_url") or listing.get("social_url")}
    found = finder.find(searched)

    stored = list(db.fetch_place_evidence(place["id"]) or [])
    claims = list(db.fetch_community_claims(place["id"]) or [])
    reviews = (list(db.fetch_reviews_for_place(place["id"]) or []) + snippets)[:5]
    variants = {"sin extra": (citation_rows(found, MAX_EVIDENCE) + stored)[:MAX_EVIDENCE]}
    if extra:
        variants["con extra"] = (extra + citation_rows(found, MAX_EVIDENCE - len(extra)) + stored)[:MAX_EVIDENCE]
    verdicts = {name: [validator.evaluate(place, reviews, claims, evidence) for _ in range(runs)]
                for name, evidence in variants.items()}
    return {
        "place_id": place["id"], "name": place.get("name"),
        "current": {"status": place.get("status"), "safety_level": place.get("safety_level"),
                    "confidence": place.get("validation_confidence"), "notes": place.get("validation_notes")},
        "listing": listing, "reviews": [r.get("text") for r in reviews], "official_accounts": found.get("official_accounts"),
        "finder_proposal": found.get("proposal"), "citations": found.get("citations"), "unattributed": found.get("unattributed"),
        "evidence": variants, "verdicts": verdicts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", nargs="+", required=True, metavar="PLACE_ID")
    parser.add_argument("--extra-evidence", metavar="JSON", help='{"<place_id>": [{"source", "text", "url"}]}')
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    from agents.clients.llm import LLMClient
    from agents.clients.supabase_client import SupabaseClient
    from agents.clients.tavily_client import TavilySearchClient
    from config.settings import get_settings

    settings = get_settings()
    settings.require("supabase_url", "supabase_service_role_key", "google_maps_api_key", "anthropic_api_key", "tavily_api_key")
    db = SupabaseClient(settings.supabase_url, settings.supabase_service_role_key)
    places = GooglePlacesClient(settings.google_maps_api_key)
    finder = EvidenceFinder(TavilySearchClient(settings.tavily_api_key), llm=LLMClient(settings.anthropic_api_key, settings.haiku_model),
                            fetch_links=fetch_social_links)
    validator = ValidatorAgent(db, LLMClient(settings.anthropic_api_key, settings.validator_model), model=settings.validator_model)
    extra = json.loads(Path(args.extra_evidence).read_text(encoding="utf-8")) if args.extra_evidence else {}

    results = []
    for place_id in args.ids:
        place = db.fetch_place_by_id(place_id)
        if not place:
            print(f"No existe el lugar {place_id}.")
            continue
        marker = manual_override_marker(place.get("validation_notes"))
        if marker:
            print(f"{place.get('name')}: tiene una decisión manual ({marker}); no se re-evalúa.")
            continue
        r = evaluate_place(db, places, finder, validator, place, extra.get(place_id) or [], args.runs)
        results.append(r)
        cur = r["current"]
        print(f"\n=== {r['name']} · hoy: {cur['status']} · {cur['safety_level']} @ {cur['confidence']}")
        print(f"    ficha de Google: {r['listing']} · cuentas oficiales: {r['official_accounts']} · reseñas con señal: {len(r['reviews'])}")
        print(f"    buscador: {r['finder_proposal']} · {len(r['citations'] or [])} citas · {len(r['unattributed'] or [])} no atribuibles")
        for name, evidence in r["evidence"].items():
            print(f"  [{name}] evidencia ({len(evidence)}):")
            for e in evidence:
                print(f"      - [{e['source']}] {e['text'][:170]} <{e.get('url') or 'sin URL'}>")
            for v in r["verdicts"][name]:
                print(f"      -> {v['status']} @ {v['confidence']} · {v['safety_level']} · flags {len(v['flags'])}")
            print(f"         {r['verdicts'][name][0]['reason']}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(OUT_DIR) / f"reevaluate-dryrun-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"writes_to_database": False, "searches_used": finder.searches_used, "results": results},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nDRY RUN: sin escrituras en la base. Búsquedas de Tavily: {finder.searches_used}. Detalle: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
