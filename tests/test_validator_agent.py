"""Unit tests for the Validator agent and the JSON parsing it relies on."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from agents.clients.llm import _parse_json
from agents.validator_agent import DEFAULT_SAFETY_LEVEL, ValidatorAgent


def make_agent():
    return ValidatorAgent(MagicMock(), MagicMock())


# --- JSON response parsing from Claude ------------------------------------


def test_parse_plain_json():
    assert _parse_json('{"verdict": "approved", "confidence_score": 0.8}') == {
        "verdict": "approved",
        "confidence_score": 0.8,
    }


def test_parse_json_inside_code_fence():
    text = '```json\n{"verdict": "rejected", "category": "shop"}\n```'
    assert _parse_json(text) == {"verdict": "rejected", "category": "shop"}


def test_parse_json_with_surrounding_prose():
    text = 'Mi veredicto: {"verdict": "needs_review", "confidence_score": 0.5}. Gracias!'
    assert _parse_json(text)["confidence_score"] == 0.5


def test_parse_json_raises_on_garbage():
    with pytest.raises(json.JSONDecodeError):
        _parse_json("no json object here at all")


# --- Confidence clamping --------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (0.5, 0.5),
        (1.5, 1.0),
        (-0.3, 0.0),
        (1, 1.0),
        (0, 0.0),
        ("0.7", 0.7),
    ],
)
def test_confidence_clamped_into_unit_range(raw, expected):
    assert ValidatorAgent._clamp_confidence(raw) == expected


@pytest.mark.parametrize("raw", [None, "abc", "", [1, 2]])
def test_confidence_invalid_becomes_none(raw):
    assert ValidatorAgent._clamp_confidence(raw) is None


# --- Conservative safety floor logic --------------------------------------


def test_invalid_safety_falls_back_to_place_value():
    agent = make_agent()
    place = {"category": "cafe", "safety_level": "celiac_friendly"}
    out = agent._normalize({"safety_level": "ultra_safe"}, place)
    assert out["safety_level"] == "celiac_friendly"


def test_invalid_safety_with_no_place_value_uses_default_floor():
    agent = make_agent()
    out = agent._normalize({"safety_level": "ultra_safe"}, {"category": "cafe"})
    assert out["safety_level"] == DEFAULT_SAFETY_LEVEL == "options_available"


def test_valid_safety_passes_through():
    agent = make_agent()
    out = agent._normalize({"safety_level": "gluten_free_100"}, {}, evidence=EXCLUSIVE_EVIDENCE)
    assert out["safety_level"] == "gluten_free_100"


# --- Confidence gates → DB status (defense in depth) ----------------------


@pytest.mark.parametrize(
    "verdict, conf, expected",
    [
        ("approved", 0.85, "approved"),       # at the approve threshold
        ("approved", 0.84, "needs_review"),   # just below → held for a human
        ("approved", 0.50, "needs_review"),   # mid band
        ("approved", 0.49, "discarded"),      # below reject threshold
        ("approved", None, "discarded"),      # missing confidence → 0.0
        ("needs_review", 0.95, "needs_review"),  # model caution respected
        ("rejected", 0.99, "discarded"),      # explicit reject, any confidence
    ],
)
def test_decide_status_gates(verdict, conf, expected):
    assert ValidatorAgent._decide_status(verdict, conf) == expected


# --- Verdict normalization ------------------------------------------------


def test_approved_with_high_confidence_maps_to_approved():
    agent = make_agent()
    out = agent._normalize({"verdict": "approved", "confidence_score": 0.9}, {})
    assert out["verdict"] == "approved"
    assert out["status"] == "approved"


def test_approved_but_low_confidence_falls_back_to_needs_review():
    # Golden rule: weak confidence can never auto-approve.
    agent = make_agent()
    out = agent._normalize({"verdict": "approved", "confidence_score": 0.6}, {})
    assert out["status"] == "needs_review"


def test_rejected_maps_to_discarded():
    agent = make_agent()
    out = agent._normalize({"verdict": "rejected", "confidence_score": 0.9}, {})
    assert out["status"] == "discarded"


@pytest.mark.parametrize("verdict", ["maybe", "", "ACCEPT", "yes"])
def test_unknown_verdict_label_defaults_to_needs_review(verdict):
    # Anything outside the allowed set is treated as the cautious middle tier.
    agent = make_agent()
    out = agent._normalize({"verdict": verdict, "confidence_score": 0.9}, {})
    assert out["verdict"] == "needs_review"
    assert out["status"] == "needs_review"


def test_invalid_category_falls_back_to_place_category():
    agent = make_agent()
    out = agent._normalize({"category": "bar"}, {"category": "shop"})
    assert out["category"] == "shop"


# --- Flags + recommendation extraction ------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (["sin TACC no mencionado", "sin certificación"], ["sin TACC no mencionado", "sin certificación"]),
        ("solo un flag", ["solo un flag"]),
        (None, []),
        ([], []),
        ([" x ", "", "y"], ["x", "y"]),
        (123, []),
    ],
)
def test_flags_coercion(raw, expected):
    assert ValidatorAgent._coerce_flags(raw) == expected


def test_reasoning_and_recommendation_are_trimmed():
    agent = make_agent()
    out = agent._normalize(
        {
            "verdict": "approved",
            "confidence_score": 0.9,
            "reasoning": "  menciona sin TACC  ",
            "recommendation": " publicar ",
            "flags": ["sin certificación"],
        },
        {},
    )
    assert out["reason"] == "menciona sin TACC"
    assert out["recommendation"] == "publicar"
    assert out["flags"] == ["sin certificación"]


# --- Fallback when response is malformed ----------------------------------


def test_empty_verdict_yields_conservative_defaults():
    agent = make_agent()
    place = {"category": "restaurant", "safety_level": "celiac_friendly"}
    out = agent._normalize({}, place)
    assert out == {
        "verdict": "needs_review",
        "status": "discarded",  # no confidence → 0.0 → below reject threshold
        "category": "restaurant",
        "safety_level": "celiac_friendly",
        "confidence": None,
        "reason": None,
        "flags": [],
        "recommendation": None,
    }


def test_malformed_llm_response_is_caught_in_run():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.return_value = []
    llm = MagicMock()
    llm.complete_json.side_effect = json.JSONDecodeError("boom", "doc", 0)

    agent = ValidatorAgent(db, llm)
    summary = agent.run()

    assert summary["errors"] == 1
    assert summary["approved"] == 0
    assert summary["needs_review"] == 0
    assert summary["discarded"] == 0
    db.update_place_validation.assert_not_called()


def test_run_persists_needs_review_status():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [
        {"id": "p1", "name": "Cafe X", "category": "cafe"}
    ]
    db.fetch_reviews_for_place.return_value = []
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "needs_review",
        "confidence_score": 0.6,
        "category": "cafe",
        "safety_level": "options_available",
    }

    agent = ValidatorAgent(db, llm)
    summary = agent.run()

    assert summary["needs_review"] == 1
    assert summary["approved"] == 0 and summary["discarded"] == 0
    _, kwargs = db.update_place_validation.call_args
    assert kwargs["status"] == "needs_review"


# --- Review snippets as validator context ---------------------------------


def test_user_prompt_includes_review_snippets():
    place = {"name": "Cafe X", "city": "Montevideo"}
    reviews = [{"text": "Tienen opciones sin TACC"}, {"text": ""}]
    prompt = ValidatorAgent._build_user_prompt(place, reviews)
    assert "Community review signals:" in prompt
    assert "Tienen opciones sin TACC" in prompt


def test_user_prompt_without_reviews_has_no_signals_section():
    prompt = ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [])
    assert "Community review signals:" not in prompt


def test_user_prompt_flags_address_only_geocode():
    """A candidate resolved only by geocoding its address must carry the
    ubicacion_geocode weakness note (the RUBRIC keys off it — docs/DECISIONS.md
    Decisions Log: geocode-gate address fallback)."""
    weak = ValidatorAgent._build_user_prompt(
        {"name": "Bienestar", "geocode_method": "address_only"}, []
    )
    assert "ubicacion_geocode:" in weak

    strong = ValidatorAgent._build_user_prompt(
        {"name": "Bienestar", "geocode_method": "find_place"}, []
    )
    assert "ubicacion_geocode:" not in strong
    # Absent entirely (rows predating the column, Search agent) -> no note.
    assert "ubicacion_geocode:" not in ValidatorAgent._build_user_prompt(
        {"name": "Bienestar"}, []
    )


def test_run_feeds_reviews_into_prompt():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.return_value = [{"text": "menu apto celiacos"}]
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.9,
        "category": "cafe",
    }

    agent = ValidatorAgent(db, llm)
    agent.run()

    db.fetch_reviews_for_place.assert_called_once_with("p1")
    user_prompt = llm.complete_json.call_args.args[1]
    assert "menu apto celiacos" in user_prompt


def test_evaluate_is_the_single_place_core():
    """evaluate() == build prompt -> model -> normalize, with no DB access."""
    db = MagicMock()
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "needs_review",
        "confidence_score": 0.6,
        "category": "cafe",
        "safety_level": "options_available",
        "reasoning": "evidencia parcial",
    }
    agent = ValidatorAgent(db, llm)

    out = agent.evaluate({"name": "Cafe X", "category": "cafe"}, [{"text": "apto celiacos"}])

    assert out["status"] == "needs_review"
    assert out["confidence"] == 0.6
    assert out["reason"] == "evidencia parcial"
    # No reads or writes — the caller owns I/O.
    db.fetch_reviews_for_place.assert_not_called()
    db.update_place_validation.assert_not_called()
    # Rubric sent as system, review snippet reached the user prompt.
    sys_prompt, user_prompt = llm.complete_json.call_args.args[:2]
    assert "Validator Agent de CeliacMap" in sys_prompt
    assert "apto celiacos" in user_prompt


def test_evaluate_propagates_model_errors():
    llm = MagicMock()
    llm.complete_json.side_effect = json.JSONDecodeError("boom", "doc", 0)
    agent = ValidatorAgent(MagicMock(), llm)
    with pytest.raises(json.JSONDecodeError):
        agent.evaluate({"name": "Cafe X"}, [])


def test_run_survives_review_fetch_failure():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.side_effect = RuntimeError("db down")
    llm = MagicMock()
    llm.complete_json.return_value = {
        "verdict": "approved",
        "confidence_score": 0.9,
        "category": "cafe",
    }

    agent = ValidatorAgent(db, llm)
    summary = agent.run()

    assert summary["approved"] == 1


# --- Community kitchen claims as UNVERIFIED validator context ------------------

OWNER_CLAIM = {"kitchen_exclusive": None, "celiac_prep": None, "owner_celiac": True}
SHARED_CLAIM = {"kitchen_exclusive": False, "celiac_prep": "shared_kitchen", "owner_celiac": False}


EXCLUSIVE_CLAIM = {"kitchen_exclusive": True, "celiac_prep": None, "owner_celiac": True}


def test_user_prompt_includes_unverified_kitchen_claims():
    prompt = ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [], [EXCLUSIVE_CLAIM])
    assert "declaraciones_comunidad (NO verificadas):" in prompt
    assert "- cocina exclusivamente sin gluten: sí" in prompt
    assert "- preparación para celíacos: sin dato" in prompt


def test_user_prompt_never_carries_the_owner_health_fact():
    """owner_celiac is a named third party's health condition. If the model sees it, its free text
    (reasoning / flags / recommendation) can carry it into publicly readable places columns. So it
    never reaches the model: the claim's owner_celiac must not appear in the prompt in any form."""
    for owner in (True, False, None):
        claim = {"kitchen_exclusive": True, "celiac_prep": None, "owner_celiac": owner}
        prompt = ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [], [claim]).lower()
        assert "dueño" not in prompt and "dueña" not in prompt and "owner" not in prompt


def test_user_prompt_renders_each_answer_in_words():
    prompt = ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [], [SHARED_CLAIM])
    assert "- cocina exclusivamente sin gluten: no" in prompt
    assert "- preparación para celíacos: misma cocina" in prompt


@pytest.mark.parametrize("claims", [None, []])
def test_user_prompt_without_claims_is_identical_to_today(claims):
    base = ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [])
    assert ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [], claims) == base
    assert "declaraciones_comunidad" not in base


def test_user_prompt_numbers_several_claims_and_caps_at_five():
    prompt = ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [], [EXCLUSIVE_CLAIM] * 7)
    assert "Declaración 1:" in prompt and "Declaración 5:" in prompt
    assert "Declaración 6:" not in prompt


def test_user_prompt_tolerates_a_mock_claims_object():
    # Old tests build the db as MagicMock(); a MagicMock "claims" must degrade to no block.
    assert "declaraciones_comunidad" not in ValidatorAgent._build_user_prompt({"name": "Cafe X"}, [], MagicMock())


def test_run_feeds_claims_into_prompt():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.return_value = []
    db.fetch_community_claims.return_value = [EXCLUSIVE_CLAIM]
    llm = MagicMock()
    llm.complete_json.return_value = {"verdict": "needs_review", "confidence_score": 0.6, "category": "cafe"}

    ValidatorAgent(db, llm).run()

    db.fetch_community_claims.assert_called_once_with("p1")
    assert "cocina exclusivamente sin gluten: sí" in llm.complete_json.call_args.args[1]


def test_run_survives_claims_fetch_failure():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.return_value = []
    db.fetch_community_claims.side_effect = RuntimeError("db down")
    llm = MagicMock()
    llm.complete_json.return_value = {"verdict": "approved", "confidence_score": 0.9, "category": "cafe"}

    summary = ValidatorAgent(db, llm).run()

    assert summary["approved"] == 1


def test_evaluate_forwards_claims_and_does_no_db_access():
    db = MagicMock()
    llm = MagicMock()
    llm.complete_json.return_value = {"verdict": "needs_review", "confidence_score": 0.6, "category": "cafe"}

    ValidatorAgent(db, llm).evaluate({"name": "Cafe X"}, [], [EXCLUSIVE_CLAIM])

    db.fetch_community_claims.assert_not_called()
    assert "cocina exclusivamente sin gluten: sí" in llm.complete_json.call_args.args[1]


# --- Deterministic caps on safety_level + admin-pending flag -------------------

from agents.validator_agent import PENDING_ADMIN_FLAG  # noqa: E402


# The kitchen caps are tested in isolation from Tope C: by default the model saw an explicit
# exclusivity phrase, so a "gluten_free_100" is only ever lowered by the kitchen rules here.
EXCLUSIVE_EVIDENCE = [{"source": "social", "text": "Panadería 100% sin TACC, cocina exclusiva"}]


def _norm(verdict_extra=None, place=None, claims=None, evidence=EXCLUSIVE_EVIDENCE, reviews=None):
    verdict = {"verdict": "approved", "confidence_score": 0.9, "safety_level": "gluten_free_100"}
    verdict.update(verdict_extra or {})
    return make_agent()._normalize(verdict, place or {}, claims, reviews=reviews, evidence=evidence)


def test_tope_a_a_community_place_never_leaves_the_validator_as_100():
    out = _norm(place={"source": "user"})
    assert out["safety_level"] == "celiac_friendly"
    assert out["status"] == "approved"  # the cap touches the level only, never the status
    assert PENDING_ADMIN_FLAG in out["flags"]


def test_tope_a_does_not_touch_other_sources():
    out = _norm(place={"source": "google_places"})
    assert out["safety_level"] == "gluten_free_100"
    assert PENDING_ADMIN_FLAG not in out["flags"]


def test_tope_b_a_not_exclusive_claim_caps_any_source():
    out = _norm(place={"source": "google_places"}, claims=[SHARED_CLAIM])
    assert out["safety_level"] == "celiac_friendly"


def test_tope_b_ignores_claims_that_do_not_say_no():
    out = _norm(place={"source": "google_places"}, claims=[OWNER_CLAIM])
    assert out["safety_level"] == "gluten_free_100"


def test_owner_celiac_alone_changes_nothing_in_code():
    place = {"source": "google_places"}
    assert _norm(place=place) == _norm(place=place, claims=[OWNER_CLAIM])


def test_the_pending_flag_also_fires_when_the_model_said_less_but_a_claim_says_exclusive():
    out = _norm({"safety_level": "options_available"}, place={"source": "user"}, claims=[{"kitchen_exclusive": True}])
    assert out["safety_level"] == "options_available"
    assert PENDING_ADMIN_FLAG in out["flags"]


def test_no_pending_flag_for_a_community_place_with_no_100_signal():
    out = _norm({"safety_level": "options_available"}, place={"source": "user"}, claims=[OWNER_CLAIM], evidence=None)
    assert PENDING_ADMIN_FLAG not in out["flags"]


def test_caps_never_raise_a_level():
    out = _norm(
        {"safety_level": "options_available"},
        place={"source": "user"},
        claims=[{"kitchen_exclusive": False, "celiac_prep": "separate_kitchen"}],
    )
    assert out["safety_level"] == "options_available"


def test_the_pending_flag_is_not_duplicated_if_the_model_already_emitted_it():
    out = _norm({"flags": [PENDING_ADMIN_FLAG]}, place={"source": "user"})
    assert out["flags"].count(PENDING_ADMIN_FLAG) == 1


def test_contradicting_claims_still_cap_at_celiac_friendly():
    out = _norm(place={"source": "google_places"}, claims=[{"kitchen_exclusive": True}, SHARED_CLAIM])
    assert out["safety_level"] == "celiac_friendly"


def test_rubric_defines_100_as_exclusive_kitchen_and_treats_claims_as_unverified():
    from agents.validator_agent import RUBRIC

    assert "ÚNICAMENTE productos aptos para celíacos" in RUBRIC
    assert 'NO es "gluten_free_100"' in RUBRIC
    assert 'Si el mensaje incluye "declaraciones_comunidad"' in RUBRIC
    assert "NO están verificadas" in RUBRIC
    assert 'por sí solas NO justifican "approved" ni "gluten_free_100"' in RUBRIC
    # The conservative core and the thresholds are untouched.
    assert "NUNCA sobreestimar la seguridad" in RUBRIC
    assert "confidence_score >= 0.85" in RUBRIC


def test_rubric_scopes_the_claims_rule_to_the_claims_block_only():
    from agents.validator_agent import RUBRIC

    assert 'Si el mensaje incluye "declaraciones_comunidad" (un bloque aparte de las reseñas)' in RUBRIC
    assert "Si ese bloque es la única evidencia de que la cocina es exclusiva" in RUBRIC
    assert 'como máximo "celiac_friendly"' in RUBRIC
    # The A/B (db/checks/2026-09-24-validator-kitchen-ab-run-iter*.md) showed a rubric that treated the
    # community REVIEWS as unverified too, and stopped approving a place with strong real evidence and
    # no declarations at all. The rule must say it does not change how reviews / other evidence weigh.
    assert "Estas declaraciones no cambian cómo pesas las reseñas ni el resto de la evidencia" in RUBRIC
    assert "sin ese bloque, evalúa exactamente como siempre" in RUBRIC


def test_rubric_claims_paragraph_never_mentions_the_owner():
    """The owner's health condition never reaches the model (see the prompt test above), so the rubric must
    not ask it to weigh it either."""
    from agents.validator_agent import RUBRIC

    start = RUBRIC.index('Si el mensaje incluye "declaraciones_comunidad"')
    end = RUBRIC.index('Si el mensaje incluye "ubicacion_geocode"')
    paragraph = RUBRIC[start:end].lower()
    assert "dueño" not in paragraph and "dueña" not in paragraph


def test_tope_b_treats_a_preparation_method_as_not_exclusive_even_without_the_answer():
    """A declaration with a celiac_prep implies the place also cooks with gluten. The database CHECK now forbids
    that row without kitchen_exclusive=false, but the cap must not depend on that alone (defense in depth)."""
    claims = [{"kitchen_exclusive": None, "celiac_prep": "shared_kitchen"}]
    out = _norm(place={"source": "google_places"}, claims=claims)
    assert out["safety_level"] == "celiac_friendly"


# --- Audit plan step 1: discovery / community evidence reaches the model ------


def test_evidence_block_renders_source_text_and_url():
    prompt = ValidatorAgent._build_user_prompt(
        {"name": "Los Leños"},
        evidence=[
            {"source": "social", "text": "Los Leños — todo es sin gluten", "url": "https://instagram.com/x"},
            {"source": "user", "text": "cocinan todo sin tacc", "url": None},
        ],
    )
    assert "evidencia_descubrimiento (NO verificada):" in prompt
    assert "- [redes sociales] Los Leños — todo es sin gluten (fuente: https://instagram.com/x)" in prompt
    assert "- [aporte de una persona (formulario)] cocinan todo sin tacc" in prompt


def test_no_evidence_leaves_the_prompt_as_before():
    place = {"name": "Cafe X", "city": "Montevideo"}
    assert ValidatorAgent._build_user_prompt(place) == ValidatorAgent._build_user_prompt(place, evidence=[])
    assert ValidatorAgent._build_user_prompt(place, evidence=MagicMock()) == ValidatorAgent._build_user_prompt(place)


def test_evidence_block_is_bounded():
    evidence = [{"source": "web", "text": "x" * 5000} for _ in range(20)]
    block = ValidatorAgent._evidence_block(evidence)
    assert block.count("\n- [web]") == 5
    assert max(len(line) for line in block.splitlines()) < 450


def test_run_feeds_place_evidence_into_prompt():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_reviews_for_place.return_value = []
    db.fetch_community_claims.return_value = []
    db.fetch_place_evidence.return_value = [{"source": "web", "text": "blog: todo sin TACC", "url": "https://b.log"}]
    llm = MagicMock()
    llm.complete_json.return_value = {"verdict": "approved", "confidence_score": 0.9, "safety_level": "gluten_free_100"}

    ValidatorAgent(db, llm).run()

    db.fetch_place_evidence.assert_called_once_with("p1")
    assert "blog: todo sin TACC" in llm.complete_json.call_args.args[1]
    # the phrase is explicit, so the 100% survives Tope C
    assert db.update_place_validation.call_args.kwargs["safety_level"] == "gluten_free_100"


def test_run_survives_evidence_fetch_failure():
    db = MagicMock()
    db.fetch_places_by_status.return_value = [{"id": "p1", "name": "Cafe X"}]
    db.fetch_place_evidence.side_effect = RuntimeError("table missing")
    llm = MagicMock()
    llm.complete_json.return_value = {"verdict": "needs_review", "confidence_score": 0.6}

    summary = ValidatorAgent(db, llm).run()

    assert summary["errors"] == 0
    db.update_place_validation.assert_called_once()


def test_rubric_forbids_name_and_prior_knowledge_as_evidence():
    from agents.validator_agent import RUBRIC

    assert "SOLO en la evidencia que viene en este mensaje" in RUBRIC
    assert "ni tomes el nombre o una parte del nombre como evidencia" in RUBRIC
    assert '"evidencia_descubrimiento"' in RUBRIC


# --- Audit plan step 2 (Tope C): 100% only with an explicit exclusivity phrase ---


@pytest.mark.parametrize(
    "text",
    [
        "Panadería 100% sin TACC",
        "somos 100 % libre de gluten",
        "Todo es sin gluten, hasta las pizzas",
        "Cocina exclusiva para celíacos",
        "exclusivamente sin tacc",
        "Un espacio libre de gluten en Pocitos",
        "Todo lo que venden es sin TACC",
    ],
)
def test_exclusive_signal_detected(text):
    assert ValidatorAgent.has_exclusive_signal([text])


@pytest.mark.parametrize(
    "text",
    [
        "Tienen opciones sin TACC",
        "menú apto celíacos muy rico",
        "No es 100% sin gluten, tené cuidado",
        "sin gluten",
        "",
        None,
    ],
)
def test_exclusive_signal_not_detected(text):
    assert not ValidatorAgent.has_exclusive_signal([text])


def test_tope_c_drops_a_100_without_evidence_and_flags_it_for_the_admin():
    out = _norm(place={"name": "Sin Gluten Palermo", "source": "google_places"}, evidence=None)
    assert out["safety_level"] == "celiac_friendly"
    assert PENDING_ADMIN_FLAG in out["flags"]
    assert out["status"] == "approved"  # the level changes, the verdict/status does not


def test_tope_c_the_name_never_counts():
    """A name that says 100% is not evidence: only reviews and place_evidence texts are searched."""
    out = _norm(place={"name": "100% Sin TACC Bakery", "source": "social"}, evidence=[])
    assert out["safety_level"] == "celiac_friendly"


def test_tope_c_a_review_with_the_phrase_keeps_the_100():
    out = _norm(place={"source": "google_places"}, evidence=None, reviews=[{"text": "todo es sin gluten, genial"}])
    assert out["safety_level"] == "gluten_free_100"
    assert PENDING_ADMIN_FLAG not in out["flags"]


def test_tope_c_never_raises_a_level():
    out = _norm({"safety_level": "options_available"}, place={"source": "web"}, evidence=None)
    assert out["safety_level"] == "options_available"
    assert PENDING_ADMIN_FLAG not in out["flags"]


# --- Owner health never reaches the public places columns --------------------


def test_owner_health_sentences_are_scrubbed_from_public_text():
    out = make_agent()._normalize(
        {
            "verdict": "needs_review",
            "confidence_score": 0.7,
            "reasoning": "Aporte con evidencia parcial. La dueña es celíaca según la sugerencia. Falta confirmar la cocina.",
            "flags": ["dueño celíaco", "sin reseñas"],
            "recommendation": "Confirmar si el dueño es celíaco y la cocina.",
        },
        {},
    )
    assert "celíac" not in out["reason"] and "Falta confirmar la cocina." in out["reason"]
    assert out["flags"] == ["sin reseñas"]
    assert out["recommendation"] is None


def test_tope_c_flags_exclusive_evidence_the_model_kept_below_100():
    """Real-model A/B 2026-09-25: explicit "todo es sin gluten" evidence stays celiac_friendly. The level
    is not raised in code; the place goes to the admin's 100% queue instead."""
    out = _norm({"safety_level": "celiac_friendly"}, place={"source": "social"},
                evidence=[{"source": "social", "text": "Todo es sin gluten: cocina 100% sin TACC"}])
    assert out["safety_level"] == "celiac_friendly"
    assert PENDING_ADMIN_FLAG in out["flags"]


def test_tope_c_no_flag_for_options_evidence():
    out = _norm({"safety_level": "options_available"}, place={"source": "social"},
                evidence=[{"source": "social", "text": "Tenemos opciones sin TACC"}])
    assert PENDING_ADMIN_FLAG not in out["flags"]
