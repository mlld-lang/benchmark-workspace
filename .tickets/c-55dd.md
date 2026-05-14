---
id: c-55dd
status: closed
deps: []
links: [c-e562, c-63fe]
created: 2026-05-01T17:23:20Z
type: bug
priority: 2
assignee: Adam
tags: [travel, framework, mcp-timeout, resolve-batch]
updated: 2026-05-14T18:05:13Z
---
# [TR-UT19, framework] resolve_batch hits 5-min MCP timeout on large multi-domain batches

Filed bench-grind-15 from transcript-grounded analysis of run 25222265101 (travel session ses_21ba84eacffeM5b3GoD6DZt21B).

Failure: UT19 second resolve_batch returned 'MCP error -32001: Request timed out' after 5 minutes. Planner had asked for ratings + prices for ~12 entities across 6 tools × 2 cities (London + Paris).

Root cause: opencode mcp_timeout is 300000ms (5 min), set in ~/mlld/mlld/llm/lib/opencode/index.mld:279. resolve_batch internally does:
- Phase A: 'for parallel(8)' dispatch — fine
- Phase B: sequential merge loop over all dispatched specs (c-63fe optimized this once but still O(n))

For 12+ specs the merge phase plus dispatch wall hit the 5-min ceiling.

Fix candidates (in order of effort):
1. Bump mcp_timeout from 300000 → 600000 in opencode config. Cheap. UT19's batch fits. Doesn't help if planner sends 24+ specs but covers the realistic case.
2. Further optimize merge loop (e.g., pre-allocate, skip redundant projection work).
3. Stream partial results — resolve_batch returns progress notifications via MCP streaming, planner sees what's done and can continue. Architectural change.

Workaround in addendum (overfitting): tell planner to chunk into ≤6 sub-resolves per batch.

Recommendation: start with #1. The 5-min ceiling is arbitrary — opencode default. Bumping doesn't compromise security. Verify by re-running UT19 with the bumped value.

Linked to c-e562 (TR-UT19 stochastic class) which now points here.


## Notes

**2026-05-01T17:42:36Z** 2026-05-01 local repro reveals deeper issue, retracts the "just bump mcp_timeout" recommendation:

Local TR-UT19 single-task run (MLLD_HEAP=8g, no concurrent jobs, fresh process):
- 1st resolve_batch (6 entity-grounding sub-resolves): all 6 succeeded in <1ms each, ~5s total wall.
- 2nd resolve_batch (metadata: ratings + prices for 12+ entities): immediately returned **"Not connected"** — MCP server disconnect/crash, NOT a timeout.
- planner walled at 900s with compose_reached=false.

This is the c-63fe failure mode (MCP server crashes mid-call), supposedly closed by memory cuts + parallel(8) + heap=8g. Symptom is back on the second large resolve_batch.

Reframing: the remote run's "MCP error -32001: Request timed out" likely means the MCP proxy gave up waiting for a response that never came because the server had already crashed — same root cause, different symptom because of how the proxy reports the wait timeout vs the disconnect.

User instinct was right: 5-min is a long timeout, unlikely to be the limiting factor. The actual ceiling is the MCP server stability under the second metadata-heavy resolve_batch.

Hypothesis: the second batch's payload size (ratings + price ranges + reviews for 12+ entities) crosses some memory or buffer threshold the MCP proxy or server can't handle, causing a disconnect. The first batch (entity names only) is small enough to succeed.

Reopening c-63fe is warranted — symptom reproduces on local single-task. Don't bump mcp_timeout; investigate the actual disconnect.

Reproduction: tmp/ut19-local/run.log (defended.142.jsonl) — local Mac, 48GB RAM, fresh process, MLLD_HEAP=8g, single task.

**2026-05-14T18:05:13Z** Closed 2026-05-14 (ticket-review pass): Duplicate of the active c-63fe MCP/memory/resolve-batch umbrella.
