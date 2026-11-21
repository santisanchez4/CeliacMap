"""The A/B detector for near places (db/checks/chat_prompt_ab.py, suite tanda), pinned on real reply shapes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("chat_prompt_ab", ROOT / "db/checks/chat_prompt_ab.py")
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)
ROWS = next(cell[3] for cell in ab.TANDA_CELLS if cell[0] == "solo_cerca")


def test_a_blank_line_between_the_header_and_the_list_still_counts_the_header():
    reply = ("No encontré lugares en el mapa para Belgrano. Los que tengo cerca están en Palermo:\n\n"
             "• Cantina Lacroze — restaurante, Espacio 100% sin gluten\n• Parrilla Báez — restaurante, Tiene opciones sin gluten")
    assert ab.nearby_misattributed(reply, ROWS) == (2, 0)


def test_near_places_under_a_header_of_the_barrio_asked_for_are_misattributed():
    reply = "En Belgrano encontré:\n\n• Cantina Lacroze — restaurante\n• Parrilla Báez — restaurante"
    assert ab.nearby_misattributed(reply, ROWS) == (0, 2)


def test_every_saved_belgrano_reply_names_palermo():
    import json
    saved = json.loads((ROOT / "db/checks/2026-11-21-chat-tanda-solo-cerca.json").read_text(encoding="utf-8"))
    replies = saved["solo_cerca"]["NEW"]
    assert len(replies) == 8
    assert [ab.nearby_misattributed(r, ROWS) for r in replies] == [(2, 0)] * 8
