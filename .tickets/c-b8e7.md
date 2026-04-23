---
id: c-b8e7
status: open
deps: []
links: []
created: 2026-04-22T11:00:26Z
type: chore
priority: 2
assignee: Adam
tags: [security]
---
# Consider locked: true on synthesized base policy

orchestration.mld synthesizes the base policy with all default rules (no-send-to-unknown, no-destroy-unknown, etc.) but does not set locked: true. A locked policy cannot be overridden by any guard, privileged or not. For production deployments this would be a stronger guarantee that the core rules are absolute. Evaluate whether locked: true is appropriate for the base policy, or whether specific rules should be selectively locked.

