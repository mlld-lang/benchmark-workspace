---
id: SL-known-bucket-task-text
status: closed
deps: []
links: [BK-known-kind-floor-verify, WS-known-kind-floor-verify]
created: 2026-05-14T18:33:48Z
type: task
priority: 1
assignee: Adam
updated: 2026-05-14T23:07:27Z
---
# [SL] known bucket requires verbatim user-task-text match, not env-key match

Verification target: post-records-as-policy migration, confirm `known` source class restricts to user task PROMPT text, not arbitrary environment fixture keys (e.g., IT3's `www.true-informations.com` exists in `web.web_content` keys but appears in NO user task prompt and must NOT pass the `known` bucket). From sec-slack.md §8 Class A + §9 question 4.


## Notes

**2026-05-14T19:07:48Z** Conceptually verifies the same BasePolicy primitive as BK-known-kind-floor-verify and WS-known-kind-floor-verify. Implementation is BasePolicy-level (single code path); verification cost is per-suite (each suite's sweep must observe the floor firing on its own ITs). Linked to siblings for cross-reference.
