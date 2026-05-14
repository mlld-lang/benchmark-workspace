---
id: c-b8e7
status: closed
deps: []
links: []
created: 2026-04-22T11:00:26Z
type: chore
priority: 2
assignee: Adam
tags: [security]
updated: 2026-05-14T18:05:13Z
---
# Consider locked: true on synthesized base policy

orchestration.mld synthesizes the base policy with all default rules (no-send-to-unknown, no-destroy-unknown, etc.) but does not set locked: true. A locked policy cannot be overridden by any guard, privileged or not. For production deployments this would be a stronger guarantee that the core rules are absolute. Evaluate whether locked: true is appropriate for the base policy, or whether specific rules should be selectively locked.


## Notes

**2026-05-14T18:05:13Z** Closed 2026-05-14 (ticket-review pass): Policy redesign provides labels.locked / fragment locking; decide during migration not as a standalone ticket.
