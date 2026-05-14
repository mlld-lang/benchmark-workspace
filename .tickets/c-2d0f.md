---
id: c-2d0f
status: closed
deps: []
links: []
created: 2026-05-04T21:14:18Z
type: feature
priority: 2
assignee: Adam
tags: [ci, bench, wall-time, batching]
updated: 2026-05-14T18:05:13Z
---
# Cloud bench: split SHOULD-FAIL/OOS-grind tasks into separate runner group

Slack/workspace/travel cloud sweeps are wall-time-dominated by
SHOULD-FAIL and OOS-EXHAUSTED tasks that grind to ~700-900s before
timeout (because of c-5ef9 / c-3438 — structurally_infeasible
detection too strict). PASSING tasks finish well under those numbers.

Effect on critical-path wall time per latest sweep (post-820f0d9):

| Suite     | Wall  | Wall ex-grinders | Δ      |
|---        |---    |---              |---     |
| slack     | 932s  | ~560s (UT6 max) | -40%   |
| workspace | 989s  | ~570s (UT33)    | -42%   |
| travel    | 1002s | ~580s (UT6)     | -42%   |
| banking   | 328s  | ~230s           | -30%   |

Two complementary strategies:

1. (long-term) Fix c-5ef9 — structurally_infeasible tracker fires
   on N/A-selection cases. SHOULD-FAIL exits fast via blocked().
   Eliminates the wall problem at root.

2. (short-term) Operational batching — dedicate one cloud runner
   to the SHOULD-FAIL/OOS-grind set; run other tasks in their
   own group. Critical-path wall time improves regardless of (1)
   landing.

This ticket covers (2). Concrete shape:

  scripts/bench.sh produces two dispatch sets per suite:
  - "fast" — tasks expected to PASS or fail-fast (most of each suite)
  - "grind" — tasks documented as SHOULD-FAIL/OOS that currently
    grind to timeout

  bench-run.yml accepts the existing 'tasks' input (already there).
  scripts/bench.sh splits via the documented OOS lists per CLAUDE.md
  scripts/bench.sh comments + the SHOULD-FAIL ticket index.

  Documented OOS/SHOULD-FAIL inventories per suite (current):
  - banking grind: UT0, UT9, UT10, UT14, UT15
  - slack grind: UT2, UT11, UT14, UT16, UT17, UT18, UT19, UT20
  - workspace grind: UT13, UT18, UT19, UT25, UT31, UT33
  - travel grind: UT0 (stochastic), UT11 (linguistic), UT16 (c-57a6),
    UT17 (c-7fb9), UT19 (c-55dd, c-e562)

  These can be authoritatively read from a single source-of-truth
  file rather than duplicated in scripts/bench.sh. Proposed:
  bench/grind-tasks.json (or similar) — one place to update when
  classification changes.

Related to c-5ef9, c-3438. Should defer until those land OR ship
ahead of them as an operational mitigation while c-5ef9 is in design.


## Notes

**2026-05-14T18:05:13Z** Closed 2026-05-14 (ticket-review pass): Operational workaround for c-5ef9 / c-3438; keep the root fix instead.
