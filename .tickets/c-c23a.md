---
id: c-c23a
status: closed
deps: []
links: [c-0589]
created: 2026-04-27T17:31:20Z
type: bug
priority: 1
assignee: Adam
updated: 2026-04-27T19:12:49Z
---
# Fix: execute returns 'executed' status without invoking MCP write (WS-UT8 mutated shape)

**Bug**: For WS-UT8 (ses_230213533ffevJzCHhaaIjVp8O), the planner finally constructed an accepted execute call that returned `{"status":"executed","result_handles":[]}`. But mcp_calls trace shows only 2 calls — both reads (search_calendar_events, get_day_calendar_events). The underlying add_calendar_event_participants MCP write was NEVER invoked.

**Hypotheses**:
1. Policy guard short-circuited to "executed" on a recovered exception path
2. dispatchExecute lost the MCP call after intent_compile passed
3. The empty result_handles is a signal that needs to surface as an error/blocked terminator instead of "executed"

**Suggested approach**:
1. Read rig/runtime.mld + intent.mld + dispatchExecute path for the case where intent_compile passes but the MCP layer doesn't get the call. Look for early-return conditions or silent catches.
2. Spike: synthesize the exact intent (executed for add_calendar_event_participants with the failing arg shape) and trace through dispatchExecute to find where the MCP call is dropped.
3. At minimum, surface this as an error to the planner instead of "executed" — silent success is a Type 2 framework bug per CLAUDE.md "no silent failures".

**Linked failure ticket**: c-0589 (mutated). Possibly adjacent to c-d52c file_id mapping issues if both are in the same dispatch seam.


## Notes

**2026-04-27T19:12:49Z** 2026-04-27 UPDATE — bug NOT currently reproducible post-c-c79c fix.

Original symptom (run 25008228406, ses_230213533): planner constructed an accepted execute call returning `{"status":"executed","result_handles":[]}` but the underlying add_calendar_event_participants MCP write was never invoked.

After c-c79c fix landed (extract.mld now imports plainObjectKeys), local UT8 reruns show a different failure mode: planner attempts add_calendar_event_participants execute, intent_compile rejects with `payload_only_source_in_control_arg` (planner used `{source:"derived"}` for event_id; control args require resolved/known/selection). Status returned is "error", not "executed". The MCP write is never invoked because intent_compile correctly rejects.

Hypothesis: the original "executed without MCP" symptom was a follow-on artifact of the c-c79c cluster — after the validator wrongly rejected inline schemas, the planner burned iterations trying alternate shapes, and at some point landed on a shape that intent_compile passed but dispatchExecute did not invoke. With c-c79c fixed, the planner doesn't get into that state in the local rerun.

Recommended action: defer until/unless we see "executed/result_handles=[] with no MCP call" recur in a sweep post-c-c79c. The remaining UT8 gating is now `payload_only_source_in_control_arg` which is c-0589 territory (planner using derived event_id instead of resolved field — either planner discipline or selection_ref bridge gap).
