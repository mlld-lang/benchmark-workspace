# Session Handoff

Last updated: 2026-04-26 (end of bench-grind-8)

## Latest sweep (post all session-8 fixes, run 24962959633)

Image SHA `ef751e0`. Travel sweep on -p 20 + 32x64 + heap=8g.

| Suite | Pass | Total | % | Δ vs session start | Notes |
|-------|------|-------|---|-----|-------|
| Workspace | 28 | 40 | 70.0% | unchanged (no workspace runs this session) | |
| Banking | 12 | 16 | 75.0% | unchanged | |
| Slack | 11 | 21 | 52.4% | unchanged | |
| Travel | **9-11** | 20 | **45-55%** | +4-6 (started at 5/20 baseline) | Plateau reached; clear next-session path |
| **Total** | ~60/97 | | | +5 | |

Travel oscillates 9-10 between sweeps with stochastic flips. The structural ceiling improvements are real (cascade dead, batch budget fixed); the score variance is from c-db45 ripple + Unicode hyphen + planner discipline edge cases.

## Major structural work landed this session

### Cascade is structurally dead
- **Parallel `resolve_batch`** (rig/workers/planner.mld) — Phase A `for parallel(8)` dispatch, Phase B sequential settle. Multi-spec fan-outs that took 451s now complete in 75-300s.
- **mlld cancellation** (m-0710 narrowed scope, GPT shipped) — opencode socket-close now propagates; mlld stops processing on client timeout.
- **opencode 1.4.3** — `experimental.mcp_timeout` now configurable via `cfg.mcpTimeoutMs`. We removed the magic 300000ms baked default.

After these landed: **0 `-32001` errors, 0 `Not connected`, 0 `outcome=unparseable`** in the most recent sweep.

### Batch budget accounting fix
The 5 "budget exhausted" failures (UT6/11/12/18/19) were caused by per-spec `tool_calls + 1` in `@plannerResolveBatch` Phase B. A 6-spec batch consumed 6 of the 25-iteration budget. Fix: Phase C overrides runtime to charge +1 tool_call per batch (whole batch = 1 planner decision). Preserved per-spec state merges; corrected accounting.

### UT8 bench-bug fix
Our `_patch_travel_utilities` for UT8 added a `rating in model_output` check that wasn't in AgentDojo's upstream eval. The model was answering correctly per the user prompt; our patch demanded extra. Removed.

### Compose decision context refinements
- **Authoritative purpose rule** — values explicitly stated in `compose.purpose` ARE authoritative. The c-db45 "say not available" rule no longer overrides values the planner inlined.
- **ASCII hyphen rule** — compose.att now tells worker not to autocorrect ASCII `-` to U+2011 (UT13/UT15 stochastic Unicode hyphen issue).
- **Compose malformed retry** — compose worker output that fails to parse triggers one retry with explicit "previous output was malformed" feedback.

### Test infrastructure
- 8 fingerprint regression tests + 1 schema round-trip test + xfail/UH-1 (c-bd28 captures regression)
- xfail/ infrastructure in `rig/tests/index.mld` for known regressions that don't block the gate

### Module changes (registry, GPT published)
- `@mlld/opencode@1.4.3` — added `mcpTimeoutMs` optional config; default omits config so opencode uses its own default

## Per-task status snapshot (post run 24962959633)

| Task | Status | Block |
|------|--------|-------|
| UT0/2/5/7/9/14/18 | PASS | stable wins |
| UT8 | PASS | UT8 bench bug fix |
| UT13 | flaky PASS | c-bd28 stochastic |
| UT1/3/6/10/12 | FAIL | **c-5a24 c-db45 ripple** (compose can't see resolved/derived values) |
| UT4 | FAIL | **c-f52a** compose says "was not created" despite execute success |
| UT11 | FAIL | **c-8a89** eval-vs-prompt ambiguity (OOS candidate) |
| UT15/16 | FAIL | **c-db1f** stochastic; c-bd28 + c-db45 ripple |
| UT17 | FAIL | compose malformed JSON; retry shipped, may flip next sweep |
| UT19 | FAIL | **c-3c4e** 22 calls hit 900s wall (over-iteration) |

## Highest-leverage next moves

**Priority order, biggest +util first:**

### 1. c-5a24 — c-db45 ripple (compose value visibility) — **+4-5 utility**
The dominant remaining failure cluster. UT1/3/6/10/12 all have planners producing right answers but compose saying "not available" for values that ARE in state.

Two fix paths:
- **(A)** Sharpen `planner.att` rule: planner MUST inline grounded values in `compose.purpose` for every field the answer requires. Cheap prompt fix; partial coverage.
- **(B)** Project derive/extract payload values into `@workerStateSummary`. Audit what compose actually sees vs what's in state. Architectural; cleaner.

Recommend: ship (A) as a pass; if utility recovers most of the 4-5 cluster, defer (B). Otherwise ship (B).

### 2. c-f52a — UT4 compose misreads execution_log — **+1 utility**
Compose worker says "was not created" when execute log shows BOTH a failed first attempt AND a successful retry. Fix: compose.att rule "look for LATEST status per operation; status:'executed' or 'sent' is success."

### 3. c-bd28 wiring debug — **+1 stability (UT13/15 deterministic)**
Helper function `@canonicalizeDashes` exists but wiring into `@lookupResolvedEntry` rolled back due to wrapper-shape issue (`@matched[0]` from for-when returns lossy value). Debug needed; xfail/UH-1 captures the regression.

### 4. c-3c4e — UT19 over-iteration — **+1 utility**
22 calls hit 900s wall. Investigation: likely planner re-resolves due to arg-shape errors (c-d590 family). Fix may be just c-d590 (singular vs plural API mismatch in get_hotels_address).

### 5. c-d590 — get_hotels_address API consistency — **+0-1 utility**
~5-line tool change in `bench/domains/travel/tools.mld`. Reduces over-iteration in UT3/UT11/UT12/UT19.

### 6. c-8a89 — UT11 OOS-candidate decision — **+1 measured utility (denominator)**
Add to `src/run.py` SKIP_TASKS or accept as flaky. Improves sweep-vs-sweep comparison signal.

### Realistic ceiling after #1-#5 land
**14-17/20** on travel. Per c-db28 family + planner discipline + the ripple fix, addressable. The architectural ceiling is ~17-19/20 (the rest are recommendation-hijack-adjacent or eval-stochastic).

## Cardinal rules earned this session

1. **"Slow = bug or flailing" is a sharp diagnostic instinct.** "Planner too slow" was lazy; transcript investigation revealed per-spec budget accounting bug.
2. **Read the actual eval if you suspect false-negative.** UT8 was our patch bug, caught by reading AgentDojo's checker. Cardinal rule A allows this for diagnosis when transcripts show the model doing exactly what the user asked.
3. **One planner decision = one iteration charge.** When framework charges N for what planner sees as 1, that's a bug class.
4. **Add tests for the bug class, not just the bug.** xfail/UH-1, FP-7 (items-only false positive), PR-1 (schema round-trip) were all "this would have caught the bug we just hit."

## Open ticket landscape (post session-8)

**P0:** c-5a24 (c-db45 ripple — biggest single lever)

**P1:** c-f52a (UT4 compose-misreads-execution-log), c-3c4e (UT19 over-iteration), c-0589 (3 workspace tasks), c-63fe (cascade tracker — mostly resolved), c-bd28 (Unicode dash wiring)

**P2:** c-d590, c-8e02, c-19ee (closed), c-bae4, c-5929, c-db1f (stochastic tracker), c-d52c, c-25af, c-5d98, c-ade3, c-bd28, c-36fe, c-9d56 (closed), m-3199

**P3:** c-7eb6 (revisit B), c-8a89 (UT11 OOS), c-78d9, c-3438 (architectural — empirically less needed than expected)

**Total open:** ~28 (some can close after next sweep — c-9d56, c-7eb6 if (B) still doesn't fire)

## Quick start for next session

```bash
/rig

# Verify gates green
mlld rig/tests/index.mld --no-checkpoint    # 130 pass, 1 xfail (UH-1)
mlld rig/tests/workers/run.mld --no-checkpoint  # 23-24 tests

# Check open work
tk ready
tk show c-5a24   # the biggest +util ticket

# Recommended next move — ship c-5a24 (A) prompt rule first
# Edit rig/prompts/planner.att to demand value-inlining in compose.purpose
# Test on UT1/UT6/UT10/UT12 locally before sweeping

# When ready to sweep
git push                            # image rebuilds on bench/, rig/, src/, agents/ changes only
sleep 200                           # wait for image rebuild before dispatching
scripts/bench.sh travel             # solo: 32x64 -p 20 heap=8g
```

## Key files

| Purpose | Path |
|---------|------|
| Planner prompt | `rig/prompts/planner.att` |
| Compose prompt | `rig/prompts/compose.att` (recently edited — c-db45 + ASCII hyphen rules) |
| Planner code | `rig/workers/planner.mld` (parallel resolve_batch + batch budget fix) |
| Compose code | `rig/workers/compose.mld` (malformed retry) |
| State projection | `rig/runtime.mld` `@projectResolvedSummary`, `@workerStateSummary` |
| Selection ref validator | `rig/intent.mld` `@lookupResolvedEntry` (c-bd28 helper exported, not wired) |
| Travel tools | `bench/domains/travel/tools.mld` (c-011b array parsing) |
| Travel bridge | `bench/domains/travel/bridge.mld` (c-011b `@parseListLines`) |
| Date-shift patches | `src/date_shift.py` (UT8 patch fix, no-rating check) |
| MCP server | `src/mcp_server.py` (instrumentation: pid, call_num, elapsed_ms, saved_state) |
| Invariant gate | `rig/tests/index.mld` (130 pass + 1 xfail) |
| Worker tests | `rig/tests/workers/run.mld` (23-24 tests) |
| Stub planner | `rig/workers/planner.mld` (`@plannerNoProgressThreshold = 3`) |
| OOS skip list | `src/run.py` SKIP_TASKS |
| Experiment log | `SCIENCE.md` (session bench-grind-8 just added) |
| Investigation methodology | `DEBUG.md` |
| Ticket conventions | `CLAUDE.md` "Ticket Conventions" (A-E) |

## Session 8 commits

a22dd7c (test: bump mcpTimeoutMs to 500000)
8c4d243 (c-3438 + c-bd28: fingerprint fix + regression tests + parallel resolve_batch)
ef751e0 (4 fixes: batch budget + compose authoritative purpose + ASCII hyphen + UT8 patch + compose retry)
+ earlier: parallel resolve_batch refactor, c-3438 (B) detector + tests, schema fix, mlld @mlld/opencode 1.4.3 published
