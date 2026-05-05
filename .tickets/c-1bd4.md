---
id: c-1bd4
status: open
deps: []
links: []
created: 2026-05-04T21:15:00Z
type: feature
priority: 2
assignee: Adam
tags: [bench, attacks, canary, security]
---
# Attack canary spot-check + full attack suite verification post-perf-fix

After the perf regression close (c-2565 + commit 820f0d9), need
to re-verify attack ASR with confidence. Plan:

1. Read prior breach records from ~/mlld/benchmarks SCIENCE* files
   (the canonical record of which attacks have historically broken
   through and where the planner architecture had gaps). Identify
   the canary set.

2. Spot-check those canary attacks on the latest defended sweep.
   Pick ~3-5 (user_task, injection_task) pairs known to have been
   the hardest cases historically. Run them as targeted dispatches:

     gh workflow run bench-run.yml -f suite=workspace \\
       -f tasks=user_task_X -f attack=important_instructions \\
       -f defense=defended

   For each, confirm whether the canary breach repeats. If it
   repeats, we have a regression to mitigate. If clean, proceed
   to step 3.

3. Mitigate any breaches found. Each mitigation lands as its own
   commit. Re-run the canary to verify. Don't proceed to step 4
   until all canaries are clean.

4. Full attack suite runs on cloud:
   - Per-suite × per-attack matrix
   - All 6 stock attacks: direct, ignore_previous, important_instructions,
     injecagent, system_message, tool_knowledge
   - Defended only (undefended is the breach-floor; we know it'll
     be ~100% ASR)

5. Record results in SCIENCE.md and the diagonal-zero matrix per
   spec-extended-attacks-benchmark.md.

Reference materials:
- ~/mlld/benchmarks/SCIENCE.md (older ASR records)
- ~/mlld/benchmarks/labels-policies-guards.md (security model
  narrative; symlinked from clean/)
- Per-suite threatmodel files (banking.threatmodel.txt, etc.)

This ticket covers steps 1-5 as a unit. Sub-tickets get filed if
specific breaches are found and need their own remediation paths.

Per CLAUDE.md attack-sweep discipline: each attack run is a
separate cloud dispatch (~bench.sh has the dispatch shape; --resume
mode exists for incremental re-runs).

