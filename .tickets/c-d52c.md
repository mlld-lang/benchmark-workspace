---
id: c-d52c
status: open
deps: []
links: []
created: 2026-04-24T20:04:26Z
type: bug
priority: 1
assignee: Adam
---
# UT32/37: execute result handle chaining not working end-to-end. The execute attestation returns result_handles and planner prompt documents how to use them, but the planner still can't chain create_file → share_file. Investigate transcript: does the planner attempt to use result_handles? Does the intent compiler accept them? May need the result handles added to resolved state so the planner can reference them as resolved refs.

