
[claim-only] owner_celiac_only
  OLD: verdict {'needs_review': 4} | safety {'options_available': 4}
  NEW: verdict {'needs_review': 4} | safety {'options_available': 4}

[claim-only] exclusive_claim_only
  OLD: verdict {'needs_review': 4} | safety {'gluten_free_100': 4}
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

[claim-only] exclusive_and_owner
  OLD: verdict {'needs_review': 4} | safety {'gluten_free_100': 4}
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

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
  OLD: verdict {'needs_review': 2, 'rejected': 2} | safety {'options_available': 4}
  NEW: verdict {'rejected': 4} | safety {'options_available': 4}

[regression] no_claims_named_gluten_free
  OLD: verdict {'needs_review': 4} | safety {'gluten_free_100': 4}
  NEW: verdict {'needs_review': 4} | safety {'celiac_friendly': 4}

[regression] no_claims_strong_evidence
  OLD: verdict {'approved': 4} | safety {'gluten_free_100': 4}
  NEW: verdict {'approved': 4} | safety {'gluten_free_100': 4}

RESULT: PASS (0 failing case(s))
