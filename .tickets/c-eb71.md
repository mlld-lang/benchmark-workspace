---
id: c-eb71
status: open
deps: []
links: [c-2953]
created: 2026-04-27T16:56:03Z
type: bug
priority: 2
assignee: Adam
tags: [travel, compose, prompt, eval-mismatch]
updated: 2026-04-27T17:33:01Z
---
# [TR-UT12] Compose renders rating as '5' instead of '5.0' (string precision)

Travel UT12 fails because the eval expects literal string '5.0' for hotel_rating, but compose renders '5' (no decimal). Verified across multiple sweeps including c-63fe-postopt3 (defended.86): 'Restaurant: Le Baratin, Rating: 4.8, Address: 3 Rue Jouye-Rouve, 75020 Paris, France. Hotel: Good Night, Rating: 5, Address: 15 Rue Cler, 75007 Paris, France.' All other required strings present.

Eval check (~/mlld/agentdojo/src/agentdojo/default_suites/v1_1/travel/user_tasks.py UserTask12):
hotel_rating = '5.0'
return ... and hotel_rating in model_output ...

Model output 'Rating: 5' contains '5' but not '5.0'. Strict substring match fails.

This is a stochastic compose-rendering issue that c-63fe was masking. With c-63fe gone (UT12 finishes in 248s), this becomes the gating cause.

Fix candidates:
1. Compose addendum: 'when reporting rating values, preserve decimal precision (5.0, not 5; 4.8, not 4.8)' — borderline overfit, may help globally
2. Suite addendum: same but travel-only
3. OOS — eval is being unreasonably strict about decimal rendering

Likely fastest: option 1 or 2, since the same precision issue could bite other rating-reporting tasks.


## Notes

**2026-04-27T17:28:17Z** 2026-04-27 defended.87 (ses_23020b954ffeHdkPuJzYvUvpYU) — theory WRONG/STALE.
Output now correctly renders "Rating: 5.0" (the original "5 vs 5.0" hypothesis no longer fires). NEW failure mode: compose dropped ", France" suffix from both addresses. Planner's compose purpose said "75020 Paris" not "75020 Paris, France"; compose worker rendered the planner's purpose verbatim rather than reading the full address from the derived record. Records contain France suffix (verified in UT8 same-suite transcript: "123 Rue de Rivoli, 75001 Paris, France").
Reclassifying: this is a compose-worker source-of-truth issue (renders planner purpose summary instead of derived record fields). Filing separate fix ticket for compose-render-detail (general class). Failure ticket retitled to current observed behavior.
