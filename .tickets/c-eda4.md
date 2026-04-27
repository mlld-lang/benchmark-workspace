---
id: c-eda4
status: closed
deps: []
links: []
created: 2026-04-26T19:50:34Z
type: bug
priority: 1
assignee: Adam
tags: [travel, resolve-batch, parallel, framework]
updated: 2026-04-26T20:49:10Z
---
# [Travel] resolve_batch state-clobber: per-spec settle replaces state instead of merging

## Symptom

Travel UT11/12/17/19 fail with `resolved_family_empty.record:hotel` after a successful prior batch resolved hotels. Same in pre-fix baseline 24962959633 and post-c-5a24 fix run 24964974666 — orthogonal to c-5a24.

Concrete: UT11 batch 1 = `[get_all_hotels_in_city, get_all_restaurants_in_city]` both succeed. Batch 2 uses `resolved_family.hotel` for hotel followups + `resolved_family.restaurant` for restaurant followups. Hotel followups fail `resolved_family_empty`; restaurant followups succeed. **Same state, hotel bucket appears empty, restaurant bucket has all 10 entries.**

## Root cause (transcript-grounded + code-read)

`rig/workers/planner.mld:362-367` — `@settlePhaseDispatch`:

```mlld
let @nextState = when [
  @phaseResult.error.isDefined() => @phaseResult.state ?? @toolCtx.state
  * => @phaseResult.state
]
...
@planner.set({ state: @nextState, runtime: @nextRuntime })
```

In `@plannerResolveBatch`:

1. **Phase A** dispatches all specs in parallel against `@initialCtx.state` (snapshot from BEFORE the batch).
   - hotel spec returns `phaseResult.state = initial + hotels`
   - restaurant spec returns `phaseResult.state = initial + restaurants` (no hotels — that spec didn't see them)
2. **Phase B** settles sequentially. Each settle does `@planner.set({state: @phaseResult.state})` — REPLACE not MERGE.
   - settle hotel → `{state: initial+hotels}`
   - settle restaurant → `{state: initial+restaurants}` ← **hotels wiped**
3. Next batch's `@initialCtx.state` reads `@planner.state` which now has only restaurants.

The comment at planner.mld:491-494 says parallel-safe because dispatchResolve has no side effects. True for dispatch, but the SETTLE writes are racing-equivalent: each settle clobbers previous settles' state contributions because each `@phaseResult.state` is a complete state snapshot, not a diff.

## Why this looked like a planner-quality issue

The planner sees "no resolved entries of record hotel" and tries every recovery (re-resolve, known, individual handles). All retries are sane responses to a real framework lie. UT19 hitting 22+ MCP calls is partly this bug forcing endless retries.

## Fix candidates

**A. Merge state diffs in Phase B (recommended).** Each spec's `phaseResult.state` is `initial + spec_writes`. Compute the diff = `phaseResult.state - initial` per spec, then apply diffs sequentially atop the current planner state.

**B. Sequential dispatch when specs reference each other.** Detect specs whose args use `resolved_family` or `resolved` referring to a record family that another spec in the same batch will produce; serialize those. Loses parallelism for dependent batches but trivially correct.

**C. Per-record-bucket merge in settle.** Phase B settle uses @mergeResolvedEntries (or equivalent) to overlay per-bucket rather than `@planner.set({state: <full>})`. Most surgical fix at the settle boundary.

Recommend **C** — most surgical, retains parallel dispatch, doesn't require diff computation, plays nicely with the indexed bucket structure already in place.

## Verification path

Synthetic probe: build initial state with no buckets, simulate two parallel specs returning `initial+A` and `initial+B`, run Phase B settle sequentially, assert merged state has both A and B. Today: B wins. After fix: both survive.

## Affected tasks (run 24964974666)

UT11 (FAIL), UT12 (FAIL, also burned 720s wall flailing), UT17 (FAIL), UT19 (FAIL, 16 MCPs of which most are recovery from this bug).

## Discovered in

Transcript investigation of all 7 failing travel tasks in run 24964974666 per Adam's request. Bug is pre-existing — same symptom in baseline 24962959633.

## Blast radius

Likely also impacts banking/slack any-time multi-spec resolve_batch is used. Travel hits it hardest because every multi-domain task issues mixed-record-type batches.


## Notes

**2026-04-26T20:40:22Z** ## 2026-04-26 — Implementation landed; verified structurally; util-headline noise

Commit `adc2e7f` on main. Verified two ways:

### Local canaries (uncommitted-tree-direct)
`uv run --project bench python3 src/run.py -s travel -d defended -t user_task_11 user_task_12 user_task_17 user_task_19 -p 4`

All 4 tasks now reach compose with substantive answers. **Zero `resolved_family_empty` errors.** Pre-fix: all 4 hit `resolved_family_empty.record:hotel` in batch 2 and burned budget retrying.

| Task | c-eda4 status | Remaining failure |
|------|---------------|-------------------|
| UT11 | ✓ compose with $1050 answer | c-8a89 eval-vs-prompt ambiguity (expected $690) |
| UT17 | ✓ compose with Good Night $1035 | Model picks rating-5 hotel; eval likely wants "budget-friendly" cheaper pick |
| UT12 | ✓ compose with full data | "address: Unable to retrieve" — `get_hotels_address` tool error mid-run |
| UT19 | ✓ compose with full €4,260 table | "MCP connection dropped" — c-63fe |

### Remote sweep `24966154043` (image_sha `adc2e7f`)
12/20 vs 13/20 baseline. Delta = stochastic (UT8/UT18 lost, UT9 gained — none touch c-eda4 paths). Headline number didn't move because the c-eda4-affected tasks have *other* failure modes downstream of the merge fix.

### Image-freshness trap caught
First attempt at sweep (run `24965802796`) used image `aeee073` (pre-c-eda4) because bench's pull step fired before `bench-image.yml` finished rebuilding. CLAUDE.md updated with discipline note (commit `994d770`): local canaries first, then push and wait, then sweep — verify manifest's image_sha matches HEAD.

### Status
**Closing.** Structural fix verified. Remaining travel failures are c-8a89 (UT11), c-63fe (UT19, possibly UT12), and unticketed model-judgment cases (UT17, possibly UT12). The merge fix is necessary scaffolding for any future improvements on these tasks because pre-fix they couldn't reach compose at all.
