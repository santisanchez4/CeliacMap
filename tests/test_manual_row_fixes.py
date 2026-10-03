"""Guards the three one-off SQL scripts of 2026-09-27 written from the admin's own checks (db/fixes/):

* Delirio Sin Gluten: its address gets the house number the business publishes (Luis Franzini 970);
* Rikuras Sin Gluten (Malvín): the website of the business card replaces the old one;
* the new branches (Rikuras El Pinar, Piu Helados Prado) and the update of the Piu Helados Cordón row that already existed.

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
NEW_BRANCHES = FIXES / "2026-09-27-new-branches.sql"

DELIRIO_ID = "7af0d1a1-5603-454a-a578-7b7bc05c8423"
MALVIN_ID = "339efc28-af19-4ce4-96ea-a9c1aa5176d4"
PINAR_PLACE_ID = "ChIJH05jRj-Ln5URB3xgh46-Mck"  # the Google listing of the El Pinar branch (Find Place, 2026-09-27)
PIU_PRADO_PLACE_ID = "ChIJu6y8K8EroJUR5Y38idweSEk"  # Piu Helados, Av. Millán 3665 (a new place)
PIU_CORDON_PLACE_ID = "ChIJU0NqfQCBn5URvFcSbHMvFQs"  # Piu Helados, Constituyente 2039: already a row, discarded by the Validator in June
PIU_CORDON_ID = "d1420754-dca8-47e2-8d60-97ac779de1c2"
MALVIN_PLACE_ID = "ChIJ64hoV1KHn5URvCEqq2PDcI4"


def test_rikuras_restoration_is_guarded_and_the_file_stays_a_rehearsal():
    pending = FIXES / "2026-10-02-rikuras-malvin-website.sql"
    sql = code(pending)
    parse_sql(sql)
    assert sql.strip().lower().endswith("rollback;")
    assert not re.search(r"\bcommit\s*;", sql, re.I)
    assert set_columns(pending) == ["website"]
    assert MALVIN_ID in sql and MALVIN_PLACE_ID in sql
    assert "https://rikurassingluten.pidedirecto.uy/" in sql
    assert "https://rikurassingluten.ambit.la/" in sql
    assert "n <> 1" in sql and "raise exception" in sql


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
    for path in (DELIRIO, MALVIN, NEW_BRANCHES):
        assert parse_sql(text(path)), path.name


def test_every_script_is_one_transaction_that_asserts_before_it_commits():
    for path in (DELIRIO, MALVIN, NEW_BRANCHES):
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


# --- the new branches: one transaction, exactly two new places -------------------------------------------------------------------------

def inserts() -> dict:
    """The INSERTs of the script by place name: {name: {column: value}} (read from the AST, not with regexes)."""
    rows = {}
    for raw in parse_sql(text(NEW_BRANCHES)):
        if type(raw.stmt).__name__ != "InsertStmt":
            continue
        cols = [c.name for c in raw.stmt.cols]
        values = [const(t.val) for t in raw.stmt.selectStmt.targetList]
        row = dict(zip(cols, values))
        rows[row["name"]] = row
    return rows


def test_the_script_inserts_exactly_two_places_and_asserts_it():
    body = code(NEW_BRANCHES).lower()
    assert sorted(inserts()) == ["Piu Helados Prado", "Rikuras Sin Gluten El Pinar"]
    assert "(select count(*) from _snap) + 2" in body  # exactly two more places, no more and no fewer
    assert "if n <> 2 then raise exception" in body


def test_every_new_place_is_a_manual_approved_row_with_no_validator_confidence_and_not_verified():
    for name, row in inserts().items():
        assert row["source"] == "manual" and row["status"] == "approved" and row["safety_level"] == "gluten_free_100", name
        assert row["validation_confidence"] is None and row["verified"] is False, name
        assert row["country"] == "Uruguay", name
        assert row["geocode_method"] == "find_place", name  # both have their own Google listing
        assert row["validation_notes"].startswith("APROBACIÓN MANUAL (2026-09-27, admin): Revisado por el admin: su Instagram ("), name
        assert manual_override_marker(row["validation_notes"]) is not None, name  # an admin decision protects, like every APROBACIÓN MANUAL


def test_each_new_place_uses_its_own_google_listing_never_another_rows():
    rows = inserts()
    ids = [rows[n]["external_id"] for n in sorted(rows)]
    assert rows["Rikuras Sin Gluten El Pinar"]["external_id"] == PINAR_PLACE_ID
    assert rows["Piu Helados Prado"]["external_id"] == PIU_PRADO_PLACE_ID
    assert len(set(ids + [MALVIN_PLACE_ID, PIU_CORDON_PLACE_ID])) == 4  # four different Google places


def test_the_coordinates_are_the_ones_of_the_google_listings():
    rows = inserts()
    pinar, prado = rows["Rikuras Sin Gluten El Pinar"], rows["Piu Helados Prado"]
    assert abs(pinar["lat"] - (-34.8043848)) < 1e-6 and abs(pinar["lng"] - (-55.9063936)) < 1e-6
    assert abs(prado["lat"] - (-34.8603244)) < 1e-6 and abs(prado["lng"] - (-56.1953583)) < 1e-6
    for row in (pinar, prado):
        assert -35.1 < row["lat"] < -34.6 and -56.4 < row["lng"] < -55.6  # Canelones / Montevideo


def test_rikuras_el_pinar_carries_the_card_data_in_local_phone_format():
    row = inserts()["Rikuras Sin Gluten El Pinar"]
    assert row["phone"] == "095 714 329" and row["website"] == "https://rikurassingluten.pidedirecto.uy/"
    assert row["city"] == "Ciudad de la Costa" and row["region"] == "Canelones" and row["category"] == "restaurant"
    assert "rikuras_singluten" in row["validation_notes"]
    assert "Perez Butler" in row["address"] and "Santa Paula" in row["address"]
    assert GooglePlacesClient.region_from_address(row["address"], "Uruguay") == "Canelones"


def test_piu_helados_prado_carries_the_card_data():
    row = inserts()["Piu Helados Prado"]
    assert row["phone"] == "098 858 031" and row["social_url"] == "https://www.instagram.com/piuheladosmontevideo/"
    assert row["city"] == "Montevideo" and row["region"] == "Montevideo" and row["category"] == "cafe"
    assert row["address"].startswith("Av. Millán 3665, 11700 Montevideo")
    assert GooglePlacesClient.region_from_address(row["address"], "Uruguay") == "Montevideo"
    assert row["validation_notes"].endswith("se presenta como heladería artesanal Gluten Free.")


def test_every_phone_is_in_local_format():
    phones = [r["phone"] for r in inserts().values()] + re.findall(r"phone\s*=\s*'([^']+)'", code(NEW_BRANCHES))
    assert len(set(phones)) == 3  # the two INSERTs and the UPDATE (its phone is asserted again at the end)
    assert all(re.fullmatch(r"0\d{2} \d{3} \d{3}", p) for p in phones), phones


def test_each_insert_is_guarded_against_running_twice():
    body = code(NEW_BRANCHES).lower()
    assert body.count("where not exists") == 2
    for place_id in (PINAR_PLACE_ID, PIU_PRADO_PLACE_ID):
        assert place_id.lower() in body.split("where not exists", 1)[1]


# --- Piu Helados Cordón: the row that already exists (a discarded Validator verdict), updated, not duplicated ----------------------

def test_the_existing_cordon_row_is_updated_by_id_with_only_its_data_and_is_not_approved_here():
    body = code(NEW_BRANCHES)
    block = re.search(r"update public\.places\s+set(.*?)\bwhere\b(.*?);", body, re.S | re.I)
    columns = re.findall(r"(?m)^\s*(\w+)\s*=", "\n" + block.group(1).strip() + "\n")
    assert columns == ["name", "category", "social_url", "phone"]  # status, level and notes are set by `review_queue --approve` afterwards
    where = block.group(2)
    assert PIU_CORDON_ID in where and "status = 'discarded'" in where and PIU_CORDON_PLACE_ID in where and "name = 'Heladería Piú'" in where
    assert re.search(r"name\s*=\s*'Piu Helados Cordón'", body) and re.search(r"category\s*=\s*'cafe'", body)
    assert "social_url = 'https://www.instagram.com/piuheladosmontevideo/'" in body


def test_the_script_says_how_the_cordon_row_is_approved_after_the_commit():
    header = text(NEW_BRANCHES).split("begin;", 1)[0]
    assert f"review_queue --approve {PIU_CORDON_ID} --level 100" in header
    assert "discarded @ 0.75" in header  # the Validator's earlier verdict stays visible in the note that approve() writes


def test_no_existing_row_other_than_cordon_changes_and_cordon_only_in_its_four_columns():
    body = code(NEW_BRANCHES)
    assert "md5(to_jsonb(p)::text)" in body
    assert "md5((to_jsonb(p) - 'name' - 'category' - 'social_url' - 'phone' - 'updated_at')::text)" in body
