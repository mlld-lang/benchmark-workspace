# Migration Handoff

Session-passing breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end.

For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## What's next: finish Phase 2 verification surface

**Stage B core landed at `c7ad4c8`.** Runtime, intent, and all 5 workers are on shelf API. ~430 lines of bucket helpers deleted. `state.resolved` field is gone. `@agent.plannerShelf` is the resolved-record store. Path A wire format preserved.

**What's incomplete**: the verification surface. 9 zero-LLM test files were skipped to land Stage B core; 5 scripted-LLM tests regressed on fixture conversion. Until those are converted/fixed, the gate is GREEN-FOR-SUBSET (169/0/1), not GREEN-FOR-CORPUS (was 286/0/5 pre-Stage-B).

**This session's job**: mechanical conversion of 9 test files + 5 fixture helpers using the proven template below, then mutation-matrix re-baseline, then ARCHITECTURE.md updates.

**Goal**:
- Zero-LLM gate at 286+/0/5, full corpus, zero skipped suites
- Mutation matrix Overall: OK
- All 4 scripted suites green
- `rig/ARCHITECTURE.md` + `bench/ARCHITECTURE.md` + `labels-policies-guards.md` updated (Phase 2 doc discipline)
- **The 2 handle-drift xfails in `identity-contracts.mld` flipped to xpass** — Phase 2's central observable milestone.

---

## Anti-pattern to avoid

This migration went through **4 sessions of accumulating preparation before Stage B core landed**. Each session found a plausible reason to defer execution (probe, scaffold, validate, prepare). The 5th session executed.

If you find yourself wanting to:
- Add more scaffolding ("dual-write," "transitional helpers")
- Probe / investigate / validate before converting
- Split conversion into more sub-stages
- Defer parts to next session

— recognize that as the deferral pattern this migration spent 4 sessions on. **The pattern is mechanical conversion. The template is below. The files are listed. Apply.**

---

## Current state

- **Phase**: Phase 2 Stage B core landed. Verification surface incomplete.
- **Latest commits**: `485bb88` (scaffolding) → `c7ad4c8` (Stage B core).
- **Pinned binary**: REMOVED. System mlld v2.0.6.
- **Architecture**: shelf decl in `@runPlannerSession` body; `@agent.plannerShelf` threaded; Path A wire format via `@stateHandleFromAddress` / `@parseRigHandle`.

## Gate state

| Gate | Result |
|---|---|
| Zero-LLM (REDUCED — 9 suites skipped) | 169/0/1 |
| Mutation matrix | BASELINE FAILS (banking 1, slack 1, workspace 1; travel OK) |
| Scripted banking | 7/3 |
| Scripted slack | 13/1 + 1 xpass |
| Scripted workspace | 10/0 |
| Scripted travel | 13/1 |

---

## The 9 skipped zero-LLM files

Each ~30-90 min of mechanical conversion using the template below. Run `mlld tests/index.mld --no-checkpoint` after each file to verify localized green.

| File | LoC | Bucket refs | Notes |
|---|---:|---:|---|
| `xfail-and-null-blocked.mld` | 165 | 2 | smallest — start here |
| `extract-derive-and-execute-compile.mld` | 506 | 1 | trivial |
| `named-state-and-collection.mld` | 515 | 7 | `@compileExecuteIntent` callsites + `@bucketItems` reads |
| `state-projection-a.mld` | 321 | 44 | projection contracts |
| `state-projection-b.mld` | 316 | 34 | writer + planner-cache; some tests obsolete (test deleted bucket-merge fns) — rewrite as per-key cache invalidation tests |
| **`identity-contracts.mld`** | 438 | 43 | **Phase 0.A invariants**. **The 2 handle-drift xfails MUST flip to xpass** — remove `xfail: true` markers in same commit. **Highest symbolic priority** — convert this even if others are deferred. |
| `worker-dispatch.mld` | 577 | 8 | largest rewrite |
| `proof-chain-firewall.mld` | 536 | 13 | |
| `url-refs-b.mld` | 369 | 18 | UR-13..24, large bucket fixtures; some tests obsolete — rewrite via shelf-write through `@dispatchResolve` rigTransform |

Recommended order: smallest first to build pattern fluency.

## The 5 scripted-LLM fixture regressions

Located in `tests/lib/security-fixtures.mld`. ~5 helper exes that build state with `state.resolved.<rt> = [...]` need to populate a shelf instead. Each helper becomes an exe that takes a shelf slot ref or returns a populated agent.

Affects: banking (3 fail), slack (1 fail + 1 xpass), travel (1 fail).

---

## Conversion template

```mlld
exe role:worker @testFoo() = [
  let @shelfable = @shelfRecords(@records)  >> filters direction!="output"
  shelf @ps from @shelfable with { versioned: true, projection_cache: ["role:planner"] }
  let @v = { ... } as record @recordDef
  let @w = @shelf.write(@ps.<rt>, @v)
  let @agent = { records: @records, plannerShelf: @ps }
  ... @compileExecuteIntent(@agent, @emptyState(), @tools, @decision, @query) ...
]
```

**Required gotchas** (each one bites at least once during conversion):

- Shelf scope expires at exe-body exit. Each test exe declares its own shelf inline.
- Records used in shelves need `write: { role:worker: { shelves: { upsert: true } } }`.
- `@shelfRecords()` filters out input-only `*_inputs` shapes (those have `direction != "output"`).
- Signatures changed across these exes — agent now threads as first arg: `@compileExecuteIntent`, `@compileToolArgs`, `@compileRecordArgs`, `@resolveRefValue`, `@lookupResolvedEntry`.
- Test exes calling `@shelf.write` need `role:worker`.
- `let @x = @shelf.write(...)` — bare statement is rejected.
- `var` not allowed inside block bodies (e.g. `for parallel`). Use `let`.
- Parameter named `shelf` shadows the `@shelf.*` global API. Use `ps` / `slotRef` / etc.
- `state.resolved` is gone. Replace with `@agent.plannerShelf.<rt>` slot ref OR `@shelf.read(@agent.plannerShelf.<rt>)` array.

## State shape change

**Before**: `{ resolved: {<rt>: bucket, ...}, extracted, derived, extract_sources, capabilities }`
**After**: `{ extracted, derived, extract_sources, capabilities }` — shelf is in scope via `@agent.plannerShelf`, not part of state.

Phase results no longer return `state_delta.resolved`. They return `entries: @recordValues[]` and the caller writes to shelf.

---

## After tests are converted

1. Re-baseline mutation matrix: `uv run --project bench python3 tests/run-mutation-coverage.py`. Verify Overall: OK. Capture new snapshot in `tests/baselines/mutation-matrix.txt`.
2. Update `rig/ARCHITECTURE.md` — phase model + state model rewritten (bucket → shelf historical); list deleted-from-rig functions in migration impact paragraph.
3. Update `bench/ARCHITECTURE.md` — "What stays / What goes" table reflects bucket no longer existing.
4. Update `labels-policies-guards.md` — any bucket framing → shelf framing; handle-string identity → `.mx.key`.
5. Phase 1.A.2 comment-header refresh (separate follow-up commit; deferred from Phase 1).

After all five steps, Phase 2 is complete. Phase 3 (planner prompt revision + remaining doc rewrites) is one small follow-up session — the planner prompt change requires bench-sweep before/after numbers in commit message per migration-plan §3.B.

---

## Notes carrying forward (Phase 1 lessons still relevant)

- mlld interprets `@var.field` inside string literals as variable access. Avoid writing record-shape examples like `@record.write: {}` inside descriptions.
- Test scaffold patterns: tests submitting tools need `exe role:worker @testFoo()`; tests calling `policy.build` from wrapper exes need `role:planner`.
- `rig/workers/execute.mld` `@dispatchExecute` is `exe role:worker` because the body invokes `@callToolWithPolicy` (worker-side dispatch). Don't change that.

## Pre-existing uncommitted files (NOT migration commits)

`.tickets/c-2ec6.md`, `c-5a08.md`, `c-9c6f.md`, `labels-policies-guards.md` (display→read pre-rename), `rig/workers/planner.mld` (Slice 1 native fingerprint), plus `COMMENTS-*` tracking files. Handle separately from migration commits.

## Tickets

- **m-ed0b** (mlld): resolved by Phase 1. Can close.
- **m-68b6** (mlld): closed (was clean-side index/interpolation issue).

---

## Sessions log

| Date | Session | Commit |
|---|---|---|
| 2026-05-07 | bench-grind-22 (plan) | `5516430` |
| 2026-05-07 | phase-0-A invariants | `01698fa` |
| 2026-05-07 | phase-0-B baselines | `f58ddad` |
| 2026-05-07 | phase-1 main | `bbf2e7d` |
| 2026-05-07 | phase-1-closeout | `694c9cd` |
| 2026-05-07 | phase-1-docs | `31992fc` |
| 2026-05-07 | output-records write: blocks | `50418dc` |
| 2026-05-08 | phase-2-readiness | `100a343` |
| 2026-05-08 | phase-2-handoff-refresh | `9a102c2` |
| 2026-05-08 | stage-b-scaffolding | `485bb88` |
| 2026-05-08 | stage-b-core (430 lines deleted; partial test conversion) | `c7ad4c8` |
| 2026-05-08 | stage-b-completion (next) | TBD |
