---
id: SL-add-user-exfil-label
status: open
deps: []
links: []
created: 2026-05-14T18:33:56Z
type: task
priority: 3
assignee: Adam
---
# [SL] Should add_user_to_channel carry exfil:send for defense-in-depth?

Open question: `add_user_to_channel` currently labels execute:w, tool:w, membership:w — no exfil:send. The 'add a recipient to a destination' semantics are operationally send-like. Without exfil:send, `@noUntrustedUrlsInOutput` guard and `labels.influenced.deny` rules don't fire as defense-in-depth (currently #handles alone carries). Decision: re-label and re-audit, or accept #handles load? From sec-slack.md §8 Class C + §9 question 1.

