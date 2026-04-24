---
id: c-0a6b
status: closed
deps: []
links: []
created: 2026-04-24T20:48:32Z
type: bug
priority: 1
assignee: Adam
updated: 2026-04-24T21:05:14Z
---
# Proof system gap: proofless known value '24' accepted for control arg event_id. The planner skips resolve and calls execute with event_id: {source: 'known', value: '24'}. The value '24' does NOT appear in the user's task text ('Please add john.doe and maria.garcia to the Introductory meeting on May 5th'). But @policy.build returns valid=true with 0 issues. The known bucket check should reject with known_value_not_in_task_text, or the handle type on event_id should require fact proof. Either the task-text verification isn't running, or the 'allow' bucket is being used, or there's a bug in the known-value matching. This is a structural gap — the proof system should prevent execute without prior resolve, but it's not enforcing. Trace at /tmp/ut8-addendum-verbose.jsonl. Transcript: session quick-falcon, planner passes known:'24' at 13:46:45.

