---
id: TR-body-content-pii-scan
status: open
deps: []
links: []
created: 2026-05-14T18:34:43Z
type: task
priority: 3
assignee: Adam
---
# [TR] Defense-in-depth: scan send_email.body for PII patterns

Defense-in-depth value-side check that send_email.body doesn't contain passport-like regex / credit-card-like patterns / bank-account-like patterns before dispatch. Not currently wired. IT5's collision (legitimate recipient janeLong@google.com from UT3 plus PII body content) means recipient grounding cannot distinguish IT5 from legitimate send by recipient identity alone; PII display omission carries independent load. Open whether body-content scanning is worth adding given display-omission already holds. Cross-suite consideration: similar pattern could apply to slack send_direct_message / banking send_money subject. From sec-travel.md §8 Class D + §9 question.

