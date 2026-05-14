---
id: SL-IT-5-authorizations-deny-remove
status: open
deps: []
links: []
created: 2026-05-14T18:34:01Z
type: task
priority: 2
assignee: Adam
---
# [SL-IT-5] Add remove_user_from_slack to authorizations.deny for user-facing scopes

Decision target: no UT in v1 or v1.1.1 exercises `remove_user_from_slack` — it appears only in IT5's ground truth. Adding it to `authorizations.deny` for user-facing scopes would close the destructive half of IT5 without affecting any legitimate task. Decision: blanket deny vs. keep tool authorizable in case future tasks need it? From sec-slack.md §8 Class C + §9 question 2.

