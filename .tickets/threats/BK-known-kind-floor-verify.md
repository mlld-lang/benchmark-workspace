---
id: BK-known-kind-floor-verify
status: closed
deps: []
links: [SL-known-bucket-task-text, WS-known-kind-floor-verify]
created: 2026-05-14T18:30:31Z
type: task
priority: 2
assignee: Adam
updated: 2026-05-14T22:59:59Z
---
# [BK] Verify known source class enforces kind: floor

Verify known source class enforces kind: floor in v2.x grammar. Closes random-string laundering attempt where attacker IBAN reaches known bucket without kind validation. From sec-banking.md §8 Class 1.


## Notes

**2026-05-14T19:07:48Z** Conceptually verifies the same BasePolicy primitive as SL-known-bucket-task-text and WS-known-kind-floor-verify. Implementation is BasePolicy-level (single code path); verification cost is per-suite (each suite's sweep must observe the floor firing on its own ITs). Linked to siblings for cross-reference.
