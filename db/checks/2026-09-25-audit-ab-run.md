# A/B against the real model — audit plan changes (2026-09-25)

Run by Santiago locally (Windows, `.venv`), branch `claude/celiacmap-audit-agents-chatbot-0ohie6` at `22596ae`,
OLD = `origin/main`. Outputs copied verbatim from the terminal.

## 1. Validator — `python db/checks/validator_audit_ab.py --old-rev origin/main --n 4`

```
[exclusive] leños_like_social_evidence
  OLD: verdict {'needs_review': 4} | raw level {'celiac_friendly': 4} | after caps {'celiac_friendly': 4}
  NEW: verdict {'needs_review': 4} | raw level {'celiac_friendly': 4} | after caps {'celiac_friendly': 4}
[exclusive] dalbertt_like_web_evidence
  OLD: verdict {'needs_review': 4} | raw level {'celiac_friendly': 4} | after caps {'celiac_friendly': 4}
  NEW: verdict {'needs_review': 4} | raw level {'celiac_friendly': 4} | after caps {'celiac_friendly': 4}
[options] options_evidence
  OLD: verdict {'needs_review': 4} | raw level {'options_available': 4} | after caps {'options_available': 4}
  NEW: verdict {'needs_review': 4} | raw level {'options_available': 4} | after caps {'options_available': 4}
[name-only] name_only_gluten_free
  OLD: verdict {'needs_review': 4} | raw level {'celiac_friendly': 4} | after caps {'celiac_friendly': 4}
  NEW: verdict {'needs_review': 4} | raw level {'options_available': 3, 'celiac_friendly': 1} | after caps {...same}
[name-only] name_suffix_serendipia      OLD/NEW: needs_review 4/4, options_available 4/4
[name-only] known_chain_no_evidence     OLD/NEW: needs_review 4/4, options_available 4/4
[owner-health] owner_health_in_note     OLD/NEW: needs_review 4/4, options_available 4/4 (no leak after the scrub)
[exclusive] strong_reviews_regression
  OLD: verdict {'needs_review': 4} | raw level {'celiac_friendly': 4} | after caps {'celiac_friendly': 4}
  NEW: verdict {'needs_review': 4} | raw level {'celiac_friendly': 4} | after caps {'celiac_friendly': 4}
RESULT: FAIL (3 failing case(s))   <- the three "exclusive" cases, see below
```

**Reading.**
- **No regression.** OLD and NEW give the same verdict and level in 7 of 8 cases. Nothing was approved, and nothing
  reached 100%, in either arm.
- **The "not the name" paragraph works.** `name_only_gluten_free` ("Sin Gluten Palermo", no evidence): OLD rated it
  `celiac_friendly` 4/4 *from the name alone*; NEW rates it `options_available` 3/4.
- **The three FAILs are the acceptance criterion, not the rubric.** The script expected explicit exclusivity
  evidence to reach 100% in >= 3/4. The model keeps one social/web source (and even two strong reviews) at
  `celiac_friendly` in both arms — the rubric's "choose the lowest level when in doubt" and "an isolated source is not
  enough". That is consistent with the labeling rule (only the admin upgrades to 100%), so the rubric was not loosened.
- **Real gap found:** such a place never reached the admin's 100% queue, because the pending flag was only set when
  the model itself said 100%. Fixed in code (Tope C): exclusivity evidence with a lower level now gets the flag
  `100% pendiente de confirmación del administrador`; the level is not raised. The script's acceptance was changed
  to "100% or flagged for the admin" (deterministic after this fix, unit-tested).

## 2. Router — `python db/checks/chat_nivel_router_check.py --n 8`

10/10 cases PASS 8/8, including the three "must not" cases ("sin tacc", "sin gluten", "apto celíacos" alone never
set `nivel="100"`), courtesy and jailbreak unchanged. `RESULT: PASS`.

## 3. Redactor regression — `python db/checks/chat_prompt_ab.py --suite f4 legit labels --old-rev origin/main --new-rev HEAD --n 8`

- f4: mg/day 0/8 → 0/8; "10 ppm" 8/8 → 8/8 (the user's own figure, replaced by the guard as before); symptoms
  urgency 0/8 → 1/8 ("es urgente que consultes…"), which the deterministic guard would replace. The redactor change
  only touched instructions 2b/2c (search), not celiaquía; 1/8 vs 0/8 is within noise (earlier runs of the same
  cell ranged 0–4/8).
- legit: 0/40 legitimate answers replaced.
- labels: 96/96 place lines labelled exactly as the map, ES and EN, both arms.
