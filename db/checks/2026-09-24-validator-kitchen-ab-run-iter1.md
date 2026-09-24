
[claim-only] owner_celiac_only
  OLD: verdict {'needs_review': 4} | safety {'options_available': 4}
  NEW: verdict {'needs_review': 4} | safety {'options_available': 4}

[claim-only] exclusive_claim_only
  OLD: verdict {'needs_review': 4} | safety {'gluten_free_100': 4}
  NEW: verdict {'needs_review': 4} | safety {'gluten_free_100': 4}
  !! FAIL: NEW rubric let a declaration alone produce approved=0 / 100%=4

[claim-only] exclusive_and_owner
  OLD: verdict {'needs_review': 4} | safety {'gluten_free_100': 4}
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 3, 'gluten_free_100': 1}
  !! FAIL: NEW rubric let a declaration alone produce approved=0 / 100%=1

[claim-only] contradicting_claims
  OLD: verdict {'needs_review': 4} | safety {'options_available': 4}
  NEW: verdict {'needs_review': 4} | safety {'options_available': 4}

[claim-only-low] shared_kitchen
  OLD: verdict {'rejected': 4} | safety {'options_available': 4}
  NEW: verdict {'rejected': 4} | safety {'options_available': 4}

[claim-only-low] separate_kitchen
  OLD: verdict {'needs_review': 4} | safety {'options_available': 4}
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

[regression] no_claims_neutral
  OLD: verdict {'rejected': 2, 'needs_review': 2} | safety {'options_available': 4}
  NEW: verdict {'rejected': 4} | safety {'options_available': 4}

[regression] no_claims_named_gluten_free
  OLD: verdict {'needs_review': 4} | safety {'gluten_free_100': 3, 'celiac_friendly': 1}
  NEW: verdict {'needs_review': 4} | safety {'gluten_free_100': 3, 'celiac_friendly': 1}

RESULT: FAIL (2 failing case(s))
