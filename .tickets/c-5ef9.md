---
id: c-5ef9
status: open
deps: []
links: [c-3438, c-3c2b]
created: 2026-05-04T17:44:28Z
type: bug
priority: 2
assignee: Adam
tags: [rig, planner, rehearse, wall-time, slack, workspace]
updated: 2026-05-05T03:13:32Z
---
# structurally_infeasible tracker doesn't fire when 'selection' is N/A

The rehearse + structurally_infeasible mechanism (commit 9d4ec43) is
designed to make SHOULD-FAIL tasks exit fast via blocked() once the
planner has tried all legal control-arg source classes. In practice
it doesn't fire when one of the three classes (selection) doesn't
apply to the task.

Spec (commit 9d4ec43): "After all three legal control-arg source
classes (resolved, known, selection) have been tried for the same
arg with failures, the framework deterministically tags the next
rehearse as structurally_infeasible."

Failure mode: many SHOULD-FAIL tasks have no resolved-set with
multiple instances to select among. A task asking to invite Dora
has only Dora as the target — there is no selection-set to draw
from. The planner correctly tries known and resolved (both fail)
plus extracted and derived (both rejected as illegal sources for
control args), but never tries selection because there is nothing
to select among. The tracker waits for selection to be tried; it
never is; structurally_infeasible stays false; the planner pivots
to alternative shapes and grinds to timeout.

Decisive transcript: slack UT16 in run 25324561113, session
ses_20c943950ffexsNtZ7Y5xrzHgZ. Six rehearse calls, planner reasoning
explicitly enumerates "I've tried known, derived, extracted, resolved
— all blocked." Framework reports structurally_infeasible: false on
all of them. Planner pivots to Eve's DM, executes that, runs out of
budget mid-execute, task times out at 900s.

Effect on bench wall time:
  - slack 932s wall is dominated by 4 tasks at 679-900s each (UT16,
    UT17, UT2, UT14). Three of those are SHOULD-FAIL with the
    no-selection-set shape. UT14 is OOS-EXHAUSTED (eval mismatch).
  - workspace 989s similarly has UT13 776s + UT19 608s, both
    SHOULD-FAIL typed-instruction-channel that grind through alt
    shapes.
  - Fixing the tracker would let these tasks fail in 30-60s.
    Slack wall would drop to ~560s (where the slowest PASSING
    task lives). Workspace wall would drop to ~570s.

Two candidate fixes:

1. **Tracker change.** Loosen the exhaustion criterion. Track per-arg:
   - tried_with_candidates (e.g. tried 'selection' against an actual
     candidate set)
   - tried_with_no_candidates (e.g. tried 'selection' but candidate
     set was empty / N/A)
   Both count toward exhaustion. Plus the existing 'tried_resolved'
   and 'tried_known' tracks.

   This is structural and reliable. Requires understanding the
   selection candidate-set semantics in the rehearse compiler.

2. **Prompt strengthening.** Add to planner.att: "If you have
   tried 'resolved' and 'known' for a control arg AND no resolved
   collection exists with multiple instances to select among,
   that counts as exhaustion — call blocked() immediately."

   Probabilistic. Less reliable. Faster to land.

Recommendation: do both. (1) for correctness, (2) as an interim
guardrail that buys time while (1) is designed.

Linked tickets:
  - c-2565 (workspace cascade) closed by lifecycle no-op fix; this
    issue is the next-tier perf cleanup
  - SHOULD-FAIL slack tickets (c-1d4b, c-5755, c-4814, c-1487,
    c-9cd0) all have the same shape — they're the population this
    fix would speed up

Per CLAUDE.md prompt-approval rule: any planner.att edit (option 2)
needs explicit user approval before being written.


## Notes

**2026-05-04T22:38:38Z** 2026-05-04: Patch landed at rig/workers/planner.mld:883-905 (commit pending). New rule: tried.size >= 3 AND tried_resolved AND tried_known. Validated by zero-LLM spike at tmp/c-5ef9-spike/probe.mld and 8 invariant tests at rig/tests/index.mld (c-5ef9/EX-1..EX-8 all PASS). Total invariant gate 200/201 (1 expected xfail). End-to-end verification against single-task SL-UT16 was inconclusive — that local run took the resolve-loop path (0 rehearse calls in 23 MCP calls) instead of the rehearse-loop path the fix targets. Same task in cloud sweep 25324561113 had 6 rehearses + 21 MCP calls — that's the shape this fix addresses. Switching verification to SL-UT2 which had 30 phase_events with only 2 MCP calls indicating heavy rehearse activity before reaching blocked.
