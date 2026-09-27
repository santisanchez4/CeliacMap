"""Guards db/fixes/2026-09-27-duplicate-place-ids.sql: the 21 duplicated Google places (two rows for one place_id) are resolved.

Found 2026-09-27 (docs/DECISIONS.md, "One Google place, one row"): 24 place_ids had two rows; 13 with both rows approved (the same business twice on the
map) and 11 with another status combination (8 need a discard, 3 already have a discarded side). The script keeps ONE row per place_id (the google_places one,
which is anchored to the Google listing, except where the social row is the approved one), moves what hangs from the other one (votes, reports and published
opinions, evidence, outreach messages, promoted suggestions) onto it, fills only the NULL panel fields of the kept row from the other, and discards the other with
"CORRECCIÓN MANUAL: duplicado de <id>". That header is a DATA correction (agents/manual_overrides.py): it protects nothing.

What is pinned: the pairs, that no row of `places` is ever deleted, the exact assignments of each UPDATE, the guards, the header wording, the counts asserted, and
that nothing is left attached to a discarded row.
"""
import re
from pathlib import Path

from pglast import parse_sql

from agents.manual_overrides import manual_override_marker

FIX = Path(__file__).resolve().parent.parent / "db" / "fixes" / "2026-09-27-duplicate-place-ids.sql"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
HEADER_PREFIX = "CORRECCIÓN MANUAL: duplicado de "


def text() -> str:
    return FIX.read_text(encoding="utf-8").replace("\r\n", "\n")


def code() -> str:
    return re.sub(r"--[^\n]*", "", text())


def pairs() -> list[tuple[str, str, str, str, str]]:
    return re.findall(rf"\('({UUID})', '({UUID})', '(ChIJ[^']+)', '(approved|needs_review)', '(approved|needs_review)'\)", code())


def update_blocks(table: str) -> list[str]:
    return re.findall(rf"update public\.{table}\b.*?(?:get diagnostics n = row_count;|;)", code(), re.S | re.I)


def set_columns(block: str) -> list[str]:
    body = re.search(r"\bset\b(.*?)\n\s*from\s+_pairs\b", block, re.S | re.I).group(1)
    return re.findall(r"(?m)^\s*(\w+)\s*=", "\n" + body.strip() + "\n")


def test_the_script_parses():
    assert parse_sql(text())


def test_it_is_one_transaction_that_asserts_before_it_commits_and_never_deletes_a_place():
    body = code().lower()
    assert body.count("begin;") == 1 and body.strip().endswith("commit;")
    assert "raise exception" in body
    assert "delete from public.places" not in body and "truncate" not in body
    assert body.count("delete from public.place_votes") == 1  # only the vote move, after its insert


def test_the_21_pairs_are_distinct_places_and_no_row_is_both_kept_and_discarded():
    p = pairs()
    assert len(p) == 21
    keep, drop, ext = [x[0] for x in p], [x[1] for x in p], [x[2] for x in p]
    assert len(set(keep)) == 21 and len(set(drop)) == 21 and len(set(ext)) == 21
    assert not (set(keep) & set(drop))
    assert sum(1 for x in p if x[4] == "approved") == 13 and sum(1 for x in p if x[4] == "needs_review") == 8


def test_the_kept_row_is_the_approved_one_or_ties_with_it_never_a_worse_status_than_the_discarded():
    for keep, drop, _, keep_status, drop_status in pairs():
        assert not (keep_status == "needs_review" and drop_status == "approved"), (keep, drop)


def test_every_step_is_guarded_by_the_pairs_and_the_expected_statuses():
    body = code()
    assert "create temp table _pairs" in body
    assert re.search(r"where p\.id = pr\.drop_id and p\.status = pr\.drop_status", body)
    assert re.search(r"if n <> 21 then raise exception", body)


def test_the_discard_sets_only_status_flags_and_notes_with_the_data_correction_header():
    block = [b for b in update_blocks("places") if "'discarded'" in b][0]
    assert set_columns(block) == ["status", "flags", "validation_notes"]
    assert f"'{HEADER_PREFIX}' || pr.keep_id" in block and "concat_ws(E'" in block and "nullif(p.validation_notes, '')" in block
    assert "100% pendiente de confirmación del administrador" in block  # a discarded place leaves the 100% queue


def test_the_header_is_a_data_correction_and_protects_nothing_but_an_approval_under_it_still_does():
    header = HEADER_PREFIX + "6797f10b-dbe4-4c67-a5d2-1b8f0e3a7c11"
    assert manual_override_marker(header) is None
    assert manual_override_marker(header + "\n\nThe name explicitly includes 'Gluten Free'.") is None
    approval = "APROBACIÓN MANUAL (2026-09-27, review_queue): Revisado por el admin. El Validator había dejado: approved @ 0.95."
    assert manual_override_marker(header + "\n\n" + approval) is not None


def test_the_kept_row_only_fills_its_null_panel_fields():
    block = [b for b in update_blocks("places") if "coalesce(" in b][0]
    assert set_columns(block) == ["phone", "website", "social_url"]
    for column in ("phone", "website", "social_url"):
        assert f"coalesce(k.{column}, d.{column})" in block


def test_what_hangs_from_a_discarded_row_moves_to_the_kept_one():
    body = code()
    assert re.search(r"insert into public\.place_votes.*?on conflict \(place_id, voter_token\) do nothing", body, re.S | re.I)
    for table, column in (("place_reports", "place_id"), ("place_evidence", "place_id"), ("outreach_messages", "place_id"),
                          ("suggestions", "promoted_place_id")):
        block = update_blocks(table)
        assert block and f"set {column} = pr.keep_id" in block[0].lower().replace("\n", " ").replace("  ", " "), table


def test_nothing_is_left_attached_to_a_discarded_row_and_the_vote_counts_agree():
    body = code()
    for table, column in (("place_votes", "place_id"), ("place_reports", "place_id"), ("place_evidence", "place_id"),
                          ("reviews", "place_id"), ("outreach_messages", "place_id"), ("suggestions", "promoted_place_id")):
        assert re.search(rf"from public\.{table} \w+ join _pairs pr on \w+\.{column} = pr\.drop_id", body), table
    assert "vote_count <> (select count(*) from public.place_votes" in body


def test_nothing_else_changes_the_assertions_compare_a_hash_of_every_other_column():
    body = code()
    assert "md5(to_jsonb(p)::text)" in body
    assert "md5((to_jsonb(p) - 'status' - 'flags' - 'validation_notes' - 'updated_at')::text)" in body  # discarded rows
    assert "md5((to_jsonb(p) - 'phone' - 'website' - 'social_url' - 'vote_count' - 'updated_at')::text)" in body  # kept rows
    assert "(select count(*) from public.places) <> (select count(*) from _snap)" in body
