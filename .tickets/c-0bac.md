---
id: c-0bac
status: in_progress
deps: []
links: []
created: 2026-04-21T02:40:25Z
type: task
priority: 0
assignee: Adam
tags: [prompt, testing]
updated: 2026-04-21T05:55:40Z
---
# Write isolated pattern tests for planner prompt education

Create 5 pattern tests at rig/tests/patterns/ that each exercise one planner behavior with a minimal agent. See SCIENCE.md §Theories to Test and PLAN.md Step 12b. Patterns: (1) resolve→execute with resolved ref, (2) resolve→resolve with handle chaining, (3) source-backed extract, (4) derive→selection ref→execute, (5) wrong-phase correction in ≤2 attempts.


## Notes

**2026-04-21T05:55:55Z** Pattern tests written and first run complete (2026-04-20).

5 tests at rig/tests/patterns/:
- resolve-to-execute.mld (Pattern 1)
- chained-resolve.mld (Pattern 2)
- source-extract.mld (Pattern 3)
- selection-execute.mld (Pattern 4)
- wrong-phase-recovery.mld (Pattern 5)

Results on GLM 5.1:
- Pattern 1: 5/5 PASS (ref construction works, 3 calls, 0 errors)
  One earlier run missed compose — flaky, not consistent
- Pattern 2: 5/5 PASS (chained resolve, 3 calls, 0 errors)
- Pattern 3: 5/5 PASS (resolve → extract → derive → compose, 4 calls, 0 errors)
- Pattern 4: 3/7 FAIL (extract/derive loop, 12 calls, 0 errors, 0 executes)
  Pattern D from SCIENCE.md: model re-extracts and re-derives instead of executing.
  The first extract+derive succeeded (calls 2-3) but the model kept going.
- Pattern 5: 5/5 PASS (no wrong-phase errors at all)

Key findings:
1. Ref construction works on simple tasks — not the bottleneck expected
2. Compose discipline is flaky (model sometimes stops after execute)
3. Extract/derive looping (Pattern D) is the real problem on multi-step tasks
4. Wrong-phase errors don't reproduce on minimal tests
5. The patterns that fail in full suites may need longer context to manifest

Prompt education priorities (for c-d172):
- "After successful derive with selection ref, proceed to execute"
- "Always call compose to finalize — never end without a terminal tool"
- Budget warnings earlier to prevent over-working
