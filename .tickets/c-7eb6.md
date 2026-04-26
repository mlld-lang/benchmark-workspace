---
id: c-7eb6
status: open
deps: []
links: []
created: 2026-04-26T17:06:30Z
type: chore
priority: 3
assignee: Adam
tags: [c-3438, b-detector, revisit]
---
# Revisit (B) no-progress detector — never fired across sweeps; remove if still unused after handoff

The (B) progress_warning detector (c-3438) was designed to nudge the planner toward blocked() when state isn't advancing. Across 4+ sweeps with the detector wired and exported correctly:

- Threshold 6: 0 instances fired
- Threshold 3: 0 instances fired

Reason: with parallel resolve_batch + mlld cancellation + cascade dead, every planner call now advances state. The "no progress loop" the warning was designed for doesn't manifest empirically. Originally we expected it to surface UT10-style empty-derive flailing, but the planner has been pivoting cleanly without the nudge.

**Code surface kept anyway:**
- @stateProgressFingerprint (rig/workers/planner.mld) + 8 invariant tests
- @plannerNoProgressThreshold + planner.att rule
- progress_warning field threaded through 5 phase result shapes
- @plannerRuntime schema fields + round-trip test (PR-1)

**Argument FOR keeping:** generic protection against future flailing patterns we haven't seen yet. Not suite-specific — applies to any rig agent. Cheap to keep (no overhead, no false positives).

**Argument FOR removing:** dead code that confused (B) wasn't firing during debugging. Schema fields persisted across writes (overhead). The fingerprint is cheap but adds complexity to read.

**Decision criteria:** if after 2+ months and 10+ sweeps the warning still hasn't fired in production, remove. If it ever fires (planner emits flailing pattern in some new task class), keep and tune threshold.

**Triggers to revisit:**
- Any sweep where progress_warning fires (sqlite check: `SELECT COUNT(*) FROM part WHERE json_extract(data, '$.state.output') LIKE '%NO PROGRESS%'`)
- New task patterns that flail in ways we predict (B) would catch
- Major rig refactor that touches @plannerRuntime schema or @settlePhaseDispatch

