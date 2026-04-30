---
id: c-a46d
status: closed
deps: []
links: [c-8738, c-be06]
created: 2026-04-27T17:32:50Z
type: chore
priority: 2
assignee: Adam
updated: 2026-04-30T03:33:25Z
tags: [oos-deferred]
---
# OOS-DEFERRED (URL-promotion): SL-UT1 - URL in untrusted message body; same family as SL-UT4 and SL-UT6

**Action**: Add user_task_1 and user_task_4 to src/run.py SKIP_TASKS for the slack suite, with reason: "URLs embedded in untrusted message bodies cannot reach get_webpage as control args without weakening the clean-planner invariant. Same defended-boundary class as SL-UT2/UT11/UT15/UT16/UT17/UT18/UT19/UT20."

**Justification**: SL-UT1 (Bob's article URL in his message body) and SL-UT4 (Eve's hobby URL in her message body) are both blocked by the same architectural invariant. UT4 has been on c-8738's roster with a slack addendum that didn't take. The cleanest action is to align with the established OOS family.

**Alternative**: implement a structural URL-promotion mechanism (a tool that materializes URLs from message bodies into webpage_content records by safe extraction). This is a non-trivial rig primitive, deferred unless a future session decides URLs-in-bodies should become in-scope.

**Linked failure tickets**: c-8738 (SL-UT1, SL-UT4, SL-UT6 — note SL-UT6 also has the c-4a08 regression but the URL fetch part is the same OOS class).

