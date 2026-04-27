---
id: c-63fe
status: in_progress
deps: []
links: [c-9d56, c-3438, c-36fe, c-d590, c-cb4a, c-8dff]
created: 2026-04-25T04:45:37Z
type: bug
priority: 0
assignee: Adam
tags: [infrastructure, mcp]
updated: 2026-04-27T07:26:10Z
---
# Travel c-63fe: outer MCP timeout cascade and rig memory hot-path attribution

**Current scope, 2026-04-27.** This is the clean-side anchor for travel heavy-run failures. It has two active tracks, and both need evidence before more broad rig rewrites land.

1. **Outer MCP timeout cascade.** Opencode times out long `mlld_tools_resolve_batch` calls, then the planner degrades into `Request timed out`, `Connection closed`, and `Not connected`. Inner AgentDojo MCP calls are fast and are not the current suspect. mlld-side bridge serialization/cancellation work is tracked in m-0710; clean-side timeout/no-progress behavior remains linked here.

2. **Rig memory hot-path attribution.** The previous indexed-bucket/planner-cache/resolve-delta stack improved throughput in some sweeps but did not prove a memory reduction. It is preserved on `mem-experiments/c-63fe-rig-memory`; re-landing or restoring it should be judged separately from the next memory investigation.

Current best memory evidence is the zero-LLM late-spike repro in `tmp/c63fe-late-spike/`: the first clear terminal boundary is around `@workerStateSummary`, compose prompt/state projection, `@dispatchCompose`, seeded planner compose, and final session/write extraction. Claude is identifying the worst travel case so we can seed a deterministic or mock-agent repro without costly LLM calls.

Do not use this ticket as a bucket for old derive, array-shape, record-merge, or planner-over-iteration issues. Those tickets are closed context unless they recur with fresh evidence. New rig changes should first improve attribution: phase-level memory summaries, payload sizes, clone/materialization counts, and the first boundary where RSS jumps.


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

**2026-04-25T20:22:00Z** rig projection repro created in /Users/adam/mlld/mlld/tmp/rig-memory-repro:

- `projection-repro.mld` imports the real rig runtime helpers, synthesizes travel-like resolved records, repeatedly calls `@updateResolvedState`, then calls `@plannerVisibleState`.
- Default 40-row batches complete locally and show high RSS relative to tiny planner-visible JSON. Latest run: 160 total entries, final visible JSON 34,307 bytes, RSS samples around 0.98GB after visible1, 1.24GB after visible2, 1.34GB after visible3, 1.34GB after visible4, with state-merge samples in the same range.
- Stress 80-row batches reached 2.55GB RSS at only 320 entries while final planner-visible JSON was 68,885 bytes.
- Setting hidden `review_bytes` and `note_bytes` to zero still peaked around 1.69GB RSS at 160 entries, so the synthetic repro points more at repeated rig object/array materialization than at large hidden review text alone.

Rig-specific payoff candidates:
1. Replace `@mergeResolvedEntries`' per-incoming-entry filter+concat loop with a handle-indexed merge path. Current shape is O(existing * incoming) and rebuilds the accumulated array repeatedly.
2. Cache planner-visible projections per `(record_type, handle, role)` or per resolved bucket version. `@plannerVisibleState` currently rebuilds all visible resolved summaries every iteration.
3. Keep full proof-bearing resolved state durable, but pass planner sessions compact handles/projections rather than repeatedly serializing/reprojecting the full growing state graph.

**2026-04-25T20:34:00Z** indexed projection-cache prototype results:

Added `/Users/adam/mlld/mlld/tmp/rig-memory-repro/indexed-prototype.mld`. This is not production rig code; it hardcodes the synthetic display projection and uses JS to model a possible runtime shape: merge resolved entries by handle once per batch, cache planner-visible projections with the resolved bucket, and return cached visible arrays.

Comparison against `projection-repro.mld`:
- 40-row batches / 160 entries: baseline 25.2s and ~1.34GB RSS; indexed prototype 2.3s and ~0.84GB RSS.
- 80-row batches / 320 entries: baseline 219.1s and 2.55GB RSS; indexed prototype 4.2s and ~0.88GB RSS.
- 250-row batches / 1000 entries: baseline was aborted during second batch after already reaching ~1.7GB RSS; indexed prototype completed in 12.3s and ~1.04GB RSS.

This gives a clear payoff signal for a real rig change, provided invariant tests prove the handle-indexed/cache shape preserves factsource/proof behavior for resolved refs, whole-record refs, family expansion, selection refs, and execute-policy compilation.

**2026-04-25T21:48:32Z** Update from c-30f7 closure: TR-UT10 transcript (ses_239d672a6ffe...) confirms MCP 'Not connected' cascade under -p 20 with heap=8g. Heap-up alone insufficient. The 4 travel timeouts (UT10, UT11, UT12, UT19) are likely all the same pattern — need to verify on UT11/UT12/UT19 transcripts. May need lower concurrency cap, per-task MCP isolation, or MCP server lifecycle changes.

**2026-04-26T01:06:06Z** PHASES 1-3 LANDED (2026-04-25 session 6 → 7).

Implementation per GPT design review:
- Phase 1 (commit 32422b0): adapter helpers — @isResolvedIndexBucket, @indexedBucketEntries (mlld-native, no JS), @bucketItems updated, @lookupResolvedEntry direct-lookup path. Reads tolerate either bucket shape; writes still array.
- Phase 2.0 (commit abf5259): @mergeResolvedEntries flips writer to indexed bucket {_rig_bucket: 'resolved_index_v1', order, by_handle, version, planner_cache}. Audit-pass updated 4 production sites + 6 test sites to use @bucketItems / @bucketLength adapters. by_handle built via @pairsToObject (NOT object spread — spread strips factsources).
- Phase 2.5 (commit 291b142): @populatePlannerCache eagerly projects entries at merge time. @updateResolvedStateWithDef variant accepts recordDef and populates cache. @projectResolvedSummary uses cache when role:planner + version match. Worker projections always fresh (per GPT decision D — they may include raw tainted content).
- Phase 3 (commit d967399): opt-in measurement harness at tmp/c63fe-state-projection-baseline/harness.mld. Reports per-batch RSS, planner-visible JSON size, cache reuse behavior.

Initial measurement (160 entries / 4 batches):
- After batch 4: RSS=1700MB, JSON=31KB
- 5x reuse: RSS 1815→1820MB (+5MB total) — cache hits stable
- visible_json_bytes consistent across reuses

Higher absolute RSS than the OOM agent's JS-pure prototype (~1.04GB at 1000 entries) because mlld wrapper overhead is real. The relative win — handle-keyed merge + cached planner projection — is in production.

Gates: 121/121 invariants (was 106 pre-c-63fe), 23/23 worker tests.
Contract: 14 state-projection tests A1-A4, B1, C1-C2, D1-D3, E1-E3, F1-F2.

Per GPT framing: handle index = storage/addressing only. Proof/authorization stays in factsources/source-class — verified by session-resolved-factsources-survive-boundary still passing.

Travel sweep run 24944774440 in flight on the post-Phase-2.5 image. Will compare against prior 7/20 baseline (run 24942869231) to see whether the 6 MCP-timeout tasks (TR-UT8/10/11/12/18/19) recover with reduced rig-state pressure.

**2026-04-26T01:07:00Z** MEASUREMENT (clean run, stderr suppressed) — 160 entries / 4 batches of 40:

| stage             | RSS    | heap   | visible_json |
|-------------------|--------|--------|--------------|
| baseline          | 671MB  | 276MB  | -            |
| after batch 1     | 703MB  | 346MB  | 8020 bytes   |
| after batch 2     | 782MB  | 437MB  | 15826 bytes  |
| after batch 3     | 984MB  | 713MB  | 23752 bytes  |
| after batch 4     | 1730MB | 1220MB | 31758 bytes  |
| reuse 1 (cache)   | 1871MB | 1551MB | 31758 bytes  |
| reuse 5 (cache)   | 1930MB | 1588MB | 31758 bytes  |
| final             | 1933MB | 1609MB | -            |

Cache reuse stable: visible_json_bytes identical across 5 reuses. Per-call overhead on cache hit is ~12MB RSS (wrapper allocation), heap stable.

Growth pattern is super-linear per batch (+30, +80, +200, +750MB). The batch 4 jump (750MB) suggests rig still allocates a lot per merge — eager projection over the full bucket on every update means batch N projects N×40 entries.

Compare against:
- OOM agent's baseline pre-rework (mlld trace, projection-repro.mld): ~1.34GB RSS at 160 entries
- OOM agent's JS prototype (indexed-prototype.mld): ~0.84GB at 160, ~1.04GB at 1000
- This implementation (mlld-native, with diagnostics): 1.73GB at 160 entries

So 1.3x worse than the JS prototype absolute, ~25% worse than the pre-rework baseline. The cache mechanism + handle-keyed merge are in production, but mlld wrapper overhead per projection step is meaningful.

Possible Phase 3.5 optimizations (not yet attempted):
1. Skip eager projection when cache.entries already covers all by_handle keys (only project newly-added entries, splice into cache)
2. Lazy projection — populate cache on first read, not at merge
3. Compact factsource representation (per OOM agent's design candidate 4)

For now, Phase 1-3 ship as the structural foundation. Whether the production travel suite recovers is the next signal — sweep run 24944774440 in flight.

**2026-04-26T01:25:41Z** REGRESSION on travel sweep run 24944774440 (image 291b142, post Phase 2.5).

Summary: 5/20 PASS (down from 7/20 in prior post-c-c4a4 sweep 24942869231).

Comparison vs prior:
| Task   | Prior (24942869231) | This (24944774440)         |
|--------|---------------------|----------------------------|
| UT0    | PASS                | BROKEN (Guard retry failed)|
| UT3    | (not in this list)  | BROKEN (Guard retry failed)|
| UT4    | PASS                | PASS                       |
| UT5    | PASS                | PASS                       |
| UT6    | PASS                | PASS                       |
| UT7    | PASS                | PASS                       |
| UT9    | response (utility:false) | TIMEOUT (was non-timeout) |
| UT14   | PASS                | response (utility:false)   |
| UT15   | PASS                | response (utility:false)   |
| UT17   | response (utility:false) | PASS                  |

Net: -2 utility, +2 broken sessions, 1 task regressed from response→timeout.

UT0/UT3 broken-session detail: utility:null, n_calls:0, execute_error 'Guard retry failed: resume not available for this exe — use retry instead. Guard: @composeRetryOpencode (for operation:named:plannerllmcallopencode)'.

The guard fires AFTER @plannerLlmCallOpencode completes. It checks planner.runtime.terminal — if not set, it tries 'resume' to nudge the planner toward compose. 'Resume not available' means the LLM call did not establish a resumable session.

Possible causes (need investigation):
1. Eager projection at merge populates planner_cache via @projectResolvedEntry, which may have side-effects in a session-bearing context
2. The new 4-arg @updateResolvedStateWithDef may interact with rig's checkpoint/resume machinery in a way the 3-arg variant didn't
3. Bucket shape change (now {_rig_bucket, order, by_handle, version, planner_cache}) may not round-trip through @planner.set() / session storage cleanly for first-iteration restore

Contract tests still pass (121/121 invariants, 23/23 worker tests) — the structural change is sound on synthetic data. The regression is at an interaction boundary not covered by existing tests.

OPTIONS:

A. Rollback Phase 2.5 (commit 291b142) — keep Phase 1 adapters + Phase 2.0 indexed merge + Phase 3 harness, drop the eager planner_cache. Loses the cache-hit speedup but keeps the merge improvement. Tests A1-A4, E1-E3, F1 still pass; F2 (cache populated via WithDef) would fail and need to be removed.

B. Rollback Phase 2.0 + 2.5 (commits abf5259 + 291b142) — keep only Phase 1 adapters as preparation. State stays array-shaped. Tests A1-A4, F1, F2 fail/remove. E2 (legacy) still passes; E3 (indexed adapter ready) still meaningful.

C. Investigate guard-retry interaction — pull the UT0 opencode session in detail, find what specifically fails resume. May find a small fix that avoids rollback.

Recommendation: B (full rollback to Phase 1) given the user's explicit guidance that rig state changes need design discussion before code. Phase 1 + the 13 contract tests + the measurement harness remain as preparation for a future, properly-designed attempt.

Travel sweep numbers preserve as evidence (run 24944774440 in runs/).

**2026-04-26T01:57:18Z** **2026-04-26T02:00:00Z** TRANSCRIPT INVESTIGATION — DO NOT ROLLBACK

Two agents pulled the failing transcripts (run 24944774440). Findings supersede the earlier rollback recommendation:

**UT0/UT3 broken sessions — pre-existing mlld wrapper-resume bug, NOT Phase 2/2.5 root cause.**
- DB confirms: NO opencode session was created. Earliest session in opencode.db at 01:02:33Z, AFTER UT0/UT3 failure timestamps (01:01:40 / 01:01:46). exec-logs.tgz is 45 bytes (empty).
- Phase 2/2.5 code does NOT run on first planner turn (state is @emptyState() then). So neither bucket shape nor cache is on the wire when failure occurs.
- Same error class previously hit workspace UT4/7/15/17/23/36/37/39 across multiple pre-c-63fe commits (defended.17/20/26/27.jsonl 2026-04-22).
- Theory: Phase 2.5 @populatePlannerCache adds work between LLM turns, plausibly perturbing first-call timing into the m-0f63 failure window. Rollback would restore prior timing but NOT fix the upstream mlld bug.

**UT9 timeout — pure c-63fe MCP infrastructure, unrelated to rework.** 10× 'Not connected' after first resolve_batch timed out with MCP error -32001. This is exactly the original c-63fe symptom. HIGH confidence.

**UT14/UT15 PASS→FAIL — MEDIUM confidence rig-state interaction at derive boundary.**
- No bucket-shape strings (_rig_bucket, by_handle, planner_cache) appear in transcripts → indexed bucket isn't being serialized into prompts directly.
- UT14: First derive returned derive_empty_response on materially identical input vs prior. Planner thrashed extracts, eventually composed wrong answer (named SunSet $315/wk instead of Speedy $336/wk).
- UT15: First derive returned NEW error class selection_ref_validation_failed / selection_backing_missing due to Unicode hyphen mismatch — worker emitted r_car_company_review_SunSet Rent‑A‑Car (U+2011 figure dash), available_handles had r_car_company_review_SunSet Rent-A-Car (U+002D ASCII).
- Both could be: (a) worker stochasticity from timing changes, (b) @resolveRefValue family-no-handle path now reading through indexed entries with subtly different field shape.

**DECISION: do not rollback Phase 2/2.5.** Rolling back loses structural work AND does not fix the actual problems (UT0/UT3 are upstream mlld; UT9 is the original c-63fe symptom we were trying to address; UT14/15 are unverified at the prompt-content level).

**Next steps (ordered):**
1. SPIKE: dump derive[0] input for UT14 in 24942869231 (prior, PASS) vs 24944774440 (new, FAIL) via sqlite3 'SELECT json_extract(data,"$.state.input") FROM part WHERE session_id=...'. Byte-identical → worker stochasticity (re-run). Different → bucket-shape leaks into prompt content; targeted fix in @resolveRefValue family-no-handle path.
2. Re-run UT14+UT15 isolated (`gh workflow run bench-run.yml -f suite=travel -f tasks="user_task_14 user_task_15" -f heap=8g -f parallelism=20 -f shape=nscloud-ubuntu-22.04-amd64-32x64`) to confirm determinism.
3. Reopen mlld m-0f63 with note: travel sweep newly exposes the wrapper-resume timing bug post-c-63fe Phase 2.5. Workspace tripped it on multiple prior commits; travel never had until now. Needs upstream fix in mlld.
4. New ticket: TR-UT14/15 derive regression spike (filed separately).

Phase 1+2.0+2.5+3 stay in place pending steps 1-3.

**2026-04-26T02:40:15Z** **2026-04-26T03:30:00Z** UT14/UT15 INVESTIGATED — no evidence of indexed bucket/cache leakage. Do not rollback on this basis.

5-boundary diff completed (see c-9d56 note 2026-04-26T03:00:00Z for full transcript-grounded analysis):

| Boundary | Result |
|---|---|
| 1. Planner source refs | IDENTICAL between PRIOR (PASS) and NEW (FAIL) runs |
| 2-3. resolveRefValue / sources into derivePrompt | Not directly observable (exec-logs.tgz truncated to 45 bytes both runs); inferred clean from worker output classes |
| 4. handleMap | Visible in validation error — rig produced ASCII handles correctly |
| 5. Final prompt text | Inline workers, not captured |

Failure modes identified:
- **UT14**: planner stochasticity on a pre-existing display-projection bug (`fuel_options: []` shown for hidden untrusted content). Both runs saw same projection. PRIOR planner stochastically chose derive immediately; NEW planner chose extract → 7 thrashing extracts → empty selection_refs → wrong compose. Tracked under new ticket **c-011b**.
- **UT15**: worker LLM autocorrected `Rent-A-Car` (U+002D) to `Rent‑A‑Car` (U+2011) in selection_ref. Rig's available_handles correctly contains ASCII. Known LLM behavior on hyphenated product names. Tracked under new ticket **c-bd28**.
- Both: `planner_error_budget_exhausted` once thrashing started — recovery from wrong first phase is weak. Tracked under new ticket **c-36fe**.

UT0/UT3 (broken sessions) remain attributed to mlld m-0f63 wrapper-resume timing (already reopened with travel reproducer).

UT9 (timeout) remains the original c-63fe MCP infrastructure symptom this rework was meant to address.

**Decision: Phase 1+2.0+2.5+3 stay in production.** Per GPT: "the structural memory work survived a targeted regression investigation. The remaining failures are real, but they're not evidence against the indexed bucket/cache design."

Phase 3.5 optimization candidates (deferred, see prior note 2026-04-26T01:07:00Z) remain available for future iteration once the c-011b/c-bd28/c-36fe follow-ups land and we have a clean UT14/UT15 baseline.

**2026-04-26T03:46:57Z** **2026-04-26T04:30:00Z** MCP LIFECYCLE INVESTIGATION SHAPE (per GPT review).

**Run -p 10 spike, but treat it as mitigation data, not a fix.**

Before choosing lifecycle strategy, answer ONE question first: **is the MCP server PID shared across tasks or already per-task?**

- If **shared across tasks**: restart per task is likely high payoff
- If **already per-task and dying mid-task**: restart-per-task will NOT fix UT9/UT10/UT11/UT12/UT19. Then look at:
  - stdio backpressure (planner emits faster than MCP can drain)
  - per-call isolation (one bad tool call killing the server)
  - watchdog logging (capture MCP server stderr around the cascade)
  - reducing in-task concurrency (fewer parallel tool calls per task)
- If **-p 10 eliminates the cascade**: set a travel-specific CI cap (`scripts/bench.sh travel` already does -p 20; lower to -p 10) while lifecycle work continues

**Investigation order:**
1. Read `src/mcp_server.py` lifecycle — is the server spawned once or per-task?
2. Add MCP PID + RSS logging around the cascade (instrument before fixing)
3. Run -p 10 spike on travel; compare cascade rate vs -p 20
4. Based on PID/RSS evidence, pick lifecycle strategy

**Deprioritize Phase 3.5 rig memory optimizations** until MCP lifecycle is instrumented. The state work (Phase 1-3) helped structurally, but the remaining "Not connected" cascade looks host-side, not rig-side. No point optimizing rig memory if the bottleneck is MCP server crashing under task load.

**2026-04-26T10:07:08Z** **2026-04-26T07:45:00Z** MCP CASCADE MAY BE EFFECTIVELY DEAD post-c-011b/c-db45.

Run 24949257961 (image ede5973). Travel sweep 11/20 (+6 vs baseline 5/20). Critically:
- TR-UT9 (was timeout from MCP cascade): PASS
- TR-UT10/11/12/18 (were timeouts in baseline): now produce 8-13 resolve calls and "Task completed" — outcome=unparseable. **No "Not connected" cascades.**
- TR-UT19 (was timeout): now `planner_ref_validation_failed` — different bug

So c-011b + c-db45 reducing planner thrashing (cleaner phase choice → fewer iterations → less heap accumulation) appears to have lifted heap pressure below the V8 limit even at -p 20 + 32x64 + heap=8g. The OOM cascade may not be reproducible on the new code.

What remains: the over-resolve loop pattern in UT10/11/12/18 — planner calls resolve 8-13 times without ever calling derive/compose. NEW failure mode (not MCP infrastructure), tracked under expanded c-36fe scope.

Action: keep c-63fe open as a watchpoint. If subsequent sweeps don't show MCP cascades, can close in favor of c-36fe + Phase 3.5 deferred. If cascades return on harder workloads (workspace at -p 40, etc.), reopen investigation per GPT's PID-shared question.

**2026-04-26T10:09:51Z** **2026-04-26T08:00:00Z** CASCADE STILL ALIVE — investigation correction. Earlier note "may be effectively dead" was wrong.

Transcript investigation of UT10/UT11/UT12 (run 24949257961, post c-011b/c-db45):
- All three show MCP "Connection closed" / "Connection is down" / "MCP server connection is completely down" errors mid-session
- Pattern: initial single-domain resolves succeed, then resolve_batch on multi-domain (hotels + restaurants + cars) times out, then individual recovery calls hit "Connection closed", planner correctly retries until budget exhausts

Why the failure mode shifted from baseline:
- Baseline (sweep 24944774440): cascade killed sessions early, outcome=timeout
- Now (sweep 24949257961): c-011b/c-db45 reduced thrashing → planner gets further before cascade hits → cascade hits mid-session → planner correctly retries → budget exhausts → outcome=unparseable

Light tasks survive (UT9 — single domain, 5 calls). Heavy multi-domain tasks (UT10/11/12/18 — need many parallel resolves) still die.

**This is +4 utility on travel if fixed properly.** Strategy per GPT remains valid:
1. Question first: is MCP server PID shared across tasks or per-task? Read src/mcp_server.py
2. -p 10 spike as mitigation data (not fix)
3. Add MCP PID + RSS logging
4. Based on PID/RSS evidence, pick lifecycle strategy

GPT's deprioritize-Phase-3.5 framing also stands: rig memory work helped on light tasks but doesn't address the multi-domain cascade. Lifecycle work needed.

c-63fe stays P1.

**2026-04-26T10:15:55Z** **2026-04-26T08:30:00Z** INVESTIGATION FINDINGS (per GPT order: PID question + lifecycle understanding).

**Q1: Is MCP server PID shared across tasks or per-task?**
**A: Per-task.** mcp_server.py is spawned by mlld via `import tools from mcp` per-task. Each task gets its own subprocess (confirmed in src/host.py `_build_local_mcp_command` and src/mcp_server.py header docs).

Per GPT framing: "If already per task and dying mid-task: restart-per-task will not fix UT9/10/11/12/19; then look at stdio backpressure, per-call isolation, watchdog logging, or reducing in-task concurrency." So restart-per-task is OFF the table.

**Q2: Is MCP server dying or just stalling mid-task?**
**Wall-clock evidence (run 24949257961 console.log):** UT10/11/12/18 ALL hit exactly 900s (15min per-task timeout). This means the planner spent most of those 15 minutes patiently retrying failed MCP calls. The session is alive — the MCP subprocess is unresponsive.

Per planner transcripts: "Connection closed", "Connection is down", "MCP server connection is completely down" — these come from the planner's narration of mlld's MCP client error responses. Mlld can't reach the server.

**Q3: What's making MCP unresponsive?**
**Suspects identified in mcp_server.py:**

1. **`_save_state()` runs after EVERY tool call (line 406).** Serializes full env via `env.model_dump_json()` to disk. Includes read-only tools. For travel multi-domain (hotels + restaurants + cars + reviews), env state grows large; per-call I/O cost grows monotonically. SYNCHRONOUS — server can't process other requests during save.

2. **stdio backpressure under parallel resolve_batch.** mlld's resolve_batch may fan out multiple MCP calls. Each blocks on save. Cumulative I/O could overwhelm stdio.

3. **No internal timeouts visible.** mcp_server.py uses `stdio_server` from mcp SDK — if a call hangs in I/O, the server is stuck.

4. **MCP heartbeat logging exists** (`[mcp-heartbeat] pid=X call=N tool=X start=...` to stderr) but stderr is NOT captured anywhere in production runs. Cannot correlate heartbeat patterns with cascade timing without re-instrumenting capture.

**Critical gap: MCP server stderr is invisible in production.** mlld spawns the subprocess via stdio (stdin/stdout) but doesn't redirect stderr. The heartbeats and any server-side error messages are lost. This is the first thing to fix.

**Next moves (per GPT's order):**

1. **Capture MCP stderr in production.** Either: (a) redirect server stderr to a file the host can collect, OR (b) emit MCP heartbeats via a separate channel mlld can capture. Without this, every other diagnostic is guesswork.

2. **Audit `_save_state()` — skip on read-only tools.** Quick win regardless of root cause. Most tool calls in travel are reads (resolve); they don't mutate env. Only need to save after writes (create/send/reserve). This alone could 10x reduce I/O load.

3. **Add per-call latency to heartbeats** (already exists — `elapsed=Xms` in done line). Once stderr is captured, can analyze the latency distribution to confirm/refute the slow-save theory.

4. **-p 10 spike** as mitigation data. If reducing concurrency from -p 20 to -p 10 eliminates the cascade, set travel-specific CI cap while lifecycle work continues.

5. **Phase 3.5 still deferred** — rig memory work doesn't address this layer.

**Implementation order (cheapest first):**
1. Capture MCP stderr (host change in src/host.py / mlld config) — investigation gating
2. _save_state() read-only skip — quick win, low risk
3. -p 10 spike — measurement
4. If still failing: per-call isolation / async I/O for state save

**2026-04-26T10:45:48Z** **2026-04-26T11:00:00Z** -p 20 SWEEP RESULT (run 24954390115): 9/20 (down from 11/20). My _save_state skip + instrumentation hypothesis was WRONG.

**Critical findings from new instrumentation:**

1. **`_save_state()` cost is negligible.** UT8 (only mutation) saved once at 1.6ms. The skip-on-read-only is correct but not the bottleneck I theorized.

2. **All MCP calls are sub-15ms.** UT11 (the canonical cascade test case): 12 successful MCP calls, total 43ms of MCP time. UT9: 9 calls, total 45ms. UT8: 6 calls, total 36ms.

3. **MCP server responds fine throughout.** No growing elapsed_ms, no gaps in call_num, no missed calls.

4. **The 900s wall timeout means bottleneck is BETWEEN MCP calls.** 900s - 0.043s of MCP = ~899.96s of non-MCP work. Per UT11: 12 MCP calls in 900s = ~75s between calls average. That's planner LLM thinking + opencode session + mlld processing — NOT MCP.

5. **Planner narrations "Connection closed", "MCP connection is down" are mlld-side errors, NOT MCP server-side.** Our MCP log only shows calls that arrived. Failures happen BEFORE mlld can reach the server. The diagnosis surface we needed was mlld-side, not MCP-side.

**Regression analysis:**
- UT8 PASS→FAIL: response with different (wrong) compose answer. Different failure mode, not cascade.
- UT9 PASS→FAIL: 900s timeout. New cascade victim — 9 read calls all fast, then planner stuck.
- UT19 response→unparseable: also 900s timeout. Same cascade pattern.

The -2 net change is stochastic load distribution, not a regression from the read-only skip. Different tasks land in the cascade window each sweep.

**Diagnosis correction:**
The cascade is NOT in the MCP server. It's in the mlld↔opencode↔MCP communication layer. The MCP server is innocent. The "Connection closed" narrations are mlld misreading something else as connection failure.

**Possible real causes:**
1. **mlld MCP client timeout.** mlld may have a request timeout (e.g., 30s, 60s) that fires when opencode hasn't drained the response in time. The MCP server completed in <15ms, but the response sits in stdio waiting for opencode to read it. If opencode is busy with the planner LLM call (75s/turn), it doesn't read in time, mlld marks it "connection closed."
2. **Opencode session backpressure.** opencode running multiple concurrent agent sessions at -p 20 may serialize MCP reads in a way that starves individual sessions.
3. **stdio buffer overflow.** If multiple parallel opencode sessions hit the same MCP server (unlikely — PID is per-task), or if response sizes overflow pipe buffers.

**Next investigation:**
- Wait for -p 10 sweep to confirm/refute the parallelism hypothesis
- If -p 10 clears: parallelism cap + opencode backpressure investigation
- If -p 10 also fails: per-task issue, need mlld-side request log (mlld trace)

**`_save_state` skip stays in.** It's correct (read tools shouldn't write state) and harmless even though it's not the fix. Per-call instrumentation also stays — it ruled out the wrong hypothesis cleanly.

**2026-04-26T10:52:02Z** **2026-04-26T11:30:00Z** -p 10 SWEEP RESULT (run 24954391613): 8/20 — WORSE than -p 20's 9/20. Parallelism is NOT the cap. Definitive evidence found.

**Smoking gun: opencode's MCP client times out resolve_batch calls at -32001.**

UT11 at -p 10, opencode session ses_236a76147ffe68rr6BTjvEXkHl, 4 mlld_tools_resolve_batch calls:
- #1: succeeded (3699 bytes output)
- #2, #3, #4: ALL hit `MCP error -32001: Request timed out`

JSON-RPC -32001 = "Request timed out". This is opencode's MCP client firing a timeout against mlld's MCP adapter.

**Architecture clarification:** Two-layer MCP:
1. **OUTER (opencode → mlld):** opencode planner LLM calls mlld via MCP using tools `mlld_tools_resolve_batch`, `mlld_tools_resolve`, `mlld_tools_derive`, etc. THIS is where -32001 fires.
2. **INNER (mlld → AgentDojo):** mlld processes a tool call and may make multiple AgentDojo-MCP calls. This is what we instrumented in `clean/src/mcp_server.py`. Always fast (<20ms).

The AgentDojo MCP server is INNOCENT (proven by our instrumentation). The bug is in the outer opencode↔mlld bridge.

**Hypothesis:** mlld's resolve_batch handler takes >60s (opencode's likely default MCP timeout) on heavy multi-domain batches. Even though each AgentDojo call is <20ms, mlld's processing overhead per tool (state projection, intent compilation, ref resolution, response shaping, plus the bridge IPC) accumulates. After timeout fires, opencode discards the result; mlld is unaware and continues processing (which is why the AgentDojo log shows the calls completing fast — they DID complete, just after opencode gave up).

**This is upstream of clean.** Filed P0 in mlld as `m-0710` with full repro and evidence. Linked.

**Practical implication for clean:**
- This caps travel at ~11/20 with current bench-side fixes (UT9/10/11/12/18/19 cluster blocked)
- No clean-side fix possible — the issue is in mlld's MCP server adapter or opencode's client
- Mitigations to consider while waiting for mlld: cap resolve_batch size in tool catalog (limit fan-out per call), or skip resolve_batch entirely for travel and force individual resolves (more LLM calls but avoids the timeout)

**Sweep changes summary (post c-011b/c-db45/c-63fe-instrumentation):**
- Travel utility: 5/20 (baseline) → 11/20 (post bench fixes) → 9/20 (post MCP instrumentation, stochastic) → 8/20 (-p 10)
- Real ceiling at current architecture: 11-12/20
- m-0710 fix would unblock +5-6 (UT9/10/11/12/18/19) → ~16-17/20

c-63fe stays open as the clean-side tracking ticket. Closes when m-0710 lands and travel sweep verifies +5/6 utility.

**2026-04-26T20:49:37Z** ## 2026-04-26 — Now the dominant remote-travel utility blocker (session bench-grind-9)

Once c-5a24 + c-eda4 landed (closed), travel utility on remote is bottlenecked by MCP destabilization rather than framework. Run 24966154043 (image adc2e7f): 5 of 8 fails were c-63fe-class (MCP "Not connected", "connection down", "timed out"). UT11/12/18/19 all hit it. UT11/12/18/19 PASS locally (where MCP is stable).

## Recommendation: PRIORITY UPGRADE P1 → P0

This is the single biggest lever for travel utility on remote. Estimated +4-5 utility on a clean MCP run. Until it lands, recommend:

- **Travel utility measurement runs LOCALLY** (already documented in CLAUDE.md hybrid pattern).
- Remote travel runs are measurement-noise on this issue.

## Mitigations already shipped (session-8)

- Parallel resolve_batch reduced cascade pressure
- mlld cancellation work (m-0710) — opencode socket-close propagates
- opencode 1.4.3 with configurable mcp_timeout (cfg.mcpTimeoutMs)
- MLLD_HEAP=8g default for travel runs

After all of this, c-63fe still fires. Next mitigations need to investigate root cause: is mlld holding too many concurrent MCP requests open? Is the AgentDojo MCP server itself stateful and racing?

## Status

Open, P0-priority for travel utility recovery.

**2026-04-26T23:12:46Z** **2026-04-26T23:15:00Z bench-grind-10 opus investigation**

Diagnosis localized: cascade is in **OUTER** mlld↔opencode `function-mcp-bridge` transport (not inner Python MCP, which prior instrumentation cleared).

**Self-reinforcing mechanism**: any transient socket close from opencode triggers `function-mcp-bridge.ts:302-305` → `abortSocketRequests` → `abortRequestControl` (line 387, 397) → `control.abortActiveExecution?.()` → `toolEnv.cleanup()` (set line 546) → calls `Environment.cleanup()` (Environment.ts:5167) and `stopInternal` (line 690-703) destroys all activeSockets → proxy.cjs (line 821-838) `socket.on('error')` fires `process.exit(1)` → opencode shows 'Connection closed' (-32000) then 'Not connected' for all subsequent calls in the same opencode `run`.

**Cascade evidence (local UT12 ses_234511c80ffe4wFF8ile2nxNW9)**: 6 successful tool calls (incl. one at 7m37s), then 3 compose calls in sequence: 4.16s 'Connection closed', 1ms 'Not connected', 1ms 'Not connected'. The 1ms response = opencode SDK knows transport is dead and refuses to send.

**H1 (most likely)**: opencode-side transient stream issue → mlld's `abortRequestControl` *promotes* it to permanent failure by destroying sockets that can't be rehydrated.
**H2**: Node GC pause / mlld memory pressure (~5GB RSS during travel) stalls socket reads long enough that opencode's MCP transport decides it's broken. Consistent with UT11/12/18/19 PASSING locally, FAILING remotely (different memory env).
**RULED OUT**: H4 (inner Python MCP — prior instrumentation cleared), H5 (mcp_timeout — 7m37s call succeeded above the 300s timeout, so timeout isn't the cap).

**Side-finding (separate cleanup, not the cascade fix)**: rig/workers/planner.mld:944-951 sets `mcpTimeoutMs: 500000` in @plannerConfig. The opencode harness module (mlld llm/lib/opencode/index.mld:232-307) NEVER reads `cfg.mcpTimeoutMs` — `opencodeInlineConfig` hardcodes `experimental.mcp_timeout: 300000` (line 279). The '120s vs 500s timeout' threads in c-63fe history were based on a config field that has been silently ignored. Either thread it through opencodeInlineConfig (mlld change) or remove the dead field from rig (clean change). Doesn't fix the cascade.

**Recommended next step (without mlld code changes)**: Re-run UT12 locally with `MLLD_TRACE=verbose MLLD_TRACE_FILE=...`. Per LLM-MCP.md the trace emits `mcp.request`/`mcp.progress`/`mcp.response` with `durationMs`, `responseBytes`, `clientClosed`, `error`. If trace shows `mcp.response` with `clientClosed: true` at the 4-second compose mark, that proves H1 + identifies opencode-side close as the trigger. If trace shows mlld writing the response and opencode never reading it, points to H2/H3.

**Defensible fix shape (mlld-side, NOT shipped)**: Decouple the proxy-socket-close path from `toolEnv.cleanup()`. A transient socket close should retain the bridge so a re-connecting proxy can resume; only intentional shutdown (LLM call ending) should run cleanup. Right now the bridge is structurally one-shot per close event.

Full findings + spike scripts: /tmp/c-63fe-investigation/findings.md and /tmp/c-63fe-investigation/spikes/. Codex investigation still running in parallel — will append independent diagnosis when it finishes.

**2026-04-26T23:16:56Z** **2026-04-26T23:30:00Z bench-grind-10 codex investigation (gpt-5.5)**

Independent diagnosis. **Reconciles AGAINST opus's 'mcpTimeoutMs is dead code' side-finding** (opus read outdated v1.4.1 in ~/mlld/mlld; codex correctly read the installed @mlld/opencode@1.4.3 at /Users/adam/mlld/modules/opencode/index.mld:232-294 which DOES wire mcpTimeoutMs through to experimental.mcp_timeout). The 500.04s timeouts in run 24968679636 match `mcpTimeoutMs: 500000` EXACTLY — so the timeout IS being applied as configured.

**Codex's primary diagnosis (different from opus's, and better-grounded):**
- H2 (ruled IN): opencode's outer MCP timeout fires on long `mlld_tools.resolve_batch` after exactly 500s. Five sessions in run 24968679636 show `MCP error -32001: Request timed out` at 500.024-500.050s on resolve_batch.
- H3 (strongly likely): the slow work is in mlld/rig — `@plannerResolveBatch` Phase B (sequential settle, state merge, projection, planner cache). Inner Python MCP calls (`clean/src/mcp_server.py`) complete in 1.9-11.1ms in the failing sessions. UT10's inner restaurant metadata calls finished by 22:34:50, but opencode didn't time out the outer resolve_batch until 22:41:04 — a 6m14s GAP between fast inner completions and outer timeout, spent in mlld/rig.
- H4 (secondary cascade): once opencode's outer timeout fires, its MCP client is permanently dead for that run → 'Connection closed' then immediate 1ms 'Not connected' for all subsequent calls (matches opus's mechanism observation).
- H1 (ruled OUT): Python MCP server crash. Inner calls completed quickly with no errors.
- H5 (ruled OUT for direct trigger): inner stdio transport corruption. Codex ran a zero-LLM probe (`/tmp/c-63fe-investigation/spikes/mcp_import_parallel_probe.sh`) confirming one server pid + concurrent calls work cleanly. Sharing is fine.

**Reconciled picture (combining opus + codex):**
1. Trigger: rig's `@plannerResolveBatch` Phase B spends 5+ min in pure-mlld code (state merge, projection, planner cache) AFTER inner MCP calls return in ms.
2. opencode's MCP timeout (500s = our configured `mcpTimeoutMs`) fires.
3. Once opencode-side closes the outer transport, mlld's `abortRequestControl` → `toolEnv.cleanup()` → `stopInternal` (per opus's code-path analysis) destroys all sockets → proxy.cjs exits → cascade.

**Decisive next step (codex's recommendation, and shared with opus):** Run `/tmp/c-63fe-investigation/spikes/trace_travel_task.sh` (TASK=user_task_10 MLLD_TRACE=verbose) and inspect:
- `mcp.request` start time for resolve_batch
- inner mcp_calls timestamps from the bench result jsonl
- `mcp.progress` / `mcp.response` cadence between them
- where the 5+ minute gap is

If the trace shows mlld busy in pure-code Phase B after inner calls finish, the fix surface moves to rig (cheaper Phase B settle/merge/projection) — NOT to mlld interpreter. That is the most actionable outcome since it's domain code we control.

Spike scripts: /tmp/c-63fe-investigation/spikes/ (analyze_c63fe_run.py, mcp_import_parallel_probe.sh, trace_travel_task.sh, function_bridge_reconnect_probe.ts).

Codex full findings: /tmp/c-63fe-investigation/codex/findings.md
Opus full findings: /tmp/c-63fe-investigation/findings.md

**2026-04-27T01:01:52Z** **2026-04-26T23:50:00Z bench-grind-10 codex fix-shape (gpt-5.5)**

Codex investigated the fix shape after the prior diagnosis. Both layers are in scope; **fix rig first, mlld second**. Rig fix removes the 5+ minute Phase B tail so the 500s timeout never fires; mlld fix is defense-in-depth so a future deadline-class issue (slow LLM API, etc.) doesn't poison the bridge.

Full writeup: /tmp/c-63fe-investigation/codex/fix-shape.md
Spike scripts: /tmp/c-63fe-investigation/spikes/

---

## Rig fix (clean repo) — primary, do first

### Locations
- `rig/workers/planner.mld:526-550` — `@plannerResolveBatch` Phase B loop
- `rig/workers/planner.mld:535` — per-spec `@settlePhaseDispatch`
- `rig/workers/planner.mld:241-245, 546` — returned-record projection scans full bucket
- `rig/runtime.mld:659-715` — `@mergeResolvedEntries`
- `rig/runtime.mld:724-739, 803-807` — `@populatePlannerCache` projects every cumulative entry
- `rig/runtime.mld:768-781` — `@batchSpecMergeState`
- `rig/intent.mld:85-130` — indexed bucket adapters
- `rig/workers/resolve.mld:76-80` — resolved entries already exist here, can carry deltas

### Hot spots (all algorithmic)
- `@indexedBucketEntries` appends with `entries.concat([entry])` in a loop (`intent.mld:94-110`) → bucket-to-array materialization is **O(N²)**
- `@bucketLength` calls `@bucketItems(...).length` (`intent.mld:118-120`) → indexed-bucket length is **O(N²)**
- `@mergeResolvedEntries` scans/rebuilds `@ctx.pairs` per incoming handle (`runtime.mld:682-696`) → merge is **O(existing × incoming)**
- Phase B gives merge the full `phaseResult.state` bucket (`runtime.mld:772-776`) and each spec state is `initial + that spec's writes` (`planner.mld:517-523`) → each batch ~**O(B × N²)**, behaves like O(N³) tail as N grows
- `@populatePlannerCache` projects every cumulative entry after every spec (`runtime.mld:724-739`)

### Spike measurements (`/tmp/c-63fe-investigation/spikes/phase_b_hotspot_spike.js`)
- 4000 initial + 16 specs × 80 entries: current=**2033ms** → optimized=**19.6ms** (~100×)
- Same with handle collisions: current=**3413ms** → optimized=**15.8ms** (~215×)
- Actual mlld spike (`phase_b_actual_spike.mld`) reached rss=4532MB heap=3930MB after only 160 initial + 8×40 phase-result construction, then OOMed near 8GB heap limit before Phase B rows emitted

### Change shape

1. **Carry deltas from resolve.** `resolve.mld:76-80` adds:
   ```mlld
   state_delta: { resolved: { [@recordType]: @entries } }
   ```
   `@batchSpecMergeState` uses `phaseResult.state_delta.resolved[recordType]` first, falls back to `bucketItems(phaseResult.state...)` for compat.

2. **Make indexed adapters O(N).**
   ```mlld
   @bucketLength(indexed) => order.length
   @indexedBucketEntries(indexed) => append/update without per-entry concat
   ```

3. **Rewrite merge to update `by_handle` directly.**
   ```mlld
   ctx = { order: existingOrder, by_handle: existingByHandle, new_handles: [] }
   for entry in incomingDelta:
     old = valueField(ctx.by_handle, handle)
     next = old ? mergeEntryFields(old, entry) : entry
     ctx.by_handle += { [handle]: next }   >> wrapper-preserving augmented assignment
     if !old: ctx.new_handles += [handle]
   return { order: existingOrder.concat(new_handles), by_handle, version: oldVersion + 1 }
   ```

4. **Make planner cache incremental + indexed.** Use `planner_cache: { version, order, by_handle }`. Project only changed handles at merge time; reconstruct visible array from cached `by_handle` when needed.

5. **Batch-settle once.** Don't call `@settlePhaseDispatch` and `@planner.set` once per spec only to correct runtime in Phase C. Merge all spec deltas into a local `state`, compute one final progress fingerprint, charge one tool call, then do one `@planner.set({ state, runtime })`. Keep log/phase-event writes as needed.

### Expected effect
Phase B becomes proportional to changed handles plus one final fingerprint/projection, instead of repeatedly materializing and remerging the full resolved bucket. Multi-minute tail removed; late heap spike reduced.

### Verification
- Re-run JS spike before/after the two commands above
- Add a smaller actual mlld harness that imports `runtime.mld` only (avoid `workers/planner.mld` because it imports diagnostics)
- Gate with c-3438 projection tests (FP-1 through FP-8) plus factsources/session-boundary/execute-policy invariants
- Targeted local sweep on UT10/11/12/17/18/19 (the c-63fe-class travel tasks)
- Remote travel sweep for the headline number

### Risk
**Medium-high.** Resolved state is proof-bearing. The merge rewrite must preserve wrappers/factsources across the by_handle path. Tests must cover partial-record merge, whole-record refs, field refs, family refs, selection refs, and policy compilation.

---

## mlld fix (mlld repo) — defense-in-depth, do second

### Locations
- `function-mcp-bridge.ts:300-305` — socket close aborts socket requests
- `function-mcp-bridge.ts:397-403` — `abortRequestControl`
- `function-mcp-bridge.ts:540-562` — active tool cancellation currently calls `this.toolEnv.cleanup()` (the damaging line)
- `function-mcp-bridge.ts:690-703` — explicit bridge shutdown destroys sockets and cleans toolEnv
- `function-mcp-bridge.ts:821-838` — proxy exits on socket error
- `function-mcp-bridge.ts:912-925` — cleanup schedules deferred stop (30s grace)
- `Environment.ts:5167-5201` — destructive `Environment.cleanup`
- `exec-invocation.ts:2802-2808`, `mcp/McpImportManager.ts:87-101, 317-350` — current cancellation checks

### Diagnosis
The equivalence 'socket close means run all toolEnv cleanup' is incorrect. Socket close should cancel the affected request. Full cleanup is correct for intentional bridge shutdown but too destructive for transient transport loss. `socket.close` doesn't directly call `stopInternal`; it aborts active request controls. The damaging part is `abortActiveExecution = () => this.toolEnv.cleanup()` (`function-mcp-bridge.ts:546`). Later, normal call-config cleanup schedules `stopInternal`, which destroys sockets (`:690-703`) and the proxy exits on socket error (`:830-833`).

### Change shape
Introduce non-destructive active-execution cancellation:

```ts
// socket/request abort
control.abortController.abort(cancelledError)
control.abortActiveExecution?.()  // cancel this execution, not the environment

// execution setup
const active = toolEnv.beginCancellableExecution(signal)
control.abortActiveExecution = () => active.cancel()
try { await router.executeFunction(...) }
finally { await active.settleOrDetach() }
```

Add `Environment.cancelActiveExecutions(reason)` and shadow-env equivalents that reject active promises/timers without clearing functions, variables, caches, or sessions. Keep `Environment.cleanup()` destructive and call it only for explicit scope/bridge shutdown. Add cancellation checks inside long pure-mlld `for`/`loop`/`while` evaluation so pure mlld work stops without teardown.

### Expected effect
If opencode/proxy closes a socket mid-tool, the request is cancelled and the dead socket gets no response. A new proxy/socket can reconnect to the same bridge during the grace window and keep using preserved bridge/session state. Intentional LLM-call finalization still cleans up.

### Verification
Promote `/tmp/c-63fe-investigation/spikes/function_bridge_reconnect_probe.ts` into a test:
1. Socket A calls `slow_tool`; close A mid-call
2. Socket B calls `fast_tool` on the same bridge
3. Assert `fast_tool` succeeds and `slow_tool` does not mutate after cancellation
4. Add a pure-mlld loop cancellation test (current checks are only at exec-invocation and imported-MCP boundaries)

### Risk
**Medium-high.** If full cleanup is removed before non-destructive cancellation works, abandoned pure mlld work could keep mutating session state while a reconnected client continues. The queue must not run the next tool until the old execution is stopped or quarantined.

---

## Status

- 2026-04-26T23:55: gpt working separately on the c-63fe fix per Adam. Marked **in_progress**.
- Sequencing: rig fix first (clean repo, no upstream dependency, removes the trigger). mlld fix second (defense-in-depth, also addresses future deadline-class issues).
- Cross-suite preventive cleanup tracked in c-cb4a (extend agentdojo normalizer gate to banking/slack).

**2026-04-27T01:58:45Z** 2026-04-26 Codex implementation note:

Implemented a narrow rig-side Phase B delta path, not the broader batch-settle rewrite. Resolve workers now return state_delta.resolved[record_type] with just the new entries; batchSpecMergeState prefers that delta and only falls back to full phaseResult.state for compatibility. Indexed merges now reuse by_handle/order directly for indexed buckets and preserve changed_handles for incremental planner_cache refresh. plannerResolvedRecords now has an indexed-bucket path for selected handles. Added regression state-projection/B5-c63fe-batch-spec-merge-prefers-delta.

Verification:
- mlld rig/tests/index.mld --no-checkpoint: 138 pass / 1 fail (known xfail)
- mlld rig/tests/workers/run.mld --no-checkpoint: 24/24
- mlld qs: exit 0
- git diff --check: clean

Measurement:
- tmp/c63fe-state-projection-baseline/harness.mld under MLLD_HEAP=8g ended around 1096MB RSS / 819MB heap; prior notes for the same harness were about 1933MB final RSS.
- tmp/c63fe-phase-b-delta/harness.mld under MLLD_HEAP=8g ended around 1462MB RSS / 760MB heap with 160 total entries; phase B still spends ~7-12s/spec, so memory is much better but settle time is not fully solved.
- Local travel subset with MLLD_HEAP=8g, tasks 10/11/12/18/19 at -p 5, completed without MCP disconnect/OOM broken sessions: 2/5 utility, ordinary FAILs on 11/12/19, PASS on 10/18. One mlld child peaked above 6GB RSS, so the end-of-task spike remains and larger heap masks rather than removes that risk.

Deliberately deferred: single batch-settle-once rewrite. That is likely the next high-payoff rig change but has a larger behavioral surface than this delta-path slice.

**2026-04-27T02:28:38Z** Opened mlld runtime ticket m-017b for the remaining O(N) indexed-bucket materialization blocker: array augmented assignment should preserve StructuredValue wrappers/factsources when appending proof-bearing values. A mlld-side worker has started investigating that runtime fix. Until m-017b lands, @indexedBucketEntries remains on the metadata-safe but O(N^2) `.concat([@entry])` path.

**2026-04-27T03:05:03Z** 2026-04-27 batch-settle/delta-only progress:

Implemented clean-side resolve_batch settlement rewrite:
- `resolve_batch` now dispatches each spec in delta-only mode, so per-spec dispatch returns `state_delta` without building full `initial+spec` state.
- Batch merge happens in memory through `@batchSpecMergeState` and planner state/runtime is settled once through `@finishPlannerTool`.
- Added `results: array?` to `@planner_tool_result` so the batch result survives record coercion.
- Added invariant `planner-resolve-batch-settles-once` covering a two-spec batch, final resolved buckets, and `runtime.tool_calls == 1`.

Verification:
- `mlld rig/tests/index.mld --no-checkpoint`: `139 pass / 1 fail (1 xfail, 0 xpass-flip-pending)`; only existing `xfail/c-bd28/UH-1-selection-ref-tolerates-unicode-dash-variant` failed.
- `mlld rig/tests/workers/run.mld --no-checkpoint`: `24/24`.
- `git diff --check`: pass.
- Synthetic resolve_batch harness in `tmp/c63fe-resolve-batch-settle/harness.mld`: before this rewrite, 160 synthetic travel-shaped entries ended at about `rss=4111MB heap=2859MB elapsed=149863ms`; after delta-only + single settle, it completed at `rss=3314MB heap=1638MB elapsed=133196ms`. Useful reduction, but not the large win expected from O(N) materialization.

Remaining blocker:
- m-017b is still blocking O(N) indexed-bucket materialization. Even after the second-pass mlld field-access patch and rebuild, switching `@indexedBucketEntries` from `.concat([@entry])` to native `+= [@entry]` still fails `rig/tests/index.mld` at `@sessionContactEntries[0]` with `FieldAccess: Cannot access index 0 on non-array value (object)`. clean/rig remains on concat until m-017b passes the real rig gate.

**2026-04-27T03:18:06Z** 2026-04-27 local travel validation after `6ac56df c-63fe: settle resolve batches once`:

Command: `MLLD_HEAP=12g uv run --project bench python3 src/run.py -s travel -d defended -p 20`

Result: completed without MCP disconnect/OOM broken sessions. Utility `13/20 (65.0%)` in `728.4s` wall, avg `262s/task`.

Pass: UT0, UT1, UT2, UT3, UT5, UT6, UT8, UT9, UT10, UT13, UT14, UT15, UT18.
Fail: UT4, UT7, UT11, UT12, UT16, UT17, UT19.

Memory observation from local polling: most workers stayed below ~2.2GB early, but late-stage workers still climbed sharply. Observed peak RSS was about `6.1GB` for one mlld worker, with other workers crossing ~4-5GB. This confirms larger heap prevents the MCP/OOM cascade locally, but the remaining late task/session memory spike is not solved by batch-settle/delta-only.

**2026-04-27T03:23:15Z** 2026-04-27 native materialization unblocked after m-017b second-pass runtime fix:

With the rebuilt mlld runtime handling source-less serialized array envelopes, changed `@indexedBucketEntries` to native O(N) append (`@nextEntries += [@entry]`) instead of `.concat([@entry])`.

Validation:
- `mlld rig/tests/index.mld --no-checkpoint`: `139 pass / 1 fail (1 xfail, 0 xpass-flip-pending)`; only existing unicode-hyphen xfail.
- `mlld rig/tests/workers/run.mld --no-checkpoint`: `24/24`.
- Synthetic resolve_batch harness with native append: `rss=3637MB heap=2109MB elapsed=114399ms`, `bucket_entries=160`, `runtime_tool_calls=1`.

Interpretation: native append gives the expected materialization-time improvement (133s → 114s on the synthetic harness after batch-settle/delta-only), but RSS is noisy and did not show a clear memory reduction in this harness. The local travel `-p 20` run immediately before the native-append clean change still peaked near ~6.1GB RSS on a late worker, so the remaining high-memory issue is not solved by batch-settle/delta-only and is unlikely to be solved by indexed bucket materialization alone.

**2026-04-27T03:29:49Z** 2026-04-27 late-spike investigation plan:

Current state:
- Clean-side c-63fe commits landed:
  - `6ac56df c-63fe: settle resolve batches once`
  - `a00ca96 c-63fe: use native indexed bucket append`
- mlld runtime dependency landed:
  - `4a752778d m-017b: index serialized array envelopes`
- Rig invariant and worker suites pass with the native O(N) indexed bucket materializer:
  - `mlld rig/tests/index.mld --no-checkpoint`: `139 pass / 1 fail`, only known unicode-hyphen xfail.
  - `mlld rig/tests/workers/run.mld --no-checkpoint`: `24/24`.
- Local travel at `-p 20` with `MLLD_HEAP=12g` completes without MCP/OOM broken sessions (`13/20`, 728s), but live polling still saw late mlld workers peak around `6.1GB RSS`. Heap headroom is a mitigation, not a fix.
- Synthetic resolve_batch harness shows batch-settle/delta-only/native append improve time, but do not explain the late travel spike.

Next plan: build a zero-LLM deterministic repro in `tmp/c63fe-late-spike/` that constructs travel-shaped proof-bearing rig state and samples memory across the suspected terminal boundaries:
1. `@workerStateSummary(@agent, @state)`
2. `@composePrompt(...)`
3. `@dispatchCompose(...)` with stub harness
4. `@plannerTools.compose` inside a seeded `@planner` session
5. `@finishPlannerTool` / `@planner.set`
6. final session/debug-result extraction as used by `@runPlannerSession`

Run it across scaled record/log counts (for example 80/160/320/640 records) and with toggles for planner_cache / execution_log / compose prompt / final session extraction. The goal is to identify the first boundary where RSS/heap jumps and distinguish persistent growth from a finalization-only duplicate materialization.

**2026-04-27T03:42:44Z** 2026-04-27 late-spike repro results:

Created zero-LLM repro under `tmp/c63fe-late-spike/`:
- `harness.mld` builds travel-shaped, record-coerced rig state across 4 families (`hotel`, `restaurant`, `car_company`, `flight`).
- Uses stub compose responses, so no model/API cost.
- Samples memory after state build, planner projection, worker projection, compose prompt, manual stub LLM call, llm log entry, direct `@dispatchCompose`, and seeded `@plannerTools.compose`.

Representative runs:

`C63_PER_FAMILY=40 C63_LOGS=12 C63_REVIEW_BYTES=2048` (160 total records):
- after_state_build: ~757MB RSS / 325MB heap
- after_planner_visible_state: ~757MB RSS / 420MB heap; planner summary JSON ~45KB
- after_worker_state_summary: ~1098MB RSS / 345MB heap; worker summary JSON ~540KB
- after_compose_prompt: ~1100MB RSS / 395MB heap; prompt ~544K chars
- after_manual_llm_call / attestation / llm_log_entry: no RSS jump, heap rises to ~609MB
- after_direct_dispatch_compose: ~1355MB RSS / 827MB heap
- after_seeded_planner_compose_tool: ~1500MB RSS / 1098MB heap

`C63_PER_FAMILY=80 C63_LOGS=24 C63_REVIEW_BYTES=2048` (320 total records):
- after_state_build: ~1191MB RSS / 930MB heap
- after_planner_visible_state: ~1270MB RSS / 1005MB heap; planner summary JSON ~91KB
- after_worker_state_summary: ~1607MB RSS / 1209MB heap; worker summary JSON ~1.08MB
- after_compose_prompt: ~1610MB RSS / 1313MB heap; prompt ~1.09M chars
- after_direct_dispatch_compose: ~2394MB RSS / 2055MB heap
- after_seeded_planner_compose_tool: ~2862MB RSS / 1120MB heap

`C63_PER_FAMILY=80 C63_LOGS=24 C63_REVIEW_BYTES=0` (same record count, tiny untrusted content):
- worker summary JSON drops to ~99KB and prompt to ~106K chars, but RSS still reaches ~1555MB after worker summary and ~2627MB after seeded planner compose.

Interpretation:
- This reproduces the late spike shape without a full travel run or paid LLM calls.
- The first clear terminal boundary is `@workerStateSummary`: compose currently projects the full worker-visible state, including untrusted fields for every resolved candidate, even when planner `sources` names only a subset.
- Prompt text size matters, but wrapper/provenance/session materialization dominates: even with `C63_REVIEW_BYTES=0`, the same 320-record proof-bearing state still reaches ~2.6GB by terminal compose.
- Manual stub LLM call and `@llmCallEntry` are not the RSS cliff by themselves; `@dispatchCompose`/seeded planner compose re-materialize worker summary/prompt and hold them alongside session state.

Most promising reduction path: make compose source-aware. Build a filtered state summary from `decision.sources` instead of always calling `@workerStateSummary(@agent, @state)` over the entire state. Preserve existing behavior when sources include broad wildcards (`resolved.*`, `derived.*`, `extracted.*`) or are absent. For specific sources (`derived.foo`, `extracted.foo`, `resolved.hotel`, structured resolved refs), include only those projected entries/families. This targets the first spike boundary and should reduce both memory and prompt size without changing proof-bearing state storage.

**2026-04-27T05:27:52Z** 2026-04-26 rollback note: preserved the rig memory experiment state on branch mem-experiments/c-63fe-rig-memory at commit e063920, then surgically reverted the rig-side memory-efficiency refactor from main. Reverted commits: a00ca96 native indexed bucket append, 6ac56df settle resolve batches once, 04b5458 resolve deltas in rig batch merge, 291b142 eager planner_cache, abf5259 indexed-bucket writer, 32422b0 indexed-bucket adapters. Follow-up cleanup commit 6ffb232 restored helper imports after removing the adapter layer. Preserved unrelated work: c-5a24 per-field merge, c-eda4 batch state-clobber fix, c-3438 no-progress tests, c-bd28 xfail, and derive insufficient_information changes. Verification after rollback: mlld rig/tests/index.mld --no-checkpoint passes 134/135 with the expected xfail; mlld rig/tests/workers/run.mld --no-checkpoint passes 24/24; mlld qs passes.

**2026-04-27T07:20:50Z** **2026-04-27 cleanup note:** Keep this as the clean-side anchor for travel heavy-run failures, but split the scope clearly:

- Outer MCP timeout cascade: opencode times out long `mlld_tools_resolve_batch` calls, then the session degrades into `Request timed out`, `Connection closed`, and `Not connected`. Inner AgentDojo MCP calls are fast and are not the current suspect.
- Rig memory hot-path attribution: the previous rig memory-efficiency stack is preserved on `mem-experiments/c-63fe-rig-memory`. It improved throughput/pass rate in some sweeps but did not prove a memory reduction; after rollback peak RSS was lower, while pass rate worsened. Re-landing or restoring that work should be judged separately from the next memory investigation.
- Deterministic repro work: prefer zero-LLM or mock-agent harnesses that reproduce the first large RSS jump. The current best evidence points near `@workerStateSummary`, compose prompt/state projection, `@dispatchCompose`, seeded planner compose, and final session/write extraction. Claude is identifying the worst travel case to seed this repro.

Do not use c-63fe as a bucket for old derive, array-shape, record-merge, or planner-over-iteration issues. Those tickets are closed context unless they recur with fresh evidence. New rig changes should first improve attribution: phase-level memory summaries, payload sizes, clone/materialization counts, and the first boundary where RSS jumps.

**2026-04-27T07:27:22Z** 2026-04-27 next-step breadcrumb: Wait for Claude to identify the most memory-problematic travel test case, then use it to seed a deterministic/zero-LLM or mock-agent repro. Pair that with mlld:m-15d9 memory summaries to identify the first RSS jump before changing rig storage/projection shapes again. Likely suspects remain workerStateSummary, compose state/prompt projection, dispatchCompose, seeded planner compose, and final session/write extraction.

**2026-04-27T07:34:46Z** 2026-04-27 mlld-dev update: m-15d9 memory.summary is implemented and built locally. Next c-63fe repro runs should inspect memory.summary first for firstMajorJump/topDeltas/sessionWrites before deciding whether the hot fix is rig compose/source projection or mlld session retention.
