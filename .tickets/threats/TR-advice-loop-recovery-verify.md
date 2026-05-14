---
id: TR-advice-loop-recovery-verify
status: closed
deps: []
links: []
created: 2026-05-14T18:34:31Z
type: task
priority: 2
assignee: Adam
updated: 2026-05-14T19:07:48Z
---
# [TR] Verify planner-loop recovery on no-influenced-advice denial (structured surface, not swallowed)

On no-influenced-advice denial, the structured failure must surface to the planner as actionable feedback rather than being swallowed. Recovery path is design-locked in rig/ADVICE_GATE.md §'Final Advice Output'. Verify end-to-end via attack sweep + transcript audit that the planner observes the denial, considers it actionable, and selects @factOnlyAnswer fallback (or surfaces refusal) rather than silently dropping the iteration. From sec-travel.md §8 Class A.


## Notes

**2026-05-14T19:07:48Z** Renamed to XS-planner-loop-recovery-on-policy-denial (generic framework concern, not advice-specific). See new ticket for body.
