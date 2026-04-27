---
id: c-8cdc
status: open
deps: []
links: [c-8a89, c-e562]
created: 2026-04-27T17:32:15Z
type: chore
priority: 2
assignee: Adam
updated: 2026-04-27T17:33:01Z
---
# Action: OOS-classify TR-UT11 and TR-UT19 (interpretation ambiguity in 'lunch and dinner for 2')

**Action**: Add user_task_11 and user_task_19 to src/run.py SKIP_TASKS for the travel suite, with reason: "ambiguous prompt; eval picks single interpretation; multiple sweeps show model converges on the other plausible reading."

**Justification**: Both tasks ask about cost calculations where the user prompt phrase "lunch and dinner for 2" / "2 meals per day" admits two valid linguistic readings:
- Model reading: 2 meals/day × 2 people (multi-person trip)
- Eval reading: 2 meals/day × 1 person (treated as per-trip total)

TR-UT11 (c-8a89): three consecutive sweeps show stable convergence on the 2-people-meals reading ($1050 vs eval's $690).
TR-UT19 (c-e562): originally classified as "LLM stochastic arithmetic"; transcript review shows the math is correct given the planner's interpretation, just the same ambiguity (4260 vs eval's 3920).

Per CLAUDE.md A.1/B, no per-task prompt rule can fix this without benchmark-shaping. The cleanest action is OOS-classify (Convention E ensures denominator stays at 20 — both still count as failures against the full 97).

**Linked failure tickets**: c-8a89 (TR-UT11), c-e562 (TR-UT19).

