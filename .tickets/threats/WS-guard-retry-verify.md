---
id: WS-guard-retry-verify
status: open
deps: []
links: []
created: 2026-05-14T18:34:55Z
type: task
priority: 4
assignee: Adam
---
# [WS] Verify #guard-retry bounded if rig adopts custom guards

If rig adopts custom guards beyond the base policy, verify retry behavior is bounded (no unbounded retry loops on deny). Currently not used in workspace v1.1.1 but tracked as a future hardening item. §8 Class F.

