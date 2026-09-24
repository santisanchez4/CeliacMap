
[claim-only] owner_celiac_only
  NEW: verdict {'needs_review': 4} | safety {'options_available': 4}

[claim-only] exclusive_claim_only
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

[claim-only] exclusive_and_owner
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

[claim-only] contradicting_claims
  NEW: verdict {'needs_review': 4} | safety {'options_available': 4}

[claim-only-low] shared_kitchen
  NEW: verdict {'rejected': 4} | safety {'options_available': 4}

[claim-only-low] separate_kitchen
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

[regression] no_claims_neutral
  NEW: verdict {'rejected': 4} | safety {'?': 3, 'options_available': 1}

[regression] no_claims_named_gluten_free
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

RESULT: PASS (0 failing case(s))
