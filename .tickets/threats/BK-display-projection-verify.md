---
id: BK-display-projection-verify
status: open
deps: []
links: []
created: 2026-05-14T18:30:31Z
type: task
priority: 2
assignee: Adam
---
# [BK] Verify role:planner display projection strips data.untrusted via shelf-read

Verify role:planner display projection strips data.untrusted content through shelf-read post-v2.x records migration. Records declare role:planner: [{value: file_path}] on @file_text and omit subject on @transaction. From sec-banking.md §8 Class 1.

