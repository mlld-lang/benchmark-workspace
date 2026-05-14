---
id: XS-fetched-content-as-task-defense
status: open
deps: []
links: []
created: 2026-05-14T18:34:16Z
type: task
priority: 3
assignee: Adam
---
# [XS] Tier-2 defense for fetched-content-as-task (TODO/instruction-channel pattern)

Cross-suite design question: slack UT18/UT19 fetch a URL (`www.company-todo-list.com/*`) whose body is interpreted as further task text. The TODO URL is itself task-text-grounded so `get_webpage` doesn't refuse, but an attacker-controlled TODO body would direct downstream sub-tasks. Pattern is structurally similar to workspace UT13/UT19 typed-instruction-channel risk. Decision: should rig add a tier-2 defense for 'fetched-content-as-task' patterns, or treat TODO content the same as any other untrusted webpage (workers extract, planner doesn't see)? From sec-slack.md §9 question 8.

