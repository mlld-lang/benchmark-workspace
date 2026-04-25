---
id: c-1ff0
status: open
deps: []
links: []
created: 2026-04-25T20:02:02Z
type: bug
priority: 2
assignee: Adam
tags: [travel, derive, selection]
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

