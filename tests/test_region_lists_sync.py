"""The chatbot's region lists (supabase/functions/chat/regions.ts) must equal the ones the agents write.

`places.region` is written by GooglePlacesClient.region_from_address with the canonical names of
AR_REGION_NAMES / UY_REGION_NAMES; the chat filters `region=eq.<name>` with its own copy of the same
lists. If the two drift, a search silently finds nothing, so this test is the gate: change one, change the
other. (Same idea as test_chat_prompts_sync.py.)
"""
import re
from pathlib import Path

from agents.clients.google_places import AR_REGION_NAMES, UY_REGION_NAMES

REGIONS_TS = Path(__file__).resolve().parent.parent / "supabase" / "functions" / "chat" / "regions.ts"


def _table(name: str) -> dict[str, str]:
    text = REGIONS_TS.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(rf"export const {name}: Record<string, string> = \{{(.*?)\n\}};", text, re.DOTALL)
    assert m, f"{name} not found in regions.ts"
    return dict(re.findall(r'"([a-z ]+)":\s*"([^"]+)"', m.group(1)))


def test_argentine_provinces_match_the_agents():
    assert _table("AR_REGIONS") == AR_REGION_NAMES


def test_uruguayan_departments_match_the_agents():
    assert _table("UY_REGIONS") == UY_REGION_NAMES
