---
id: c-eb71
status: closed
deps: []
links: [c-2953]
created: 2026-04-27T16:56:03Z
type: bug
priority: 2
assignee: Adam
tags: [travel, compose, prompt, eval-mismatch]
updated: 2026-04-30T20:48:27Z
---
# TR-UT12 - rating dropped decimal precision (CLOSED)

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

**2026-04-27T22:50:38Z** 2026-04-27 reproduces in run 25023003899 / local ses_22eeac35fffeXNDN21WqiGIUkp.

Compose worker rendered planner's purpose with JSON-numeric form `5` rather than literal string "5.0". This sweep's failure surface is "5 vs 5.0"; LAST sweep's surface was "Paris vs Paris, France". Same root cause: compose-purpose-as-source-of-truth (c-2953). Stochastic between sweeps which detail drops first.

Action c-2953: tighten compose-worker prompt to render exact field values from records — preserve trailing decimals when source field is a number with .0 precision; preserve the full address string from records.

**2026-04-30T20:48:27Z** ACTUAL ROOT CAUSE — fixed in commit 7d28cb1 (bench-grind-13, with c-2953).

Both 2026-04-27 notes (original 'compose drops record detail / rating-precision' theory and the second 'compose-purpose-as-source-of-truth / address suffix dropped' theory) — SUPERSEDED by transcript-grounded diagnosis: planner-authored derive schemas declared rating fields with 'type': 'number'. JS Number coercion normalizes integer-valued floats: 5.0 → 5. Compose was reading derive output (integer 5), not the original review_blob string ('5.0'). The sweep-to-sweep surface variation (sometimes '5' vs '5.0', sometimes 'Paris' vs 'Paris, France') reflected which task instance the planner was running, not a stochastic compose paraphrase.

Fix: rating-as-string structurally end-to-end — bridge keeps verbatim, records type as string?, planner addendum directs derive schemas to use 'type': 'string' for rating fields rather than 'type': 'number'.

UT12 went from 1/3 → 5/5 deterministic post-fix.

Cardinal Rule D reinforced: two consecutive theories were wrong; transcript + records inspection found the structural typing cause. Original hypotheses preserved in body for the audit trail.
