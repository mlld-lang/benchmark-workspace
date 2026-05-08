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
| **`identity-contracts.mld`** | 438 | 43 | **Phase 0.A invariants**. **The 2 group-level `xfail: true` markers MUST be removed in same commit**: line 399 (group `cross-resolve-identity-handle-drift`, contains `@testCrossResolveIdentitySlackHandleDrift` line 228) and line 406 (group `selection-ref-survives-reresolve-handle-drift`, contains `@testSelectionRefSurvivesHandleDriftSlack` line 272). Both ticketed `m-shelf-wildcard`. **Also**: 3 `@testEntryShapeBucket*` tests (banking/workspace/travel/slack) test `_rig_bucket: "resolved_index_v1"` sentinel directly — obsolete, rewrite as shelf-shape entry contracts (not just xfail removal). **Highest symbolic priority** — convert this even if others are deferred. |
| `worker-dispatch.mld` | 577 | 8 | largest rewrite |
| `proof-chain-firewall.mld` | 536 | 13 | |
| `url-refs-b.mld` | 369 | 18 | UR-13..24, large bucket fixtures; some tests obsolete — rewrite via shelf-write through `@dispatchResolve` rigTransform |

Recommended order: smallest first to build pattern fluency.

## The 5 scripted-LLM fixture regressions

Located in `tests/lib/security-fixtures.mld`. ~5 helper exes that build state with `state.resolved.<rt> = [...]` need to populate a shelf via slot-ref-passing pattern (see template below).

Affects: banking (3 fail), slack (1 fail + 1 xpass), travel (1 fail).

**Mutation matrix baseline-fail attribution**: all three are fixture-conversion regressions, not independent bugs:

- **banking** — `updateScheduledTxExtractedRecipientRejected`: expects `payload_only_source_in_control_arg`; gets `control_ref_backing_missing` because the resolved-bucket fixture path no longer populates the shelf. Fixture needs to call shelf-write before invoking `@compileExecuteIntent`.
- **slack** — `selectionRefRealSlackMsgHandleRejected`: "fixture setup minted no slack_msg handles" because fixture builds `state.resolved.slack_msg = [...]` directly; with shelf, those entries never land.
- **workspace** — `extractEmptyResponseRejected`: same family; fixture builds bucket-shape state for an extract path.

All three clear once the fixture helpers populate via shelf. No independent investigation needed. Travel's mutation matrix passing despite scripted fail tells you mutation matrix uses a stricter fixture path that's already shelf-clean for travel.

**Fixture helper signature** (Q4 from prior session, verified pattern):

```mlld
>> tests/lib/security-fixtures.mld
exe role:worker @populateBankingScheduledTxs(slot, recipientName) = [
  let @t1 = @mintScheduledTx("tx_001", @recipientName, "100") as record @scheduled_transaction
  let @w1 = @shelf.write(@slot, @t1)
  let @t2 = @mintScheduledTx("tx_002", "Bob", "50") as record @scheduled_transaction
  let @w2 = @shelf.write(@slot, @t2)
  => 2  >> count for verification
]

>> consuming test
exe role:worker @testFoo() = [
  shelf @ps from @shelfRecords(@bankingRecords) with { ... }
  let @count = @populateBankingScheduledTxs(@ps.scheduled_transaction, "Alice")
  let @agent = { records: @bankingRecords, plannerShelf: @ps }
  ... assertions ...
]
```

Helpers take slot refs as params; shelf decl stays in caller's body so the slot stays alive. Helpers never return an agent (shelf reference dies across exe boundaries).

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
- `@shelfRecords()` filters out input-only `*_inputs` shapes (those have `direction != "output"`). Don't use `from @records` directly when `@records` includes `*_inputs` shapes — error is loud but easy to miss the helper exists.
- Signatures changed across these exes — agent now threads as first arg: `@compileExecuteIntent`, `@compileToolArgs`, `@compileRecordArgs`, `@resolveRefValue`, `@lookupResolvedEntry`.
- Test exes calling `@shelf.write` need `role:worker`.
- `let @x = @shelf.write(...)` — bare statement is rejected.
- `var` not allowed inside block bodies (e.g. `for parallel`). Use `let`.
- Parameter named `shelf` shadows the `@shelf.*` global API. Use `ps` / `slotRef` / etc.
- `state.resolved` is gone. Replace with `@agent.plannerShelf.<rt>` slot ref OR `@shelf.read(@agent.plannerShelf.<rt>)` array.

**Gotchas observed during the 14 conversions in `c7ad4c8`** (apply prophylactically):

- **Helpers can't return populated agents — shelf reference dies across exe boundaries.** Pattern that works: shelf decl in caller's body; helper takes slot ref(s) as params and writes to them; helper signature is `(slotRef, ...params) → recordsWritten` not `(...) → agent`. For multi-slot population, take multiple slot refs.
- **`tests/fixtures.mld` records need `write:` blocks too.** Phase 1 added them to `bench/domains/*/records.mld` but not to test-only records. `@contact`, `@note_entry`, `@flat_display_contact`, `@plain_mode_message` already updated; `message_entry`, `number_row`, others may need same when their tests come up. Without the declaration, `@shelf.write` denies with `WRITE_DENIED_NO_DECLARATION`.
- **Helper-record vars need explicit re-export from `tests/fixtures.mld`.** Updating the file's export list (around lines 476-507) when a converted test imports `@aliceContactRecord` etc. Already added: `@aliceContactRecord`, `@bobContactRecord`, `@noteEntryRecord`, `@numberOneRecord`, `@numberTwoRecord`, `@summaryRecord`.
- **Records with `key: <typed-handle-field>` reject string fixture values at shelf-write time.** Pre-Stage-B, tests assigned `parse_id: "pv10_test"` to `state.resolved` directly with no validation. Shelf validates strictly. Either change `key:` to a string fact field (parse-value test did this — `key: iban_value`) or use a runtime-handle-minting helper that produces a real handle value.
- **`projection_cache:` array must list every role the test asserts through.** If a test projects via `role:advice`, decl needs `projection_cache: ["role:planner", "role:worker", "role:advice"]`. Missing roles don't cache (correctness fine; versioning behavior may surprise in cache-correctness tests).
- **`[rig:diag:resolveRef]` trace lines are noisier post-Stage-B.** Every `@resolveRefValue` goes through the agent-shelf path. Stub responses now produce extra trace lines that aren't failures — easy to mistake for errors when scanning output.
- **`as record @def` inside a `for` doesn't parse as expression form.** `for @v in @items => @v as record @def` fails. Use let binding: `for @v in @items [ let @c = @v as record @def => @c ]`.

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
