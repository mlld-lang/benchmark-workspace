# Migration Handoff

Session-passing breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end.

For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## What's next

**Session 2026-05-08 (migrator-2) progress** (mostly uncommitted; partial 744ba93 commit by user mid-session):
- Records audit landed (8 output records: type:handle → type:string,kind) — committed in 744ba93
- 4 zero-LLM files converted, 2 deleted as obsolete (state-projection-{a,b}) — committed in 744ba93
- identity-contracts.mld rewritten as 5 shelf-shape tests — uncommitted
- @entryHash + @entryFallbackHash deleted from rig/workers/planner.mld — uncommitted
- @parseRigHandle kept in JS with rationale comment (native rewrite via @parse.address breaks null-comparability) — uncommitted
- testExecuteResultHandlesFromReturnsRecord (writeback test) revived in named-state-and-collection.mld post-m-4b6f fix — uncommitted
- Gate at **207/0/1** (up from 169/0/1 baseline)
- m-4b6f filed and fixed by mlld-dev (function-call frame role-leak via stale exe labels)

## Findings — promote to permanent bench/ARCHITECTURE.md in next doc pass

These are records-as-policy / shelf-architecture principles, not session notes. They will trip future record/test authors. Lift to a permanent "Records primitives" or "Working with shelves" section in `bench/ARCHITECTURE.md` as part of the doc updates next session — DO NOT leave them as session-log text.

**F1. `type: handle` vs `type: string, kind: "X"` is the load-bearing distinction.**
- `type: handle` = session-local authorization proof (bridge-minted, validated at write-tool input boundary).
- `type: string, kind: "X"` = authoritative ID with cross-call identity, kind-tagged for downstream fact correlation.
- `.mx.address.key` = stable lookup address (content-derived hash, separate from both).
- **Output records** (tool returns:, projected to LLM, shelved) use `type: string, kind: "X"`.
- **Input records** (`*_inputs`, write-tool inputs that LLM emits handles for) use `type: handle`.
- Conflating these was the original Stage B blocker; the audit (commit 744ba93) reshaped 8 records to align.

**F2. Sessions and shelves are separate primitives that happen to share lifetime in the planner case.**
- `var session @planner` stores call-local planner state (agent, query, runtime, state).
- `shelf @x = ...` stores typed records with permission/merge semantics, scope-local lifetime.
- They co-occur in `@runPlannerSession` (declare shelf inline, thread onto agent, then bind `@planner` session) — but they're distinct concerns.
- **DO NOT** add shelf hooks to the `@planner` session schema. Coupling them on the session primitive makes future non-shelf agents harder. (Surfaced from the scripted-LLM seed gap; see task #17.)

**F3. `as record @alias` bakes the import alias into `.mx.address.record`.** If you `import { @url_ref as @slack_url_ref }` and write `let @r = {...} as record @slack_url_ref`, then `@r.mx.address.record == "slack_url_ref"` (alias name), not `"url_ref"`. Then `@shelf.write(@ps.url_ref, @r)` rejects with "first @shelf.write argument must be a shelf slot reference" because the slot's record type doesn't match. **Don't alias record imports.** (Filed and fixed as m-0904; keep the principle in head for any future records that get aliased.)

**F4. Without `key:` declaration, shelf `merge: append` by default — even if `.mx.address.key` is identical between writes.** Two writes of the same canonical content produce two slot entries, not one. The slack handle-drift xfail flip is blocked on this: `slack_msg` has no `key:` field, so even content-identical messages don't field-merge through the shelf. Keyless append is documented behavior in mlld; either declare an explicit `key:` on records that need merge, or accept the append semantics. (Filed at m-f4a0, closed with discoverability notes.)

**F5. Cross-tool dispatch composition (resolved id_ → handle-typed input) belongs in scripted/live tier.** Production mints handles via real `@dispatchResolve`; zero-LLM tests can't reproduce that path without deep dispatch stubbing. Three tests deleted from `named-state-and-collection.mld` (testRescheduleDispatchSucceeds, testCollectionDispatchPolicyBuild, testCollectionDispatchCrossModuleM5178) per this principle. Documented in-place; covered by scripted/live tier instead.

**F6. m-4b6f fix unblocks function-call dispatch in zero-LLM tests.** `@dispatchExecute` from a `role:worker` test exe now respects role context. `@dispatchResolve` similar. This is what made `testExecuteResultHandlesFromReturnsRecord` revival possible. (Same family as m-5b7d's bare-statement role leak.)

---

## Deferred test root-causes (per advisor — surface here, not just in-file)

**testExecuteResultHandlesFromReturnsRecord** (named-state-and-collection.mld, dispatch writeback): pre-m-4b6f the `@dispatchExecute → @compileForDispatch (role:planner) → returns → @writeRecordsToShelf` chain leaked role:planner forward into the shelf-write call, tripping `WRITE_DENIED_NO_ROLE`. **REVIVED post-m-4b6f fix** (commit 5c229ad). Currently passing.

**testRescheduleDispatchSucceeds, testCollectionDispatchPolicyBuild, testCollectionDispatchCrossModuleM5178** (named-state-and-collection.mld, cross-tool composition): pass `event_id: { source: "resolved", record: "calendar_evt", handle: "r_calendar_evt_X", field: "id_" }` to `add_calendar_event_participants`/`reschedule_calendar_event` whose input records require `event_id: { type: handle }`. Post-records-audit, `calendar_evt.id_` is `type: string` (correctly — output records); the resolved-ref returns a string, and input-handle validation rejects. Production mints actual handle wrappers via real resolve dispatch (the bridge boundary); zero-LLM tests can't reproduce that without re-introducing bucket-shaped fixtures. **DEFER PERMANENTLY** — this test class belongs in scripted/live tier, not zero-LLM. Per F5 above.

**testUr19RecordArgsRejectsForgedHandle** (url-refs-b.mld, recordArgs validator): asserts that `@compileRecordArgs` rejects a "forged" resolved-handle that doesn't exist on any shelf. Pre-Stage-B, the validator (then operating on bucket-shape state) checked handle existence in `state.resolved.<rt>` as part of recordArgs validation. Post-Stage-B, that check moved out of `@compileRecordArgs` into `@lookupResolvedEntry` — recordArgs validation is now strictly shape-checking (record name + no field). **DEFER, REFRAME** — this is intentional rig refactor, not regression. Reframe as a downstream-resolution test that exercises `@lookupResolvedEntry` against a forged handle, then re-add. Test exe preserved in url-refs-b.mld for revival.

**Group D: testUr21..testUr24 (url-refs-b.mld, dispatch integration)**: invoking `@dispatchResolve` from a `role:worker` test exe with a `var tools` catalog tool that has `recordArgs: { message: "slack_msg" }` trips `record arg '_mlld' is missing` inside `@compileRecordArgs`. Sharp repro: when `@compileRecordArgs` is called via the `@dispatchResolve` function-call frame, `@recordArgsSpec.mx.keys` returns `["message", "_mlld"]`; when the same body is inlined in a test exe, it returns `["message"]`. Same code path, only the function-call frame differs. **MLLD-SIDE REGRESSION** — same family as m-4b6f (frame-boundary metadata leaking into the callee). Tracked as **m-e730** (open, with sharp repro). Tests stay deferred until m-e730 lands.

**Slack handle-drift xfail flips** (identity-contracts.mld, `testCrossResolveIdentitySlackHandleDrift` + `testSelectionRefSurvivesHandleDriftSlack`): per F4, slack_msg has no `key:` declaration and shelf defaults to `merge: append`, so identical `.mx.address.key` doesn't collapse. The migration's "central observable milestone" (per migration-plan.md §0.A) needs slack_msg to gain a content-derived `key:` from canonical fact composition (sender, recipient, body) before the xfail flips become observable. **DEFER** — bench-side records change, separate work item. Both test exes preserved in identity-contracts.mld for revival when slack_msg gets a `key:`.

## Remaining work, ranked by leverage

**Likely-mechanical (no blocker beyond writing the code):**
1. **`url-refs-b.mld`** — PARTIAL (committed in 7578afc). 7/12 tests landed (Group B + Group C minus UR-19). Group D (UR-21..24, dispatch integration) deferred — `@dispatchResolve` from a role:worker test exe trips "record arg '_mlld' is missing" inside the recordArgs validator (likely the `var tools` declaration injects `_mlld` into the catalog and validation iterates ALL keys). UR-19 (forged-handle rejection) deferred — pre-Stage-B's recordArgs validated handle existence; post-Stage-B that moved to @lookupResolvedEntry, so the test needs reframing as a downstream-resolution test. Test exes preserved in file for fast revival.
2. **`proof-chain-firewall.mld`** (536 lines, 17 tests) — pure compile-test file, no scripted-LLM. 11 module-scope `var` consumers of `@sampleState`. Pull all module-scope dispatch results into per-test `role:worker` exe bodies that build their own shelf-bound agent (mirror identity-contracts/url-refs-b/named-state-and-collection per-test pattern). Module-scope role:worker calls are untested in mlld and likely don't have role context, so per-test is the safer pattern. **Watch**: don't alias record imports — `as record @alias` bakes alias into `.mx.address.record` and fails shelf-write (caught in url-refs-b conversion).
3. **3 ARCHITECTURE.md doc updates** (rig, bench, labels-policies-guards) — pure docs. Should describe: shelf as resolved-record store; type:string,kind vs type:handle principle (per audit); planner-shelf threading; removed bucket primitives; m-shelf-wildcard primitive integration.

**Architectural / requires design (not mechanical):**
4. **Task #17: shelf-aware seed for scripted-LLM tests (mock-llm.mld).** Unblocks: mutation matrix re-baseline (3 fixture-fails clear), scripted-suite seed-resolved tests (security-banking B3 etc.), most of `worker-dispatch.mld` conversion. **The fix: `@runWithState` (and `@runScriptedQuery`) in `tests/lib/mock-llm.mld` declare a shelf inline mirroring `@runPlannerSession`'s body, thread it onto the agent before the `@mockOpencode` call.** ~20 lines per consumer, mirroring planner.mld:1256.

   Why inline (not a helper): shelves have scope-local lifetime per m-box-shelf — `shelf @x from ...` must live at the call-site scope. Can't factor into a helper that returns the agent (shelf dies on return). Same pattern as the c7ad4c8 batch, applied to the scripted-LLM scaffold instead of zero-LLM tests.

   **DO NOT** add a hook to the `@planner` session schema. Sessions and shelves are different primitives that happen to share lifetime in the planner case. Coupling them on the session primitive makes future non-shelf agents harder. Push back if this comes up.

   **Scope discipline**: ~20 lines mirroring `@runPlannerSession`. If it grows beyond that — refactoring the session primitive, adding cross-cutting test infra, etc. — stop and reconsider scope.

**Likely-blocked-on-#17:**
5. **`worker-dispatch.mld`** — 577 lines, mostly `exe llm` scripted-LLM. Post-dispatch `state.resolved.*` reads everywhere. Some non-scripted tests may be convertible standalone; needs assessment.
6. **`security-fixtures.mld` shelf-resolved fixtures + 4 scripted suite consumers** — direct dependency on #17.

**Suggested order**: #1, #2, #3 (parallel-ish — test conversions don't change rig, so docs are stable). DO NOT parallelize #3 against #4 — task #4 lands scaffolding details the docs need to describe accurately. After #1-3: #4 (the architectural unblock) → #5, #6 (mechanical once #4 lands) → mutation matrix re-baseline → close.

**Effort sanity check**: ~2-3 sessions. Session A: #1 + #2 + #3 in parallel. Session B: #4 (scoped tight per task #17 description). Session C: #5 + #6 + mutation re-baseline + closeout.

---

## Session 2026-05-08 (stage-b-completion-1) findings

### Records audit landed (LOAD-BEARING for everything else)

8 output records reshaped from `id_: { type: handle, kind: ... }` → `id_: { type: string, kind: ... }`:
- workspace: email_msg, calendar_evt, file_entry
- banking: transaction.id, scheduled_transaction.id
- slack: url_ref.id_, referenced_webpage_content.id_
- travel: calendar_evt.id_

9 input records keep `type: handle` (correct — input records validate LLM-emitted handles via the bridge). 

**Architectural principle (now load-bearing)**: `type: handle` = session-local authorization proof (bridge-minted). `type: string, kind: "X"` = authoritative ID with cross-call identity. `.mx.address.key` = stable lookup address. Output records use string-with-kind; input records use handle. Conflating them was the original blocker that surfaced post-Stage-B because shelf validates strictly. See "Background" below for full thread.

### Files converted (4) — full pass with shelf-shape patterns

1. `xfail-and-null-blocked.mld` — UH-1 dropped (out-of-scope per user; track c-bd28 separately). NF + BFH groups intact.
2. `extract-derive-and-execute-compile.mld` — stub agent `{ records: {}, plannerShelf: undefined }` works for tests that only hit extracted/derived (not selection/resolved) refs.
3. `named-state-and-collection.mld` — 7/11 tests converted. **4 dispatch-composition tests deleted with comments**: testExecuteResultHandlesFromReturnsRecord (returns:-shelf-writeback hits role-context bug — see below); testRescheduleDispatchSucceeds + testCollectionDispatchPolicyBuild + testCollectionDispatchCrossModuleM5178 (event_id flowing from resolved-record to handle-typed input now requires real resolve dispatch to mint handles — end-to-end territory, not zero-LLM).
4. `identity-contracts.mld` — rewritten as 5 shelf-shape tests. **slack handle-drift xfail flips DEFERRED**: needs `key:` declaration on slack_msg derived from canonical (sender, recipient, body) for shelf field-merge to apply. Without `key:`, identical `.mx.address.key` produces 2 separate entries, not 1. This is a bench-side records change beyond test conversion scope. Cross-suite-sentinel + entry-shape-bucket groups dropped (tested deleted `_rig_bucket: "resolved_index_v1"` shape).

### Files deleted (2) — concept obsoleted

- `state-projection-a.mld` and `state-projection-b.mld` DELETED. 100% test surface targeted bucket helpers (@mergeResolvedEntries, @batchSpecMergeState, @bucketItems, @cachedPlannerEntries) that no longer exist. Structural properties (dedup by handle, partial-field merge, parallel-batch accumulation, per-key cache invalidation) now provided by `@shelf.write` directly and tested by shelf-integration.mld groups 1 (box-shelf-lifetime), 3 (shelf-parallel), 4 (projection-cache-per-key).

### Real findings worth surfacing to mlld-dev / next session

**1. Stage B role-context propagation bug (BLOCKS testExecuteResultHandlesFromReturnsRecord and probably worker-dispatch.mld scripted-LLM tests).** When a test exe (role:worker) calls `@dispatchExecute` (role:worker) which calls `@compileForDispatch` (role:planner) which returns, subsequent `@writeRecordsToShelf` inside `@dispatchExecute` body fires `WRITE_DENIED_NO_ROLE` with `activeRole: role:planner`. The role context appears to taint forward across the sub-call return. **Naive `role:worker` decl on `@writeRecordsToShelf` regresses banking scripted** (`updateUserInfoExtractedAcceptedAtRehearse` flips PASS→FAIL). Needs mlld-side review of role-context propagation through `exe role:X` boundaries. Verified with minimal probe (probe-role.mld, since deleted).

**2. slack_msg needs content-derived `key:` declaration for the migration milestone xfail flip.** Per the audit, slack_msg has no `key:` field; @shelf.write produces a fresh entry per call even when `@r1.mx.address.key == @r2.mx.address.key`. Without `key:`, shelf can't field-merge. The handle-drift case stays observably broken until slack_msg gets a content-derived key (e.g. `key: [sender, recipient, body]` or a synthesized canonical fact field).

**3. Cross-tool dispatch composition tests (input-handle validation) belong in scripted/live, not zero-LLM.** Tests that thread `event_id: { source: "resolved", record: "calendar_evt", handle: ..., field: "id_" }` to a write tool whose input record requires `event_id: { type: handle }` will fail post-audit because resolved-ref returns string id_, not a handle. Production works because resolve dispatch mints real handles before execute; tests can't reproduce that without running real dispatch.

### Conversion patterns proven this session

- **Build inline test agents with shelf in caller scope**, return `{ suite, defense, records, plannerShelf, tools, toolsCollection, basePolicy }` plus any test-specific bindings. Don't try `@rigBuild`; it doesn't construct a shelf.
- **Pre-bind `@shelfRecords()` via `let`**: `shelf @ps from @shelfRecords(@recs)` doesn't parse. Two lines: `let @shelfable = @shelfRecords(@recs); shelf @ps from @shelfable with { ... }`.
- **Mint wire-format handles via `r_<rt>_@rec.mx.address.key`** when a test needs to thread a stable handle to a downstream call (parse-value pattern).
- **Stub fixture exes that produce records for shelf-write need `=> <recordName>` arrow** (without it, the value is plain JSON without factsources, and shelf-write rejects with `SHELF_FACT_PROOF_REQUIRED`).

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

- **Phase**: Phase 2 Stage B partial verification surface landed (uncommitted as of session 2026-05-08).
- **Latest commits**: `485bb88` (scaffolding) → `c7ad4c8` (Stage B core) → `eb8bc47` (handoff backfill). **Session 2026-05-08 stage-b-completion-1 work uncommitted: records audit + 4 file conversions + 2 deletes.**
- **Pinned binary**: REMOVED. System mlld v2.0.6.
- **Architecture**: shelf decl in `@runPlannerSession` body; `@agent.plannerShelf` threaded; Path A wire format via `@stateHandleFromAddress` / `@parseRigHandle`. Output records use `id_: { type: string, kind: ... }` post-audit; input records keep `type: handle`.

## Gate state

| Gate | Result |
|---|---|
| Zero-LLM (2 suites still skipped: worker-dispatch, proof-chain-firewall; url-refs-b PARTIAL) | **214/0/1** (was 169/0/1 baseline) |
| Mutation matrix | NOT YET RE-BASELINED (3 baseline fails persist; clearing them depends on task #17) |
| Scripted banking | 7/3 (baseline; B3 + 2 correlate fails — fixture/shelf-seed gap) |
| Scripted slack | 13/1 + 1 xpass (baseline; 1 selection-ref fail — same gap) |
| Scripted workspace | 13/1 (1 extract-empty fail — same gap) |
| Scripted travel | 10/0 (clean) |

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
