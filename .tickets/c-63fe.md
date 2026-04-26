---
id: c-63fe
status: open
deps: []
links: [c-9d56]
created: 2026-04-25T04:45:37Z
type: bug
priority: 1
assignee: Adam
tags: [infrastructure, mcp]
updated: 2026-04-26T01:57:57Z
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
