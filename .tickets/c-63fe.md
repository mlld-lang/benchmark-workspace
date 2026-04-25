---
id: c-63fe
status: open
deps: []
links: []
created: 2026-04-25T04:45:37Z
type: bug
priority: 1
assignee: Adam
tags: [infrastructure, mcp]
---
# MCP server disconnects mid-run on remote bench runners (travel + workspace-b)

Symptom: travel run 24921398132 has 177 MCP tool errors (152 'Not connected', 13 'Request timed out', 12 'Connection closed') across multiple sessions. workspace-b run 24921396588 has 76 similar errors. Slack and banking runs on the same dispatch had 0 MCP infrastructure errors.

Concrete evidence: opencode.db part data for prt_dc2dcf3a3001go9QnbLx3ngREB shows 'state.error': 'Not connected' from the very first tool call of travel UT2. Subsequent retries hit the same error.

Why it matters: causes the planner to look like it's stuck in resolve loops (Pattern C compact symptom) when actually the MCP server has died and every tool call is failing infrastructure-level. Travel's apparent 6/20 utility is unmeasurable — the actual model/framework behavior is hidden behind these failures.

opencode_debug.py masks the issue: it renders the tool error as 'output=null' which looked like 'no error message propagated' (a different framework bug). The real error is in the part state.error field. Should fix opencode_debug.py to surface state.error when status=error.

Possible causes:
- MCP server (uv run python3 src/mcp_server.py) crashes or times out on long-running tasks. Travel tasks have higher per-task tool counts and longer wall times.
- Per-task MCP timeout setting too short. The session resets at some point and the planner can't reconnect.
- Container-level resource issue (memory, file descriptors, ephemeral ports) under high parallelism (-p 40).
- Possibly correlates with travel's larger tool catalog (28 tools) creating more MCP load.

Investigation:
1. Check src/mcp_server.py for crash conditions / timeout configs
2. Inspect docker container resources during travel run
3. Look for patterns: do disconnects cluster around specific tools, specific iter counts, specific wall times?
4. Reproduce locally with travel suite at -p 5 to see if it's environment-specific

Workaround until fixed: travel results from remote 40-parallel runs are unreliable. Use lower parallelism or local single-task verification for travel debugging until MCP stability lands. Slack and banking remote runs are clean.

Run IDs affected: 24921398132 (travel), 24921396588 (workspace-b).


## OOM linkage (2026-04-25)

User confirms the run hit OOMs in the test infra, likely related to MCP.
That fits the data perfectly:

- Travel has 28 tools (largest surface) and multi-step tasks with many
  tool calls per session — highest MCP memory load.
- Workspace-b is also long-running with file/email tasks.
- Banking and slack are smaller surfaces / shorter sessions and
  finished before MCP saturated.

Hypothesis: src/mcp_server.py (uv run python3 ...) accumulates state
across tasks within a single runner, gets OOM-killed by the container,
and all subsequent in-flight tool calls report "Not connected".
The 152 'Not connected' + 13 timeouts + 12 'Connection closed' is the
characteristic shape of "child process died" — the parent (mlld
runtime) keeps trying, gets immediate disconnects.

Investigation paths:
1. Check src/mcp_server.py for per-task state accumulation that doesn't
   reset between tasks (suite env, response cache, log buffers)
2. Confirm the container memory limit and observe peak RSS during
   travel runs — current Team-plan 8x16 might be too tight when
   running -p 40 with 28 tools per task
3. Add a watchdog log line in mcp_server.py to flag when memory crosses
   a threshold; correlate with disconnect events
4. As workaround: drop travel -p back from 40 to a lower number for
   the next sweep (e.g. -p 10) — fewer concurrent MCP tool calls,
   lower memory, less likely to OOM

This is the same shape as the prior MLLD_HEAP_TRACE / m-60ed work in
mlld where child environments accumulated. Worth checking if there's
a similar leak in the mcp_server bridge.

## Update (2026-04-25): per-task lifecycle, not infrastructure capacity

Tested four shape/parallelism combinations on travel; MCP infra errors
remain ~100+ per run regardless:

| Run | Shape | Parallelism | Outcome | MCP errors |
|-----|-------|-------------|---------|------------|
| 24921398132 | 8x16 | -p 40 | success (2/20) | 177 |
| 24922900959 | 8x16 | -p 40 | OOM-kill exit 137 | — |
| 24923046920 | 16x32 | -p 40 | OOM-kill exit 137 | — |
| 24923172871 | 16x32 | -p 10 | success (2/20) | 102 |
| 24923761759 | 32x64 | -p 20 | success (2/20) | 125 |

OOMs at the runner level resolve with bigger shape + lower parallelism,
but the MCP "Not connected" / "Request timed out" / "Connection closed"
cascade persists in every successful run. Two passes per run, but
which two is flaky — UT0 always; second pass shifts (UT4, UT5, UT7,
UT14, UT15, UT16 across runs).

**The MCP server is dying at the per-task / per-session level, not at
the runner level.** Bigger shape doesn't help because the bottleneck
isn't aggregate memory pressure — it's the MCP server process for an
individual travel session crashing mid-task. Once that one MCP dies,
the planner's session sees ~100 cascading "Not connected" errors as
it keeps trying to call tools.

Travel's per-task properties that are different from banking/slack/
workspace:
- 28 tools in catalog (vs. 10-15 elsewhere)
- Multi-step family→metadata→derive chains take longer per task
- More parallel `read` calls per task (resolve_batch on metadata tools)

Hypotheses for the per-task lifecycle issue (none verified):
1. **MCP server memory leak per session.** Long travel sessions
   accumulate state in the python MCP process (response cache,
   AgentDojo env diff, log buffers) until it OOMs at the process
   level (not container-level — survives runner cap).
2. **Stdio pipe buffer overflow.** mlld talks to the MCP server via
   stdio. Travel sessions emit larger / more frequent tool results
   (record-coerced lists of 5-10 hotels with metadata). If pipe
   buffers fill faster than mlld drains, the MCP server's writes
   eventually block / time out.
3. **AgentDojo env-diff state growth.** The MCP server stores per-task
   env mutations to feed the evaluator at task end. Travel tasks may
   touch more env state than other suites, growing the diff blob.

**Workaround until root cause is fixed:** travel runs locally per the
hybrid pattern in CLAUDE.md. Local mlld doesn't show the MCP cascade
(MCP server is the same code, but local file-system + smaller worker
counts are better-behaved than the container under -p 10+).

**Next investigation steps for whoever picks this up:**
1. Add `MLLD_HEAP_TRACE` to mcp_server.py and log peak RSS at task
   end. Compare across travel UT2 (long) vs UT0 (short) to confirm
   per-session growth.
2. Check src/mcp_server.py for caches / closures that don't reset
   between tasks within a runner.
3. Add a watchdog in mcp_server.py that emits a structured error
   before SIGKILL so the planner sees something more informative
   than "Not connected".
4. Consider running each MCP tool dispatch as a fresh subprocess
   instead of long-lived stdio (heavyweight but isolates failures
   per-call).

## Notes

**2026-04-25T17:19:11Z** needs-human-design: rig memory reduction candidates from local travel trace work

Context: I experimented briefly with removing duplicate resolved-state `entry.value` storage, then reverted it. That was too invasive without a stronger understanding of rig's state contract. It also did not solve the failure: the high-risk local travel subset still crossed the 4 GB line and was killed.

Evidence from local run:
- Command shape: travel defended high-risk subset (`user_task_10 user_task_11 user_task_12 user_task_18 user_task_19`) with `-p 5`, `MLLD_TRACE_MEMORY=1`, `MLLD_TRACE=effects`.
- Trace max after the experimental state-shape change: ~4.78 GiB RSS / ~3.69 GiB heap at late planner/tool execution (`@plannerToolContext`).
- Largest traced session writes were `planner.state` writes, peaking around 335 MB even after the experiment.
- Hot scopes near the peak included late planner context/projection/tool metadata paths: `@plannerToolContext`, `@toolLabels`, `@recordDisplayMode`, `@projectResolvedEntry`, `@toolDeclaredParamNames`, and `@plannerValidateResolvedFamilyRef`.
- This suggests the remaining pressure is not only the Python MCP server; mlld's planner session is repeatedly serializing / retaining very large proof-bearing state during long travel tasks.

Design candidates to consider before changing code:
1. Add a regression/measurement harness first. Capture max RSS, max heap, and max `planner.state` session write size for the travel high-risk subset. This gives us a safe way to compare proposed fixes without relying on remote OOM symptoms.
2. Clarify the resolved-state contract. `entry.value`, `identity_value`, and `field_values` may intentionally preserve different wrapper/factsource behavior. Removing one copy ad hoc is risky and should be treated as a design change, not a local optimization.
3. Consider separating durable proof-bearing state from planner session state. The planner session may only need compact handles plus planner-visible projections; full wrapped state could live in a side store/checkpoint that ref resolution and policy compilation can read without forcing each planner session write to serialize the entire object graph.
4. Consider compact factsource representation. Instead of storing full StructuredValue metadata on every duplicated field wrapper, store scalar field values plus compact source attestations keyed by `(record, handle, field)`, then reconstruct/check attestations only where policy/ref compilation needs them. This needs careful invariant tests for c-aed5 / c-4a08 / c-ut8r behavior.
5. Avoid full summary reprojection on every tool result where possible. Travel's family -> metadata pattern creates many repeated records. Returning only newly-resolved handles/projections, or caching planner-visible projections until state changes, may reduce late `@projectResolvedEntry` pressure.
6. Treat review/blob storage separately from planner-visible metadata. Travel is unusual because review-heavy metadata is needed by derive/compose workers but should not be planner-visible. Large untrusted blobs may be better stored behind handles/artifacts and materialized only for worker phases.

Important non-suggestion: I do not recommend simply deleting `entry.value` from resolved state based on the current evidence. It failed to keep the run under 4 GB and may break intentional invariants around whole-record refs and factsources.

**2026-04-25T19:21:04Z** mlld-side memory reductions landed in /Users/adam/mlld/mlld:

- f5d720b9d: release finalized session frames, avoid document-mode completed-session history, store live session writes in one observed slot copy.
- 98fe71171: make --trace-memory memory-only unless --trace is also set, avoid building disabled session trace/SDK payloads, skip final session trace construction when session trace is off, reuse returned final session snapshots during disposal, and structurally share unchanged subtrees across observed session writes.

Validation: affected Vitest/SDK/CLI suites passed (136 pass / 1 skip), npm build passed, and rig invariant gate passed at 106/0.

Travel p20 local with MLLD_TRACE_MEMORY=1 and trace file still crossed the 4GB guard after these changes. Latest structural-sharing run: trace max was ~3.79GB RSS / ~2.91GB heap at rig/runtime.mld:@projectResolvedEntry, then external monitor saw ~4.35GB before kill. Top sampled scopes were @projectResolvedEntry (~715 calls), @mergeResolvedEntries, @normalizeResolvedValues, and @finishPlannerTool.

Current hypothesis: remaining spike is not mlld trace/session observer overhead. It is the rig state shape/projection path rebuilding the growing resolved state late in travel runs, especially repeated display projection and merge of resolved entries. Clear rig payoff likely comes from making planner-visible state incremental/cached/handle-indexed so @projectResolvedEntry/@normalizeResolvedValues do not rebuild all prior resolved records on every planner tool completion.

**2026-04-25T20:00:21Z** WORKAROUND IN PLACE (2026-04-25, OOM agent session). Travel runs reliably with MLLD_HEAP=6g (8g headroom). scripts/bench.sh now passes -f heap=8g for travel dispatches automatically. With 6 GB heap on -p 20:
- bench_exit=0, no OOM/MCP-disconnect/fatal-heap errors
- Peak external monitor RSS 6383 MB
- mlld trace max 5133 MB RSS / 4546 MB heapUsed at @directExe llm.call:finish

Remaining: travel utility 8/20 (12 fail, 4 of those are 900s timeouts). Heap fix unblocks measurement; underlying memory tail spike + task quality remain open. Workspace + travel can't run concurrently in CI (64 GB Team-plan cap).

Per-task failures filed as separate tickets — see TR-UT* tickets for transcript-grounded analysis on each.
