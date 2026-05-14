---
id: XS-locked-policy-rigwide
status: open
deps: []
links: []
created: 2026-05-14T19:07:48Z
type: task
priority: 4
assignee: Adam
---
# [XS] Decide locked: true policy posture for production deployments (rig-wide)

rig's synthesized policy is not currently locked: true. For production deployments (not AgentDojo benchmark) this could be tightened to foreclose any runtime policy mutation. Decide: when does locked-policy land — pre-2026.06 production review, or deferred. Originally filed as WS-locked-policy from sec-workspace.md §8 Class F + §9 #7; reclassified XS-* because the fix is rig-side, not workspace-specific. Applies to any agent built on rig.

