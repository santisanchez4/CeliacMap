"""Guards the three one-off SQL scripts of 2026-09-27 written from the admin's own checks (db/fixes/):

* Delirio Sin Gluten: its address gets the house number the business publishes (Luis Franzini 970);
* Rikuras Sin Gluten (Malvín): the website of the business card replaces the old one;
* Rikuras Sin Gluten El Pinar: the new branch, a manual place anchored on its own Google listing.

What is pinned: every script parses; each changes exactly what it says and nothing else (the UPDATEs by their assignments, the INSERT by its columns
and values); each is guarded and asserts its row count; and the Delirio header is a DATA correction (agents/manual_overrides.py) that protects nothing.
"""
import re
from pathlib import Path

from pglast import parse_sql

from agents.clients.google_places import GooglePlacesClient
from agents.manual_overrides import manual_override_marker

FIXES = Path(__file__).resolve().parent.parent / "db" / "fixes"
DELIRIO = FIXES / "2026-09-27-delirio-address.sql"
MALVIN = FIXES / "2026-09-27-rikuras-malvin-website.sql"
PINAR = FIXES / "2026-09-27-rikuras-el-pinar.sql"

DELIRIO_ID = "7af0d1a1-5603-454a-a578-7b7bc05c8423"
MALVIN_ID = "339efc28-af19-4ce4-96ea-a9c1aa5176d4"
PINAR_PLACE_ID = "ChIJH05jRj-Ln5URB3xgh46-Mck"  # the Google listing of the El Pinar branch (Find Place, 2026-09-27)
MALVIN_PLACE_ID = "ChIJ64hoV1KHn5URvCEqq2PDcI4"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def code(path: Path) -> str:
    return re.sub(r"--[^\n]*", "", text(path))


def const(node):
    """The Python value of an A_Const of the AST."""
    if node.isnull:
        return None
    val = node.val
    for attr in ("sval", "fval", "ival", "boolval"):
        if hasattr(val, attr) and getattr(val, attr) is not None:
            v = getattr(val, attr)
            return float(v) if attr == "fval" else v
    return None


def set_columns(path: Path) -> list[str]:
    block = re.search(r"update public\.places\s+set(.*?)\bwhere\b", code(path), re.S | re.I).group(1)
    return re.findall(r"(?m)^\s*(\w+)\s*=", "\n" + block.strip() + "\n")


# --- all three ---------------------------------------------------------------------------------------------------------------

def test_the_three_scripts_parse():
    for path in (DELIRIO, MALVIN, PINAR):
        assert parse_sql(text(path)), path.name


def test_every_script_is_one_transaction_that_asserts_before_it_commits():
    for path in (DELIRIO, MALVIN, PINAR):
        body = code(path).lower()
        assert body.count("begin;") == 1 and body.strip().endswith("commit;"), path.name
        assert "raise exception" in body, path.name


# --- Delirio: the address ----------------------------------------------------------------------------------------------------------

def test_the_delirio_header_is_a_data_correction_and_protects_nothing():
    header = re.search(r"'(CORRECCIÓN MANUAL 2026-09-27: dirección corregida[^']*)'", text(DELIRIO)).group(1)
    assert manual_override_marker(header) is None
    assert manual_override_marker(header + "\n\nThe name explicitly includes 'Sin Gluten'.") is None
    approval = "APROBACIÓN MANUAL (2026-09-27, review_queue): Revisado por el admin. El Validator había dejado: approved @ 0.95."
    assert manual_override_marker(header + "\n\n" + approval) is not None  # an admin decision under it still protects


def test_delirio_changes_only_address_and_validation_notes_and_the_coordinates_stay():
    assert set_columns(DELIRIO) == ["address", "validation_notes"]
    assert not re.search(r"\b(lat|lng)\s*=", code(DELIRIO))


def test_delirio_new_address_has_the_house_number_and_keeps_its_region():
    new = re.search(r"\bset\s+address\s*=\s*'([^']+)'", code(DELIRIO)).group(1)
    assert new == "Luis Franzini 970, 11300 Montevideo, Departamento de Montevideo, Uruguay"
    assert GooglePlacesClient.region_from_address(new, "Uruguay") == "Montevideo"  # places.region stays in step with the address


def test_delirio_is_guarded_by_its_id_and_its_old_address_and_asserts_one_row():
    body = code(DELIRIO)
    assert DELIRIO_ID in body
    assert "address = 'Luis Franzini, 11300 Montevideo, Departamento de Montevideo, Uruguay'" in body
    assert body.count("if n <> 1 then raise exception") >= 2  # the guard and the update
    assert "md5((to_jsonb(p) - 'address' - 'validation_notes' - 'updated_at')::text)" in body  # nothing else changed


# --- Rikuras Malvín: the website --------------------------------------------------------------------------------------------------

def test_malvin_changes_only_the_website_of_that_row_from_the_old_one():
    body = code(MALVIN)
    assert set_columns(MALVIN) == ["website"]
    assert re.search(r"website\s*=\s*'https://rikurassingluten\.pidedirecto\.uy/'", body)
    assert MALVIN_ID in body and "website = 'https://rikurassingluten.ambit.la/'" in body
    assert "if n <> 1 then raise exception" in body
    assert "md5((to_jsonb(p) - 'website' - 'updated_at')::text)" in body


# --- Rikuras El Pinar: the new branch ---------------------------------------------------------------------------------------------

def insert_of_pinar() -> dict:
    stmt = parse_sql(text(PINAR))
    inserts = [s.stmt for s in stmt if type(s.stmt).__name__ == "InsertStmt"]
    assert len(inserts) == 1, "one INSERT, and it is not a DO block string"
    ins = inserts[0]
    cols = [c.name for c in ins.cols]
    values = [const(t.val) for t in ins.selectStmt.targetList]
    return dict(zip(cols, values))


def test_the_new_branch_is_a_manual_approved_row_with_no_validator_confidence_and_not_verified():
    row = insert_of_pinar()
    assert row["name"] == "Rikuras Sin Gluten El Pinar"
    assert row["source"] == "manual" and row["status"] == "approved" and row["safety_level"] == "gluten_free_100"
    assert row["validation_confidence"] is None and row["verified"] is False
    assert row["country"] == "Uruguay" and row["region"] == "Canelones" and row["category"] == "restaurant"


def test_the_new_branch_uses_its_own_google_listing_never_the_malvin_one():
    row = insert_of_pinar()
    assert row["external_id"] == PINAR_PLACE_ID and row["external_id"] != MALVIN_PLACE_ID
    assert row["geocode_method"] == "find_place"
    assert -35.1 < row["lat"] < -34.6 and -56.2 < row["lng"] < -55.6  # Canelones, on the coast east of Montevideo
    assert abs(row["lat"] - (-34.8043848)) < 1e-6 and abs(row["lng"] - (-55.9063936)) < 1e-6


def test_the_new_branch_carries_the_card_data_and_a_manual_approval_note_with_the_same_evidence():
    row = insert_of_pinar()
    assert row["phone"] == "095 714 329" and row["website"] == "https://rikurassingluten.pidedirecto.uy/"
    note = row["validation_notes"]
    assert note.startswith("APROBACIÓN MANUAL (2026-09-27") and "rikuras_singluten" in note
    assert manual_override_marker(note) is not None  # an admin decision: it protects, like every APROBACIÓN MANUAL
    assert "celíaco" not in note.lower().replace("celíacos", "")  # no health data of a person, only "apta para celíacos"


def test_the_new_branch_address_names_the_corner_and_parses_to_canelones():
    row = insert_of_pinar()
    assert "Perez Butler" in row["address"] and "Santa Paula" in row["address"]
    assert GooglePlacesClient.region_from_address(row["address"], "Uruguay") == "Canelones"


def test_the_insert_is_guarded_against_running_twice_and_asserts_exactly_one_new_row():
    body = code(PINAR).lower()
    assert re.search(r"where not exists\s*\(\s*select 1 from public\.places\s+where", body)
    assert PINAR_PLACE_ID.lower() in body.split("where not exists", 1)[1]
    assert "if n <> 1 then raise exception" in body and "count(*) from _snap" in body
