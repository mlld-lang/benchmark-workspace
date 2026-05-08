# Migration Handoff

Session-passing breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end. **Keep terse — under 30 lines.**

For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state

- **Phase**: Phase 1 fully landed and closed. All gates green. Ready for Phase 2.
- **Commits**: `01698fa` (0.A) → `f58ddad` (0.B) → `bbf2e7d` (Phase 1 main) → `694c9cd` (Phase 1 closeout: banking description + test error code).
- **Pinned binary**: REMOVED. System mlld v2.0.6 (current main with m-rec-perms-update + m-shelf-wildcard) is the binary.

## Gate state (post-Phase-1)

| Gate | Result |
|---|---|
| Zero-LLM (`mlld tests/index.mld`) | 270 pass / 0 fail / 5 xfail |
| Mutation matrix (`tests/run-mutation-coverage.py`) | all 11 mutations OK; Overall OK |
| Scripted banking | 9 pass / 0 fail |
| Scripted workspace | 14 pass / 0 fail |
| Scripted slack | 14 pass / 0 fail / 1 xfail (c-fb58, pre-existing) |
| Scripted travel | 10 pass / 0 fail |

The 5 xfails in zero-LLM are the handle-drift bug-class markers in identity-contracts that flip to xpass at Phase 2.

## Tickets

- **m-ed0b** (mlld): policy.build returns valid:false in role-scoped exe wrappers post-m-rec-perms-update. Resolved by Phase 1 (clean-side write: declarations on input records). **Can close.**
- **m-68b6** (mlld): MCP camelCase method names not resolving. **CLOSED — not an mlld bug.** Default scripted-index.mld imports workspace tools causing listFiles to dispatch against a non-workspace MCP server. Per-suite indexes already exist; mutation runner uses them correctly. The actual clean-side error after fixing index mismatch was a `.write` interpolation bug in a description string, fixed in Phase 1 closeout.

## What's still pending

Phase 1 deferred items (low-priority cleanups; gates already green without them):

- Output records' `write: { role:worker: { shelves: true } }` — spec §1.B item; not blocking gates but cleaner. Add when needed.
- `rig/orchestration.mld` policy synth read from `write:` declarations (currently still works via `can_authorize` fallback).
- Phase 1.A.2 comment-header refresh (separate follow-up commit per the comment refresh discipline).

## What's next

**Phase 2 (bucket → shelf collapse)** is the next major work. Per migration-plan.md §2.

### Pre-flight done in this session

- ✅ Output records have `write: { role:worker: { shelves: true } }` declared (commit `50418dc`). Without this, every Phase-2 resolve hits `WRITE_DENIED_NO_DECLARATION` at first MCP boundary crossing.
- ✅ Bounded-shelf semantics verified: `shelf @x from @recordSet` rejects out-of-scope record-type writes with `MlldSecurity: Record '@X' is not in scope for wildcard shelf '@Y'` (probe at `/tmp/probe-shelf-bounded.mld`).
- ✅ Field-level merge + versioning verified: same-`.mx.key` writes collapse to one entry; `slot.mx.version` and `shelf.mx.version` increment per content-changing write (probe at `/tmp/probe-shelf-merge.mld`).

### State.resolved consumer inventory (migration map)

**Delete per spec** (defined in `rig/runtime.mld`):

| Function | Replacement |
|---|---|
| `@mergeResolvedEntries`, `@mergeEntryFields`, `@mergeFieldDict` | shelf upsert with field-level merge default |
| `@stateHandle`, `@stateKeyValue`, `@recordIdentityField` | `.mx.key` (m-d49a) |
| `@isResolvedIndexBucket`, `@bucketObject`, `@bucketItems`, `@bucketLength`, `@indexedBucketEntries` | shelf read API: `@s.<slot>`, `@s.<slot>.length`, `@s.<slot>.byKey(<k>)` |
| `@cachedPlannerEntries`, `@populatePlannerCache` | shelf `projection_cache:` attribute |
| `@normalizeResolvedValues` | shelf does this on write |
| `@updateResolvedState`, `@updateResolvedStateWithDef`, `@batchSpecMergeState` | `@shelf.write(@s.<slot>, @entry)` |
| `@projectResolvedSummary`, `@projectResolvedEntry`, `@projectResolvedFieldValue` | `@fyi.shelf.<alias>` (bridge projection) |

**Source files materially changed**:
- `rig/runtime.mld` — bulk of deletions
- `rig/intent.mld` — bucket walks → shelf reads (lines 239, 263, 950-996)
- `rig/transforms/url_refs.mld` — `@updateResolvedStateWithDef` callsite + url_refs typed-shelf migration
- `rig/workers/{resolve,derive,execute,planner}.mld` — entry envelope construction → shelf upsert
- `rig/session.mld` — shelf decl gains `from @agent.records with { versioned: true, projection_cache: ["role:planner"] }`

**Test files needing update**:
- `tests/rig/identity-contracts.mld` (Phase 0.A invariants — 5 xfails) — convert fixtures to shelf writes; the 2 handle-drift xfails should flip to xpass at conversion. Remove `xfail: true` flags in the same commit per migration-plan.md §2 gate.
- `tests/rig/state-projection-a.mld`, `state-projection-b.mld`, `named-state-and-collection.mld`, `thin-arrow-and-display.mld`, `worker-dispatch.mld`, `xfail-and-null-blocked.mld` — direct bucket access → shelf API.

### Phase 2 commit shape

Per the plan: 2.A core + 2.B consumer migration + 2.C identity-heuristic cleanup. Can split or land as one. The synthetic per-key cache invalidation test (Phase 2 gate item) should be added to `tests/rig/identity-contracts.mld` at conversion time — easiest seam since the file already covers shelf-shape entry contracts.

Architecture doc updates land alongside the Phase 2 commit per discipline:
- `rig/ARCHITECTURE.md` phase model + state model rewritten (bucket → shelf historical)
- `bench/ARCHITECTURE.md` "What stays / What goes" updated
- `labels-policies-guards.md` bucket framing → shelf framing

## Notes for next agent

### Phase 2 readiness (added pre-phase-2-recon, 2026-05-07)

This session probed shelf semantics and surveyed all consumers but did NOT
touch code. Findings the next agent should not re-derive:

**Shelf primitive verified working in v2.0.6**:
- `shelf @x from @records with { versioned: true, projection_cache: ["role:planner"] }` — declares wildcard shelf bounded to record set.
- Field-level merge by `.mx.key` collapses same-key writes (verified: two writes for `name="Hotel X"` with different fields merged to one entry with merged fields).
- `@plannerState.hotel.mx.version` and `@plannerState.mx.version` work (slot + shelf rollup).
- `@shelf.read(@s.<slot>)` returns plain array of records.

**Shelf gaps vs spec assumptions**:
- `@s.<slot>.byKey(<k>)` mentioned in `migration-plan.md` §2.A and `mlld howto shelf-slots` is **not implemented in v2.0.6** — calling it produces `Method not found: byKey`. Lookups must be done via filter on `@shelf.read(...)` or via `@shelf.remove(@s.<slot>, <k>)` (which IS implemented per howto). Per-key cache invalidation is internal — the API surface for direct key lookup needs a workaround OR a follow-up against mlld.
- Probe at `/tmp/probe-shelf-bykey.mld` reproduces the error.

**Wire-format handle question** (UNRESOLVED — needs decision before cutover):
- Current handle format: `r_<recordType>_<keyValue>` (e.g. `r_hotel_HotelX`). Minted by `@stateHandle()`; serialized into refs as `{ source: "resolved", record: "<type>", handle: "<h>", field: "<f>" }`; planner LLM produces and consumes these strings.
- Post-shelf: `.mx.key` is a content-derived hash (`367b05bc` etc.) for keyed records, NOT the readable key value.
- Two paths: (A) keep wire-format `r_<type>_<key>` synthetic and derive it from `.mx.key` at construction time so planner prompt unchanged; (B) switch wire format to `.mx.key` directly and accept the planner prompt drift. Path A is safer for the migration commit; path B is structurally cleaner. Decide before writing any worker/intent code.

### Phase 2 architecture LOCKED (2026-05-08, post-mlld-feature-landing)

The three mlld features (m-box-shelf + m-stable-address + m-shelf-parallel) are
in v2.0.6. All probed working against rig-shaped records:

- **m-box-shelf**: `shelf @x from @records ...` works inside exe bodies (NOT only `box [...]`). Per-call lifetime confirmed (each call gets fresh shelf, version resets). `from @records` binds at call time. Probed at `/tmp/probe-new-1b.mld`.
- **m-stable-address**: `.mx.address.{record,key,string}`, `| @parse.address`, `.byKey()`, `.byAddress()` all work. Address format is `<record>:<.mx.key>`. `.mx.key` for keyed records is content-derived hash (e.g. `Hotel X` → `367b05bc`), not the literal key field. Probed at `/tmp/probe-new-2b.mld`.
- **m-shelf-parallel**: `for parallel(N)` branches see pre-parallel snapshot via `@shelf.read`; writes commit on parallel exit; same-`.mx.key` collisions field-merge across branches. Probed at `/tmp/probe-new-3-parallel.mld`.

**Threading pattern (probed)**:
- Shelf decl in `@runPlannerSession` body
- Augment agent: `let @agent = { ...@rawAgent, plannerShelf: @plannerShelf }`
  (object spread preserves shelf identity — verified at `/tmp/probe-shelf-no-spread.mld`)
- Pass agent through to LLM bridge via existing `seed: { agent, ... }` pattern
- Inside dispatchers: `@planner.agent.plannerShelf.<recordType>` is the slot ref
- Pass slot refs through exe parameters; inner exes can `@shelf.write(@slotRef, @val)` cleanly (verified at `/tmp/probe-shelf-passing.mld`)

**Pitfalls observed**:
- Parameter named `shelf` shadows the `@shelf.*` global API. Use `ps` / `slotRef` / `plannerShelf` etc.
- `@shelf.write(...)` rejected as bare statement. Use `let @x = @shelf.write(...)` or assign to throwaway. Matches existing rig style (`let @next = @updateResolvedStateWithDef(...)`).
- `var` not allowed inside block bodies (e.g. inside `for parallel`). Use `let`.

**mlld bug (REPORT BEFORE STAGE B EXECUTION)**: `shelf @s from @recordsVar` inside an exe body fails with `Record '@hotel' is not defined` (or `Variable not found: <var>`) when that exe is invoked via *indirect* reference — e.g. through `@runSuites([@suite])` which calls test exes by handle, or via `exe @callIt(fn) = [ => @fn() ]; @callIt(@indirectFn)`. Direct calls work; standalone module runs work. The shelf decl's `from <expr>` resolution does NOT appear to capture the defining module's scope across indirect-call boundaries.

Reproducer: `/tmp/probe-wrapper-pattern.mld` + `/tmp/probe-wrapper-B.mld` (also `/tmp/probe-shelf-runner-indirect.mld`). Stage B's planner-loop tools dispatch through the LLM-bridge runtime — that's an indirect call path. **This bug is likely to bite Stage B.** File the mlld ticket and verify it's resolved before starting Stage B implementation, OR design Stage B around the workaround (records inlined into a no-arg wrapper exe defined in the same module as the shelf decl).

### Phase 2 readiness validator (this session)

`tests/rig/shelf-integration.mld` — 16 tests across 4 groups, exercises all three new mlld features against rig-shaped fact-bearing records:
- `box-shelf-lifetime` (4): shelf-in-exe-body, per-call lifetime, slot-ref threading via params, shelf survives object spread
- `stable-address` (8): `.mx.address` contract, `@parse.address` round-trip, `.byKey()` / `.byAddress()` lookups, missing-key returns null, Path A wire-format synthesis (`r_<recordType>_<key>` from `.mx.address`)
- `shelf-parallel` (3): pre-parallel snapshot reads, post-block commit, same-key field-merge across branches
- `projection-cache-per-key` (1): Phase 2 gate per migration-plan §2 — write A, write B, mutate A, B's content unchanged

All 16 pass standalone (`mlld tests/rig/shelf-integration.mld --no-checkpoint`). NOT wired into `tests/index.mld` due to the indirect-call shelf-scope bug above. Wire-up follow-up after the mlld fix.

**Wire-format handle decision LOCKED — Path A**:
- Phase 2 keeps the `r_<recordType>_<keyValue>` synthetic format that the planner LLM currently produces/consumes. New helper: `@stateHandleFromAddress(@val)` returns `r_@val.mx.address.record_@val.mx.address.key`.
- The new read-projection auto-emits `.mx.address` fields in projected records. Planner sees address strings in projections but doesn't act on them. Benign.
- Phase 3.B (planner-prompt revision) flips wire format to `.mx.address.string` directly. Bench-sweep gated.

**Old shelf scope question** (RESOLVED):
- Probed `shelf` declarations inside exe bodies and box bodies — both rejected by parser ("Expected a directive or content, but found 's'"). v2.0.6 only allows `shelf @x = ...` at module scope.
- Module-scope shelf with `@shelf.clear` at start of each call works (probed at `/tmp/probe-shelf-clear.mld`): each call sees its own clean slate, slot version increments globally but that's fine.
- **Caveat**: this conflicts with rig's parallel resolve batch (`@plannerResolveBatch` → `@batchSpecMergeState` per c-eda4). Today, parallel specs run on a snapshot state and return deltas merged sequentially. With a module-scope shelf, parallel specs would race on the same shelf — they can't write concurrently against a snapshot.
- **Implication**: Stage B must change the parallel batch to either (i) return deltas as plain record arrays and serialize the shelf writes after parallel work completes, or (ii) drop parallelism (regresses c-eda4). Path (i) is the correct fix — preserves c-eda4's parallelism, just moves the shelf write outside the parallel section.

**`from @agent.records` binding question** (NEW UNRESOLVED):
- Migration plan suggests `shelf @planner_state from @agent.records with { ... }`. But `@agent.records` is per-rig.run() data, not module-scope; the shelf decl in session.mld can't reference it.
- Options: (A) bare `*` shelf, accept any record type (per spec, allowed but "less safe"); (B) declare the shelf in a per-agent module (e.g. each bench suite's agent.mld imports a `rig/shelf-<suite>.mld` that hardcodes its records — but this introduces N shelf modules); (C) propose a mlld feature for runtime-bound `from <expr>` (out of scope — file an mlld ticket).
- **Recommended**: (A) bare `*` for v1 of the rig migration; security is still record-bound (write: declarations + read: projections enforce per-record). Add a runtime check that incoming records are members of `@agent.records` to compensate for the lost `from <scope>` boundary — this is a plain mlld check, not shelf machinery.

### Per-function migration table (Stage B playbook)

Pre-built so Stage B is pattern-application, not fresh discovery.

| Old API (delete) | Replacement | Notes |
|---|---|---|
| `@stateHandle(recordType, key, idx)` | `@stateHandleFromAddress(@val)` returning `r_<rec>_<.mx.key>` | Path A wire-format preserve |
| `@stateKeyValue(field, value, idx)` | drop — `.mx.key` is the canonical key | |
| `@recordIdentityField(recordDef)` | drop — `.mx.address.record` carries the record type | |
| `@normalizeResolvedValues(rt, rd, raw)` | drop — tool returns are already coerced via `=> @recordDef`; pass directly to `@shelf.write` | bridge already runs coercion |
| `@mergeFieldDict(existing, incoming)` | drop — shelf field-merge is automatic for keyed `record[]` | |
| `@mergeEntryFields(existing, incoming)` | drop — same | |
| `@mergeResolvedEntries(bucket, entries)` | `for @e in @entries [ let @w = @shelf.write(@ps.<rt>, @e) ]` (sequential) or `for parallel` for batch | parallel exercises m-shelf-parallel |
| `@populatePlannerCache(bucket, rt, rd)` | drop — shelf `projection_cache: ["role:planner"]` attribute does this automatically | |
| `@cachedPlannerEntries(bucket)` | drop — shelf cache is internal | |
| `@bucketEntriesForRole(...)` | `for @e in @shelf.read(@ps.<rt>) => @projectResolvedEntry(...)` | bridge applies projection on read |
| `@bucketObject(value)` | drop — shelf reads already return plain arrays | |
| `@bucketItems(bucket)` | `@shelf.read(@ps.<rt>)` | |
| `@bucketLength(bucket)` | `@ps.<rt>.length` | |
| `@isResolvedIndexBucket(bucket)` | drop | |
| `@indexedBucketEntries(bucket)` | drop | |
| `@updateResolvedState(state, rt, entries)` | inline shelf writes | |
| `@updateResolvedStateWithDef(state, rt, entries, rd)` | inline shelf writes; `recordDef` no longer needed (shelf knows from binding) | |
| `@batchSpecMergeState(cumulative, phaseResult, agent)` | drop — `for parallel` with shelf writes does this implicitly | exercises m-shelf-parallel |
| `@phaseResultWithState(...)` | likely drop — phaseResult shape changes (no state.resolved) | |
| `@projectResolvedSummary(records, state, role)` | rewrite around `for @rt, @rd in @records [ for @e in @shelf.read(@ps.<rt>) => @projectResolvedEntry(...) ]` | keep |
| `@projectResolvedEntry(rt, rd, entry, role)` | KEEP — record-bound projection still needed for Path A wire format | input is now plain record (not envelope); rewrite to read fields directly |
| `@projectResolvedFieldValue(entry, fieldName)` | drop — direct field access on records | |
| `@lookupResolvedEntry(state, rt, handle)` | `let @addr = @handle | @parse.address; @ps.<addr.record>.byAddress(@addr)` | parse Path-A handle to address |
| `@resolvedEntries(state, rt)` | `@shelf.read(@ps.<rt>)` | |
| `@resolvedEntryFieldValue(entry, fieldName)` | direct field access on the record value (entry is now the record) | path-traversal helper still needed for nested fields |
| `@compileRecordArgs(...)` JS helper's `entriesOf(bucket)` | rewrite as `@shelf.read(@ps.<rt>)` from mlld side | the JS helper signature changes |
| `state.resolved[rt]` | `@agent.plannerShelf.<rt>` slot ref OR `@shelf.read(...)` array | |

### State shape change

**Before**: `{ resolved: {<rt>: bucket, ...}, extracted, derived, extract_sources, capabilities }`
**After**: `{ extracted, derived, extract_sources, capabilities }` — shelf is in scope via `@agent.plannerShelf`, not part of state.

The state-passing convention through phases stays; just the resolved-bucket field is gone. Phase results no longer return `state_delta.resolved`; instead they return `entries: @recordValues[]` and the caller writes to shelf.

### Per-key cache invalidation test (Phase 2 gate)

Add to `tests/rig/identity-contracts.mld`:

```mlld
exe @testProjectionCachePerKeyInvalidation() = [
  shelf @s from @records with { versioned: true, projection_cache: ["role:planner"] }
  let @w1 = @shelf.write(@s.hotel, @mintHotel("Hotel A", "addr-A"))
  let @w2 = @shelf.write(@s.hotel, @mintHotel("Hotel B", "addr-B"))
  >> Read both — populates cache for both keys
  let @r1 = @shelf.read(@s.hotel)
  >> Mutate ONLY Hotel A (different field)
  let @w3 = @shelf.write(@s.hotel, @mintHotelPrice("Hotel A", "100"))
  >> Hotel B's cache slot should still be hit; Hotel A's invalidated.
  >> Test by reading via role:planner and asserting projection content.
  let @r2 = @shelf.read(@s.hotel)
  >> Assert Hotel A reflects merged content; Hotel B unchanged.
  ...
]
```

Exact assertion shape needs the projection-cache observability decision — if mlld doesn't expose cache-hit/miss directly, the test is content-based (correct merged output proves correct invalidation).

### Stage breakdown for Phase 2 (recommended)

Phase 2 is too tightly coupled to ship in one commit safely. Suggested split:

**Stage A — shelf scaffolding alongside bucket** (small, low risk, gates green):
1. Probe shelf-in-box scoping; pick scope answer.
2. Add shelf decl in chosen location.
3. Write parallel state primitives in `rig/runtime.mld` that operate on the shelf (`@shelfWriteEntries`, `@shelfReadEntries`, etc.). Mirror bucket API surface.
4. NO consumer changes. Bucket primitives still active. Gates pass because nothing uses the new API yet.
5. Commit.

**Stage B — switch consumers + delete bucket** (the load-bearing commit):
1. Decide wire-format handle question (path A or path B above).
2. Replace state.resolved bucket reads with shelf reads in `rig/intent.mld`, `rig/workers/{resolve,derive,execute,planner}.mld`, `rig/transforms/url_refs.mld`.
3. Replace `@updateResolvedStateWithDef` callsites with `@shelf.write(@s.<type>, @recordValue)`. Tool result needs `=> record @recordDef` coercion at the worker boundary (currently it's plain JS-returned data going through `@normalizeResolvedValues`).
4. Update `tests/rig/identity-contracts.mld` xfails (handle-drift cases flip to xpass — remove markers).
5. Update `tests/rig/{state-projection-a,state-projection-b,named-state-and-collection,thin-arrow-and-display,worker-dispatch,xfail-and-null-blocked}.mld` to use shelf API.
6. Delete bucket helpers from `rig/runtime.mld` and `rig/intent.mld` (the ~15 functions listed below).
7. Verify all gates green; bench security canary; ASR=0; utility within ±2 of baseline.
8. Commit. ARCHITECTURE.md updates land in this commit per Phase 2 doc discipline.

**Stage C — `state.capabilities.url_refs` typed shelf** (smaller, can ship separately):
- `state.capabilities.url_refs` → `shelf @url_refs from @url_ref_record` (bounded to single record type per spec).
- Update `rig/transforms/url_refs.mld` (~270 lines, mostly unchanged but the merge/lookup primitives swap).
- Update `dispatchFindReferencedUrls` and `dispatchGetWebpageViaRef` callsites in `rig/workers/resolve.mld`.

### Files materially changed at Stage B (canonical inventory)

| File | LoC | Touch |
|---|---:|---|
| `rig/session.mld` | 33 | Add shelf decl or wire shelf into session shape |
| `rig/runtime.mld` | 1280 | Delete ~30 fns; total shrinks to ~700-800 |
| `rig/intent.mld` | 1163 | Delete bucket walks (lines 63-142, 237-277, 503-538, 943-1015 JS bucket walker); shelf reads replace |
| `rig/transforms/url_refs.mld` | 268 | Stage C |
| `rig/workers/resolve.mld` | 233 | `@normalizeResolvedValues` callsites → `@shelf.write` |
| `rig/workers/derive.mld` | 221 | `@bucketItems(@state.resolved[X])` → `@shelf.read` |
| `rig/workers/execute.mld` | 230 | Same pattern |
| `rig/workers/planner.mld` | 1337 | Lines 248-296 `@plannerResolvedRecords`; lines 243-274 `@stateProgressFingerprint` rewrite (read slot.mx.version + entry.mx.hash directly) |
| `tests/rig/identity-contracts.mld` | 439 | Remove xfails on handle-drift; entry-shape helper handles shelf mode |
| `tests/rig/state-projection-a.mld` | ? | Bucket → shelf API |
| `tests/rig/state-projection-b.mld` | ? | Bucket → shelf API |
| `tests/rig/named-state-and-collection.mld` | ? | Bucket → shelf API |
| `tests/rig/thin-arrow-and-display.mld` | ? | Bucket → shelf API |
| `tests/rig/worker-dispatch.mld` | ? | Bucket → shelf API |
| `tests/rig/xfail-and-null-blocked.mld` | ? | Bucket → shelf API |

### Functions to delete from `rig/runtime.mld` at Stage B

`@recordIdentityField`, `@stateHandle`, `@stateKeyValue`, `@normalizeResolvedValues`, `@cachedPlannerEntries`, `@bucketEntriesForRole`, `@projectResolvedSummary` (rewrite around shelf), `@projectResolvedFieldValue`, `@projectResolvedEntry` (keep — projection still record-bound), `@mergeFieldDict`, `@mergeEntryFields`, `@mergeResolvedEntries`, `@populatePlannerCache`, `@updateResolvedState`, `@updateResolvedStateWithDef`, `@batchSpecMergeState` (rewrite around shelf write API), `@phaseResultWithState` (likely keep), plus exports.

### Functions to delete from `rig/intent.mld` at Stage B

`@bucketObject`, `@isResolvedIndexBucket`, `@indexedBucketEntries`, `@bucketLength`, `@bucketItems`, `@resolvedEntries` (rewrite as shelf read), `@lookupResolvedEntry` (rewrite as shelf-filter or follow-up if mlld lands `byKey`), the JS `@compileRecordArgs`'s `entriesOf` helper (lines 954-963).

### Existing uncommitted files (NOT Phase 2)

`.tickets/c-2ec6.md`, `c-5a08.md`, `c-9c6f.md`, `labels-policies-guards.md`, `rig/workers/planner.mld` (Slice 1 native fingerprint, pre-existing). Plus the COMMENTS-* tracking files. Handle separately.

### Cutover lessons from Phase 1 (still relevant)

- pre-cutover, mlld did not enforce write deny-by-default; post-cutover, every write surface needs explicit `write:` declarations. Test scaffold patterns: tests submitting tools need `exe role:worker @testFoo()` (or `with { read: "role:worker" }` on module-scope vars); tests calling `policy.build` from wrapper exes need `role:planner` to satisfy authorize permission.
- `rig/workers/execute.mld:151` was `exe role:planner` pre-cutover; changed to `role:worker` because the body invokes `@callToolWithPolicy` (worker-side dispatch).
- mlld interprets `@var.field` inside string literals as variable access. Avoid writing record-shape examples like `@record.write: {}` inside descriptions.
- migration-plan.md §1.A documents the third rename axis (role-key prefix); plan adds "Phase 1 is one semantic unit" callout.

## Sessions log

| Date | Session | What landed | Commit |
|---|---|---|---|
| 2026-05-07 | bench-grind-22 | migration plan + archive of old plan | `5516430` |
| 2026-05-07 | phase-0-A | Phase 0.A invariant tests | `01698fa` |
| 2026-05-07 | phase-0-B | Phase 0.B baselines | `f58ddad` |
| 2026-05-07 | phase-1 | Phase 1 main: rename + write: + role refactor; tickets m-ed0b + m-68b6 filed | `bbf2e7d` |
| 2026-05-07 | phase-1-closeout | Banking description fix + update_password test error code; m-68b6 closed (not mlld bug); all gates green | `694c9cd` |
| 2026-05-07 | phase-1-docs | rig/ARCHITECTURE.md role-context section + dispatchExecute load-bearing comment + stranded MUTATION-COVERAGE marker fix | `31992fc` |
| 2026-05-07 | pre-phase-2 (this session) | Output records' write: shelves blocks (26 records); can_authorize transitional comment; Phase 2 pre-flight probes (bounded-shelf rejection, field-merge, versioning) + state.resolved consumer inventory captured in handoff. Mutation matrix Overall OK, zero-LLM 270/0/5. | `50418dc` |
| 2026-05-07 | pre-phase-2-recon (this session) | Reconnaissance only, no code change. Probed: shelf field-merge by `.mx.key` works; `.byKey()` lookup is unimplemented in v2.0.6 (filter-on-read instead). Surveyed all consumers; produced per-file change map and Stage A/B/C breakdown in handoff. Surfaced two unresolved questions: wire-format handle (path A vs B) and shelf scope (module vs box vs exe). | (no commit) |
| 2026-05-08 | phase-2-architecture-lock (this session) | mlld v2.0.6 ships m-box-shelf + m-stable-address + m-shelf-parallel + `.byKey()` / `.byAddress()`. All three probed working against rig-shaped records (probes at `/tmp/probe-new-*.mld`). Architecture LOCKED: shelf in `@runPlannerSession` body, threaded via `@agent.plannerShelf`, Path A wire-format. Per-function migration table written. Stage B execution deferred to next session. | (handoff-only) |
| 2026-05-08 | phase-2-readiness-validator (this session) | Wrote `tests/rig/shelf-integration.mld` — 16 tests across 4 groups validating all three mlld features against rig-shaped records. 16/16 pass standalone. NOT wired into `tests/index.mld` due to indirect-call shelf-scope mlld bug surfaced during wire-up: `shelf @x from @recordsVar` fails when exe is invoked via @runSuites indirection. Bug must be fixed before Stage B (planner-loop tool dispatch is also an indirect-call path). Main gate stays 270/0/5. | (uncommitted) |
