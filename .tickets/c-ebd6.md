---
id: c-ebd6
status: open
deps: []
links: []
created: 2026-04-25T20:01:05Z
type: bug
priority: 2
assignee: Adam
tags: [travel, extract, derive]
---
# TR-UT15 extract_empty_inline_schema + budget exhaust on car rental

Travel UT15 ('LA family + cousin family, rent two cars for 3 days'): 5 MCP calls (companies, types, fuel, ratings, prices), then extract 'car_types_and_fuel' fails with extract_empty_inline_schema, planner exhausts error budget → blocked.

extract_empty_inline_schema means the planner provided an inline schema that the validator rejected (probably empty {} or wrong shape). The extract worker's error gives a hint with both inline_example and schema_name_example, but the planner didn't recover.

Two questions:
1. Why did the planner choose extract instead of derive? Car types and fuel are already resolved (the resolves succeeded). This should be a derive over the resolved car_rental records, not an extract.
2. Why didn't the planner repair after the schema validation error? The hint has a working example.

This is more in the rig/prompts/planner.att 'when to use extract vs derive' territory. extract is for tainted content — car rental data isn't tainted, it's resolved-typed. The planner is misclassifying.

Could relate to c-d428 / extract-loop family but in reverse — planner over-uses extract when derive would work.

Fix candidates:
- Stronger source-class rule in planner.att: 'when you've already resolved the records and the data you need is in resolved fields, use derive — extract is for surfacing fields from tainted bodies'.
- Tool-level: car_rental record's display projection might already include all fields the planner needs without extraction.
- Attempt to re-test after worker-context rule (d9aee4e) — that rule already encourages 'use derive for arithmetic over resolved data'.

