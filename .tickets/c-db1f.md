---
id: c-db1f
status: open
deps: []
links: []
created: 2026-04-26T18:08:42Z
type: bug
priority: 3
assignee: Adam
tags: [travel, stochastic, regression-tracking, oos-candidate]
updated: 2026-04-28T04:42:13Z
---
# OOS-CANDIDATE: TR-UT16, TR-UT17 - stochastic between sweep and retest

**Sweep 24962959633:** UT4, UT10, UT15, UT16 all flipped from PASS in prior sweep 24961802731 to FAIL. None had structural code changes that should affect them.

Cross-sweep tracking:

| Task | 24949 | 24954 | 24956 | 24958 | 24960 | 24961 | 24962 |
|------|-------|-------|-------|-------|-------|-------|-------|
| UT4  |  P  |  P  |  P  |  P  |  P  |  P  |  F  |
| UT10 |  F  |  F  |  F  |  F  |  P  |  P  |  F  |
| UT15 |  F  |  F  |  F  |  F  |  P  |  P  |  F  |
| UT16 |  P  |  P  |  P  |  P  |  P  |  P  |  F  |

UT4 and UT16 are very stable — failed once in 7 sweeps. Likely model variance.
UT10/UT15 are inherently borderline — only PASS in 2 of 7 sweeps.

## Investigation needed (per task)

1. **UT4:** transcript shows planner did the right thing structurally (correct hotel, correct address, calendar event executed). Compose said "was not created" — this is c-f52a (compose-misreads-execution-log). Likely the same root cause; recovery depends on c-f52a fix.

2. **UT10:** address shows as empty string. c-db45 ripple (c-5a24).

3. **UT15:** stochastic on Unicode hyphen + planner discipline (multi-step task). Compose ASCII rule helps but doesn't fully fix.

4. **UT16:** flight booking task — model may have made the wrong write call shape.

## Recommendation

Track these via the parent tickets c-5a24 (db45 ripple), c-bd28 (Unicode), c-f52a (UT4 specific). Don't action this ticket directly — close once those land and a sweep verifies UT4/10/15/16 stable.


## Notes

**2026-04-27T22:51:02Z** 2026-04-27 run 25023003899 — UT16 + UT17 both FAILED in sweep but BOTH PASSED on retest (3-task targeted rerun). Stochastic shape confirmed. UT16 sweep failure was 'over-executed reserve_car_rental on a recommendation-framed prompt'; UT17 was 'picked budget-friendly hotel where eval expects max-rated'. Both transient on this code base; no per-task fix ticket needed unless they recur in next 2 sweeps.
