---
id: WS-delete-email-deny
status: open
deps: []
links: []
created: 2026-05-14T18:34:41Z
type: task
priority: 2
assignee: Adam
---
# [WS] Add delete_email to @authorizations.deny for all scopes (no legitimate UT carrier)

No workspace UT requests email deletion; only IT5 exercises delete_email as cover-up. Adding delete_email to deny lists across all scopes would foreclose the cover-up chain at the policy layer rather than relying on task-text validation. Defense-in-depth / architectural posture. §8 Class C+F, §9 #4.

