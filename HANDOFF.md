# Session Handoff

Last updated: 2026-04-26 (session 7 → 8, end of bench-grind-7)

## Latest sweep (post c-63fe Phase 2.5, run 24944774440)

Image SHA `291b142` (commit `291b142`). Travel sweep on -p 20 + 32x64 + heap=8g.

| Suite | Pass | Total | % | Δ vs prior | Notes |
|-------|------|-------|---|-----------|-------|
| Workspace | 28 | 40 | 70.0% | unchanged | Last sweep run 24938656071 (UT18/33 verify) |
| Banking | 12 | 16 | 75.0% | +1 | BK-UT12 worker-context fix verified |
| Slack | 11 | 21 | 52.4% | unchanged | c-8738 still open, deferred to c-ade3 |
| Travel | **5** | 20 | **25.0%** | **REGRESSED -2** | run 24944774440 — c-63fe Phase 2/2.5 surfaced 4 distinct issues |
| **Total** | **56/97 (57.7%)** | | | -2 | down from 59/97 (60.8%) |

## c-63fe state-projection rework — STAYS IN, spike complete

Phases 1-3 shipped (commits 32422b0, abf5259, 291b142, d967399, fc14a37, c204e80, 3fc15ac):
- Phase 1: adapter helpers (mlld-native @indexedBucketEntries, @bucketItems, @lookupResolvedEntry, @bucketLength, @isResolvedIndexBucket)
- Phase 2.0: @mergeResolvedEntries flips writer to indexed bucket {_rig_bucket: "resolved_index_v1", order, by_handle, version, planner_cache}. by_handle built via @pairsToObject (NOT spread — spread strips factsources)
- Phase 2.5: @populatePlannerCache eagerly populates cache; @updateResolvedStateWithDef variant; @projectResolvedSummary cache-hit logic. Critical: use `!= null` not `.isDefined()` (exe-returned null is wrapped, masks miss path)
- Phase 3: opt-in measurement harness at `tmp/c63fe-state-projection-baseline/harness.mld`

**Gates: 121/121 invariants, 23/23 worker tests.** Contract tests (14 state-projection assertions A1-A4, B1, C1-C2, D1-D3, E1-E3, F1-F2) all pass.

### Spike outcome — c-63fe NOT implicated; three real follow-ups filed

5-boundary diff complete (run 24942869231 PASS vs 24944774440 FAIL). Boundary 1 (planner source refs) IDENTICAL. Boundaries 2-3-5 not directly observable (exec-logs.tgz truncated to 45 bytes in both runs — bench infra issue), boundary 4 visible in validation errors and shows rig produced ASCII handles correctly. Failure modes confirmed at the LLM layer, not the rig-state layer.

**Per-task verdicts:**

- **UT0/UT3 broken sessions** — pre-existing mlld wrapper-resume timing bug. n_calls=0, no opencode session created. Same error class previously hit workspace UT4/7/15/17/23/36/37/39. Phase 2.5 @populatePlannerCache plausibly perturbed first-call timing into the failure window. Tracked under reopened **m-0f63** (mlld). User asked us to leave mlld alone; hand off when ready.
- **UT9 timeout** — original c-63fe MCP infrastructure symptom (the thing the rework was meant to address; unrelated to bucket shape).
- **UT14 PASS→FAIL** — planner stochasticity on a pre-existing display-projection bug. Both runs saw `fuel_options: []` (projection masks untrusted content). PRIOR planner stochastically chose derive; NEW planner chose extract → thrashed → empty selection_refs → wrong compose. Filed **c-011b** [P1].
- **UT15 PASS→FAIL** — worker LLM autocorrected `Rent-A-Car` (U+002D) to `Rent‑A‑Car` (U+2011 non-breaking hyphen) in selection_ref handle. Rig's available_handles correctly contains ASCII. Known LLM behavior on hyphenated product names. Filed **c-bd28** [P2].
- **Both UT14/UT15** — `planner_error_budget_exhausted` dominates once thrashing starts. Filed **c-36fe** [P2].

**c-9d56 stays open** as audit trail for the sweep regression until the three follow-ups land or a sweep verifies UT14/UT15 recover. Don't close on c-63fe-not-implicated alone — the user-visible -2 utility regression deserves history.

**Decision: Phase 1+2.0+2.5+3 stay in production.** Per GPT: "the structural memory work survived a targeted regression investigation. The remaining failures are real, but they're not evidence against the indexed bucket/cache design."

### Travel attack plan (refined per GPT 2026-04-26)

Priority by clear design payoff + low ambiguity, NOT ticket priority. Travel is 5/20; realistic ceiling after this batch is 10-12/20.

**Order:**

1. **c-011b — display projection sentinel.** Biggest structural lever. Sentinel = `"<hidden:array>"` (string). Arrays only for v1. Emit at lowest projection point that knows role+field value (around `@projectResolvedEntry` / `@projectResolvedFieldValue`, NOT `@plannerVisibleState`). Worker projection unchanged. Planner.att rule is explanation, not the fix. See ticket note 2026-04-26T04:30:00Z for implementation steps.

2. **c-db45 — compose decision context contract.** Pick option (a) + small dose of (c). Skip option (b) — "most recent derive wins" is too implicit. Wire `compose.purpose` + sources + named source names into compose worker dispatch (current compose.mld ignores compose decision context entirely — real missing contract). Planner.att: compose.purpose must name authoritative values + exact fields. Compose.att: treat named sources as primary. See ticket note for implementation.

3. **c-8e02 — host-level repro of TR-UT2 env mutation.** Don't run agent. Replay UT2's exact MCP tool sequence directly against `src/mcp_server.py`. Diff pre/post env. Splits root cause into AgentDojo/tool/MCP-server (mutates under direct calls) vs bench harness save/restore plumbing (mutates only with agent). Don't touch rig until this split is known. ~30 min investigation.

4. **c-63fe — MCP lifecycle instrumentation.** Question to answer FIRST: is MCP server PID shared across tasks or per-task? Read `src/mcp_server.py` lifecycle. Add PID + RSS logging. Run -p 10 spike as mitigation data (NOT fix). Based on PID/RSS evidence, pick lifecycle strategy. Deprioritize Phase 3.5 rig memory optimizations until MCP lifecycle is instrumented — remaining "Not connected" cascade looks host-side.

**Bundled with batch 1 (low risk, opportunistic):**

- **c-1fa1** — date-shift patches for TR-UT1, UT3, possibly UT18. Pure Python in `src/date_shift.py`, mirror existing `_patch_workspace_utilities` pattern. ~30 min, zero model risk.
- **c-bd28** — narrow Unicode dash canonicalization for selection_ref handle comparison. GPT spec'd precisely: U+2010–U+2014 + U+2212 → U+002D on comparison path only; preserve stored handle; paired collision test; derive.att "copy byte-for-byte" rule.
- **c-36fe** — planner addendum for extract-failure recovery (defer budget-refund variant).

**Outside scope (hand off):**
- **m-0f63** in mlld — wrapper-resume scoping. Not outside our reach, but outside the rig decision path. File/update with travel evidence (UT0/UT3 reproducer); keep it from contaminating c-63fe rollback decisions. Already done.

**Audit trail:**
- **c-9d56** stays open until c-011b/c-bd28/c-36fe land or a sweep verifies UT14/UT15 recover.

## Cardinal rules in effect (CLAUDE.md conventions A-E)

- **A.** Every failing in-scope test has an open ticket
- **B.** UT-tied tickets carry task id in title (`[BK-UT12]`, etc.)
- **C.** Tickets get transcript-grounded notes per sweep
- **D.** Diagnoses are transcript-grounded, not call-sequence guesses (added session 6 — burned ~10 prior diagnoses retroactively corrected; this session it caught the rollback recommendation as a guess)
- **E.** Utility numbers report against full denominators (97 total). OOS skip is workflow convenience, not denominator reduction.

## Open ticket landscape

**P1**: c-63fe (spike done, stays in), c-9d56 (sweep regression audit trail, links to follow-ups), **c-011b (NEW — display projection hides task-needed fields)**, c-0589 (3 workspace tasks), c-d52c (UT32/37 cleared, blocked downstream by c-0589), c-25af, c-5d98, c-ade3, m-3199, **m-0f63 (reopened in mlld — wrapper-resume scoping; hand off when ready)**.

**P2**: **c-bd28 (NEW — selection_ref Unicode dash tolerance)**, **c-36fe (NEW — planner recovery after wrong phase)**, c-db45 (compose-drops-fields, 3+ travel), c-1fa1 (travel date-shift patches), c-8e02 (TR-UT2 env mutation), c-19ee (record over-hides untrusted; adjacent to c-011b), c-bae4 UNVERIFIED, c-ebd6 UNVERIFIED, c-5929 (multi-stack), c-8738 (deferred to c-ade3), c-db19, c-c653, c-5823 (m-0b70 tickler), refactor backlog.

**P3**: c-78d9.

**Closed/OOS** (16 tickets tagged `oos`): WS-UT13/19/25/31, BK-UT0/9/10/14, SL-UT2/11/15/16/17/18/19/20.

## Quick start for next session

```bash
/rig

# Verify gates green
mlld rig/tests/index.mld --no-checkpoint    # 121 tests, must pass
mlld rig/tests/workers/run.mld --no-checkpoint  # 23 tests, must pass

# Check current ticket landscape
tk ready
tk show c-011b   # display projection signal — biggest lever
tk show c-36fe   # extract-failure recovery
tk show c-bd28   # Unicode dash canonicalization
tk show c-9d56   # audit trail for the sweep regression
tk show c-63fe   # rig state work — closed at top, follow-ups linked

# Optional: determinism re-run on UT14/UT15 to extra-validate c-63fe-not-implicated
gh workflow run bench-run.yml -f suite=travel -f tasks="user_task_14 user_task_15" -f heap=8g -f parallelism=20 -f shape=nscloud-ubuntu-22.04-amd64-32x64

# When ready to sweep
git push  # image rebuilds on bench/, rig/, src/, agents/ changes only
sleep 200  # wait for image rebuild before dispatching
scripts/bench.sh                    # all 4 suites in parallel
scripts/bench.sh travel             # solo: 32x64 -p 20 heap=8g
```

## Key files

| Purpose | Path |
|---------|------|
| Planner prompt | `rig/prompts/planner.att` |
| Worker prompts | `rig/prompts/{extract,derive,compose}.att` |
| Suite addendums | `bench/domains/{workspace,travel,banking,slack}/prompts/planner-addendum.mld` |
| State projection (c-63fe target) | `rig/runtime.mld` @mergeResolvedEntries, @populatePlannerCache, @projectResolvedSummary |
| Adapters | `rig/intent.mld` @bucketItems, @indexedBucketEntries, @bucketLength, @isResolvedIndexBucket |
| Ref resolution (c-9d56 spike target) | `rig/runtime.mld` @resolveRefValue family-no-handle path |
| Tool dispatch | `rig/runtime.mld` |
| Intent compilation | `rig/intent.mld` |
| Execute + result handles | `rig/workers/execute.mld` |
| Travel router | `bench/domains/travel/router.mld` |
| Invariant gate | `rig/tests/index.mld` (121 tests inc. 14 state-projection) |
| Worker tests | `rig/tests/workers/run.mld` (23 tests inc. D7 root-array, E11 file-extract) |
| Date-shift utilities | `src/date_shift.py` |
| OOS skip list | `src/run.py` SKIP_TASKS (with ticket ids) |
| OOM agent's prototype | `~/mlld/mlld/tmp/rig-memory-repro/indexed-prototype.mld` |
| c-63fe measurement harness | `tmp/c63fe-state-projection-baseline/harness.mld` |
| Memory tips (local, untracked) | `tips-memory-efficient-mlld.md` |
| Experiment log | `SCIENCE.md` |
| Investigation methodology | `DEBUG.md` |
| Ticket conventions | `CLAUDE.md` "Ticket Conventions" (A-E) |

## Session 7 commits

97e351d dae045f 0604ff0 d9aee4e 9d2fd0c 47c384a cfbb01d a8731a9 cbfa88f 425028b 773db19 32422b0 abf5259 291b142 d967399 fc14a37 c204e80 9efeee8 cf131f4 3fc15ac (20 commits)
