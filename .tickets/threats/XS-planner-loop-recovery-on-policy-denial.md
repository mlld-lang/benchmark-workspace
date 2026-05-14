---
id: XS-planner-loop-recovery-on-policy-denial
status: open
deps: []
links: []
created: 2026-05-14T19:07:48Z
type: task
priority: 2
assignee: Adam
---
# [XS] Verify planner-loop recovery on policy denial (structured surface, not swallowed)

On a structured policy denial (no-influenced-advice in travel, but applies to any future denial-arm policy in any suite), the failure must surface to the planner as actionable feedback rather than being swallowed. Recovery path design-locked in rig/ADVICE_GATE.md §'Final Advice Output' for travel; the framework concern is generic. Verify end-to-end via attack sweep + transcript audit that the planner observes the denial, considers it actionable, and selects fallback rather than silently dropping the iteration. Originally filed as TR-advice-loop-recovery-verify from sec-travel.md §8 Class A; reclassified XS-* because planner-loop-recovery-on-policy-denial is a generic framework concern.

