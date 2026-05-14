---
id: WS-display-shelf-roundtrip
status: open
deps: []
links: []
created: 2026-05-14T18:34:28Z
type: task
priority: 2
assignee: Adam
---
# [WS] Verify role:planner display projection survives shelf write+read post v2.x migration (m-aecd class)

m-aecd shelf round-trip class can re-introduce untrusted on data.trusted fields. Verify role:planner field omission (Class A foundational defense) survives a shelf write+read cycle for @email_msg records. Add tier-2 test asserting planner view of an email post-shelf-roundtrip omits body. §8 Class A, §9 #5.

