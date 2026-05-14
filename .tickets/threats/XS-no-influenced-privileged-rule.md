---
id: XS-no-influenced-privileged-rule
status: open
deps: []
links: []
created: 2026-05-14T18:30:32Z
type: task
priority: 2
assignee: Adam
---
# [XS] Add no-influenced-privileged policy rule (generalize across suites)

Open question: add a no-influenced-privileged rule blocking influenced data from privileged:* operations, analogous to no-untrusted-privileged. Currently banking @update_password_inputs absent-write-block carries this load via hard-deny. Would generalize across suites. From sec-banking.md §8 Class 4 + §9 question 2.

