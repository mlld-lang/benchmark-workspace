---
id: BK-validate-strict-verify
status: open
deps: []
links: []
created: 2026-05-14T18:30:32Z
type: task
priority: 2
assignee: Adam
---
# [BK] Verify validate:strict enforcement on all banking input records

Verify validate: "strict" rejects unknown fields and type mismatches at dispatch boundary for all banking write input records (send_money, schedule_transaction, update_scheduled_transaction, update_user_info, update_password). From sec-banking.md §4 + §8 Class 1.

