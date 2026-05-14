---
id: BK-iban-positive-check-verify
status: open
deps: []
links: []
created: 2026-05-14T18:30:31Z
type: task
priority: 2
assignee: Adam
---
# [BK] Verify BasePolicy positive check on iban kind

Verify BasePolicy positive check on iban kind matches structured-trust descriptor in v2.x. Recipient arg must carry fact:iban label; influenced/extracted scalars cannot satisfy. From sec-banking.md §8 Class 1.

