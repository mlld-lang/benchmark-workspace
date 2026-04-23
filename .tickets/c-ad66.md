---
id: c-ad66
status: open
deps: []
links: [c-pe02, c-eeb6, c-32db]
created: 2026-04-23T04:39:31Z
type: bug
priority: 0
assignee: Adam
tags: [extract, worker, null-response]
updated: 2026-04-23T16:44:06Z
---
# Extract worker returns null on source-backed extraction from resolved records

UT4: When the extract worker receives a resolved calendar_evt record as source and is asked to extract description/title fields, it returns null. The planner correctly passes the source ref and a schema, the extract dispatcher resolves the source value, calls the LLM worker with the full record content — but the worker produces no output.

This is different from tool-backed extract (get_email_by_id) returning null, which is an MCP bridge issue. This is the source-backed path where the extract LLM worker runs and returns nothing.

The model tried 3 parallel source-backed extracts for 3 different calendar events — all returned null. Then tried inline JSON schemas — rejected with extract_empty_inline_schema.

Possible causes:
1. The extract worker prompt doesn't give enough guidance for extracting from calendar records
2. The schema_name 'calendar_evt_summary' doesn't match any available record, confusing the worker
3. The worker LLM doesn't understand what to extract when the schema is a bare JSON object

Worth checking: does the extract worker prompt include the source record's actual content? Or is it getting the planner-projected view (which hides title/description)?

