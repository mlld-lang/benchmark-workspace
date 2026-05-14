---
id: WS-known-kind-floor-verify
status: open
deps: []
links: [BK-known-kind-floor-verify, SL-known-bucket-task-text]
created: 2026-05-14T18:34:52Z
type: task
priority: 1
assignee: Adam
updated: 2026-05-14T19:07:48Z
---
# [WS] Verify known source class enforces kind: floor in new grammar (shared with banking)

Verify the known source class enforces kind: annotations (kind:email for workspace recipients/participants) in the new grammar. Closes arbitrary-string laundering: known scalars must still satisfy kind. Shared concern with BK-known-kind-floor-verify; verifying both per-suite. §8 Class B.


## Notes

**2026-05-14T19:07:48Z** Conceptually verifies the same BasePolicy primitive as BK-known-kind-floor-verify and SL-known-bucket-task-text. Implementation is BasePolicy-level (single code path); verification cost is per-suite (each suite's sweep must observe the floor firing on its own ITs). Linked to siblings for cross-reference.
