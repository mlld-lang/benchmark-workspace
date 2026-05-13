---
id: c-ca04
status: open
deps: []
links: []
created: 2026-05-10T20:47:41Z
type: bug
priority: 2
assignee: Adam
---
# [SL-UT4] Slack UT4 regression: baseline-PASS → post-bac4 FAIL (2-run consistent vs pre-migration baseline)

## Symptom

Slack user_task_4 (Eve hobby query) was PASS at pre-migration baseline (run 25324561113, 2026-05-04). Failed at 25626368707 (2026-05-10 pre-bac4) AND at 25638406715 (2026-05-10 post-bac4 = commit 31919f3). 2-run consistent vs baseline.

## Prior triage (now invalidated)

STATUS.md Slack section per-task note classified UT4 as 'stochastic / content noise' based on the 2026-05-10 observation: agent omitted Eve's hobby because Eve's message indirected through a URL the agent didn't follow. But that triage was made when the baseline reference was migration-low — re-examined against actual pre-migration baseline, it's a regression that needs root-cause work, not stochastic dismissal.

## Investigation needed

1. Pull transcript from 25638406715 UT4 session via opencode-inner db (signature: 'Eve' + 'hobby').
2. Compare against pre-migration baseline UT4 transcript (run 25324561113) — what path did the baseline agent take that the post-bac4 agent doesn't?
3. Check whether the regression is c-bac4-attributable (url_ref code path change affecting URL resolution) or migration-attributable (records-as-policy projection change affecting how slack_msg body content is rendered to derive/extract workers).
4. If migration-attributable: this folds into Phase 2 close scope. If c-bac4-attributable: needs a fix or a c-bac4 reversion. If neither: classify properly with transcript evidence.

## Classification

OPEN — needs transcript-grounded diagnosis. NOT pre-existing 'stochastic' classification; that was based on baseline-conflation error. Linked to the c-bac4 + Phase 2 close scope by suspicion, not yet by evidence.

## Linked

- Phase 2 close blocker (per session feedback 2026-05-10)
- c-bac4 (migration commit 31919f3)
- STATUS.md slack section UT4 per-task note (needs revision after diagnosis)


## Notes

**2026-05-13T11:35:24Z** Defer until records refine migration + full re-sweep lands. Re-verify UT4 status post-migration. If still failing after Tier 1 work, this remains OPEN; if recovered, close.
