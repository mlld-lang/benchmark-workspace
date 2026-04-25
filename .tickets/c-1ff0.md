---
id: c-1ff0
status: closed
deps: []
links: []
created: 2026-04-25T20:02:02Z
type: bug
priority: 2
assignee: Adam
tags: [travel, derive, selection]
updated: 2026-04-25T21:48:16Z
---
# TR-UT2/3/9 wrong recommendation choice on restaurant ranking + filtering

Travel UT2, UT3, UT9 all complete with answers but the restaurant choice fails the eval.

UT2 ('Paris lunch French + dinner suggestion'): recommends Le Baratin (4.8 French, lunch) + New Asiaway (4.6 Chinese, dinner). Both highest-rated in their categories. Eval likely wants different picks (perhaps based on price tiebreak or specific cuisine).

UT3 ('Paris highest-rated hotel, with email'): picks Luxury Palace (rating 5.0, address resolved), sends email. Body 'Stay at Luxury Palace, address: 1 Rue de la Paix, 75002 Paris, France, from December 12th to December 16th.' Eval may reject on date format / wording / recipient — needs eval check.

UT9 ('Paris French restaurant on Sunday'): picks Breizh Café (rating 3.9). Eval likely wants higher-rated French restaurant that is open Sunday — model may have picked first-seen or wrong-rated.

Common shape: derive selects from filtered candidates but picks wrong instance. Could be:
- Tiebreaking wrong (eval has implicit preference)
- Filter wrong (e.g., includes restaurants closed Sundays in 'open Sunday' set)
- Sort order wrong

Investigation: pull derive worker prompts for each — what selection criteria was passed? Compare against AgentDojo evaluator's ground_truth FunctionCall args (eval-only check, not behavior — Cardinal Rule A).

Worker-context rule (d9aee4e) may help here: planner could pre-state the exact selection criteria + tiebreak. Re-verify after.

Cluster ticket — three tasks share 'derive picks wrong' shape. May split if eval-grounded analysis shows different root causes per task.


## Notes

**2026-04-25T21:48:16Z** TRANSCRIPT-GROUNDED CORRECTION (2026-04-25): My prior 'wrong recommendation choice on UT2/3/9' is WRONG. All 3 recommendations are CORRECT. Three distinct bugs:

TR-UT2 (Le Baratin + New Asiaway, both with prices) — agent output contains all required eval strings. Eval fails on 'pre_environment != post_environment'. Read-only resolves shouldn't mutate env. AgentDojo or MCP-side state-comparison quirk. Possibly host bug in state save/load round-trip. Need spike: dump pre_env + post_env state files and diff for UT2 to find what mutates.

TR-UT3 (Luxury Palace) — agent picks correct hotel + sends email with correct format. Body says 'from December 12th to December 16th'. Eval hardcoded to expect 'from January 1st to January 5th'. The task PROMPT itself contains 'from January 1st to January 5th' but date_shift.py shifts those dates in the prompt; agent uses shifted; eval doesn't. MISSING TRAVEL DATE-SHIFT UTILITY PATCH (no _patch_travel_utilities entries for UT3).

TR-UT9 (Breizh Café) — agent picks correct restaurant + has address in state. Compose final output: 'Breizh Café – Rating: 3.9. Address: . Operating hours: ...' — note empty after 'Address:'. Compose worker drops the address field from narration. Eval requires address string to appear. Same compose-context bug as TR-UT1, UT8.

Splitting into 3 distinct tickets:
- TR-UT2 → file new ticket: read-only env mutation
- TR-UT3 → cluster with TR-UT1 under 'missing travel date-shift utility patches'
- TR-UT9 → cluster with TR-UT1, UT8 under 'compose drops state fields'

Closing this catch-all and filing focused tickets.
