---
id: c-pe06
status: open
deps: [c-pe04]
links: []
created: 2026-04-23T16:43:41Z
type: task
priority: 2
assignee: Adam
tags: [prompt-audit, bench, travel]
updated: 2026-04-23T16:43:41Z
---
# Travel suite addendum and tool descriptions

Travel has the most complex multi-step workflow of any suite (family resolve -> per-instance metadata -> derive -> execute/compose) but no suite addendum. Pattern C (resolve loop) is the dominant travel failure.

Create bench/domains/travel/prompts/planner-addendum.mld:
- Document the family -> instance -> metadata -> derive/execute workflow
- Explain that metadata tools require SPECIFIC item names from a prior get_all_*_in_city result
- Not city names or category filters

Improve travel tool descriptions (bench/domains/travel/tools.mld):
- All metadata tools (get_cuisine_type, get_rating_reviews, get_prices, get_address, etc.): explain that the arg is an array of specific names from a prior family resolve
- get_all_*_in_city tools: clarify these return the family, use the names in subsequent metadata calls

See plan-prompt-error-updates.md M4 + M5.

Files: bench/domains/travel/prompts/planner-addendum.mld (new), bench/domains/travel/tools.mld
Depends: c-pe04 (rig-level changes first)

Testing:
1. Rig test gate (validate)
2. Canary: travel UT2 (resolve loop), travel UT9 (family ref where instance needed)
3. Regression: travel UT0 (was passing previously)

