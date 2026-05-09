# Migration Handoff

Session-passing breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end.

For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state (2026-05-09)

**Gate**: 229/0/1 (started at 169/0/1 — +60 tests landed across 2 sessions). The "1" xfail is `template/known-broken/intentionallyFails` (ticket c-9999) — the test framework's own placeholder demonstrating xfailGroup mechanics, not a deferred migration test. Scripted suites at baseline (banking 7/3, slack 13/1+1xpass, workspace 13/1, travel 10/0).

**Committed at 6196ed0**. All previously-uncommitted work from sessions migrator-1 and migrator-2 is now in main. Working tree clean except for the documented pre-existing uncommitted files at the bottom of this doc.

**Architecture**: Stage B core landed; `state.resolved` is gone, shelf is the resolved-record store via `@agent.plannerShelf`; output records use `id_: { type: string, kind: ... }` post-audit; input records keep `type: handle`. m-shelf-wildcard + m-rec-perms-update both fully consumed.

---

## Next priorities (ordered)

### Session A — parallel work, ~3-4 hours total

These don't depend on each other. The two test conversions don't change rig, so the docs are stable; the docs describe production shape that's settled.

1. **`proof-chain-firewall.mld`** (~60-90 min — structurally similar to named-state-and-collection.mld which migrator-2 took longer than 60 min on; 11 module-scope restructures into per-test `role:worker` exes isn't trivially mechanical even with the template proven). Pure compile-test rewrite. 17 test exes, 11 module-scope `var` consumers of `@sampleState`. Pull all module-scope dispatch results into per-test `role:worker` exe bodies that build their own shelf-bound agent (mirror identity-contracts/url-refs-b/named-state-and-collection per-test pattern). Watch: don't alias record imports per F3 below. Hitting friction is normal; not a sign to stop.

2. **`rig/ARCHITECTURE.md`** (~30 min) — phase model + state model rewritten (bucket → shelf historical); list deleted-from-rig functions in migration impact paragraph. **Lift findings F1-F6 below into a permanent "Records primitives" or "Working with shelves" section** — these are records-as-policy principles, not session notes.

3. **`bench/ARCHITECTURE.md`** (~20 min) — "What stays / What goes" table reflects bucket no longer existing. Same F1-F6 promotion target.

4. **`labels-policies-guards.md`** (~30 min) — bucket framing → shelf framing; handle-string identity → `.mx.key`.

### Session B — architectural unblock + cleanup, ~3-4 hours

5. **Task #17: shelf-aware seed for scripted-LLM tests (`tests/lib/mock-llm.mld`).** ~1 hour.

   **Files + lines**:
   - Source-of-truth pattern: `rig/workers/planner.mld:1242-1315` (`@runPlannerSession` full body — shelf decl + thread onto agent + session bind)
   - Edit target #1: `tests/lib/mock-llm.mld:63 @runWithState(agent, query, script, seedState)` — currently passes `agent` straight into `@mockOpencode`'s `seed:`; needs the shelf decl + agent threading inline before the `@mockOpencode` call
   - Edit target #2: `tests/lib/mock-llm.mld:56 @runScriptedQuery(agent, query, script)` — same shape, no `seedState`

   **The fix**: ~20 lines per consumer mirroring planner.mld:1256. Declare `shelf @plannerShelf from @shelfRecords(@rawAgent.records ?? {}) with { versioned: true, projection_cache: ["role:planner"] }`, then `let @agent = { ...@rawAgent, plannerShelf: @plannerShelf }`, then call `@mockOpencode` with the shelf-bearing agent in the seed.

   For fixture preload of records that USED to live in `state.resolved`: lead with running real `@dispatchResolve` setup steps from the test's script (production path; records enter shelf with proper factsource minting). A direct `@shelf.write` helper IS acceptable as escape hatch for narrow tests where dispatch is not the subject — must use the same `=> record @def + @shelf.write` path production uses, and must label in source as a fixture primitive with a comment naming what production path it bypasses. Don't revive bucket-shaped state.

   **DO NOT** add a hook to the `@planner` session schema. Sessions and shelves are separate primitives that happen to share lifetime in the planner case (per F2 below).

   Scope discipline: ~20 lines for the shelf decl wrapper. If it grows beyond that — refactoring the session primitive, adding cross-cutting test infra — stop and reconsider scope.

6. **`worker-dispatch.mld`** (~1-2 hours, post-#17) — 577 lines, mostly `exe llm` scripted-LLM. Post-dispatch `state.resolved.*` reads everywhere. Convert with the new mock-llm shelf scaffold from #5. Some non-scripted tests may convert standalone earlier; needs assessment.

7. **`security-fixtures.mld` shelf-resolved fixtures + 4 scripted suite consumers** (~30 min, post-#17). Direct dependency on #5.

8. **Mutation matrix re-baseline** (~10 min, post-#7). The 3 baseline-fails (banking B3, slack handle test, workspace extract-empty) clear once the fixture-shelf-seed is in place. `uv run --project bench python3 tests/run-mutation-coverage.py` → verify Overall: OK → capture snapshot in `tests/baselines/mutation-matrix.txt`.

### Phase 3 (separate work, after Stage B closes)

9. **m-8ffd (mixed authority — synthesizedAuthorizations reads catalog can_authorize while policy.build enforces record write:)** should LEAD Phase 3 per advisor. It's a security-posture fix: currently bench tools' two surfaces happen to agree by hand; nothing prevents future drift. **Lands as its own commit, separate from item 10** — bundling means the planner-prompt bench sweep can't attribute which change moved which numbers.

10. Planner prompt revision (per migration-plan §3.B). Bench-sweep before/after numbers in commit message; revert if utility regresses beyond ±2 of baseline.

---

## Open external dependencies (low priority — don't block on)

- **mlld m-3116 (try expression)** → clean **c-cdf5** (task #19). When mlld lands `try`, upgrade `@xfailGroup` to wrap test invocations and classify catchable errors as XFAIL instead of bail. Replaces the current delete-and-comment xfail workaround for the recoverable subset. Hard-security errors (WRITE_DENIED_*, TOOL_AUTHORIZE_*) stay delete-and-comment per m-3116's NOT-catchable matrix. Minor quality-of-life; not blocking the migration.

  **Revival audit grep target when m-3116 lands**: `grep -nE "Stage B follow-up.*deleted|deleted.*conversion" tests/rig/*.mld`. Currently flags:
  - `tests/rig/named-state-and-collection.mld:404` testRescheduleDispatchSucceeds (WRITE_DENIED — stays deleted per F5)
  - `tests/rig/named-state-and-collection.mld:455` testCollectionDispatchPolicyBuild (WRITE_DENIED — stays deleted per F5)
  - `tests/rig/named-state-and-collection.mld:463` testCollectionDispatchCrossModuleM5178 (WRITE_DENIED — stays deleted per F5)
  - `tests/rig/identity-contracts.mld:26` 3 entry-shape-bucket tests (obsolete bucket sentinel, NOT m-3116 territory — already covered by shelf-integration)
  - `tests/rig/identity-contracts.mld:151` no-progress fingerprint anchor (covered by FP-2 in progress-fingerprint.mld)

  The named-state-and-collection deletions are all hard-security (WRITE_DENIED_*), so per m-3116's NOT-catchable matrix they STAY deleted. Identity-contracts deletions are concept-obsolete, also stay. So the actual revival yield from m-3116 is 0 currently-deleted tests — but new tests can use try going forward.

- **mlld m-e5e0 follow-up** (low priority): `@parse.address` wrapped-null comparison ergonomics. Currently using `.isDefined()` workaround; not blocking.

---

## Findings — promote to permanent bench/ARCHITECTURE.md in Session A docs pass

Records-as-policy / shelf-architecture principles, not session notes. Lift to a permanent "Records primitives" or "Working with shelves" section as part of #2/#3 above. **DO NOT leave them as session-log text.**

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
- **DO NOT** add shelf hooks to the `@planner` session schema. Coupling them on the session primitive makes future non-shelf agents harder.

**F3. `as record @alias` bakes the import alias into `.mx.address.record`.** If you `import { @url_ref as @slack_url_ref }` and write `let @r = {...} as record @slack_url_ref`, then `@r.mx.address.record == "slack_url_ref"`, not `"url_ref"`. Then `@shelf.write(@ps.url_ref, @r)` rejects. **Don't alias record imports.** (Filed and fixed as m-0904.)

**F4. Without `key:` declaration, shelf defaults to `merge: append` — even if `.mx.address.key` is identical between writes.** Two writes of the same canonical content produce two slot entries, not one. Either declare an explicit `key:` on records that need merge, or accept append semantics. (Filed at m-f4a0, closed with discoverability notes.)

**F5. Cross-tool dispatch composition (resolved id_ → handle-typed input) belongs in scripted/live tier.** Production mints handles via real `@dispatchResolve`; zero-LLM tests can't reproduce that path without deep dispatch stubbing. Three tests deleted from `named-state-and-collection.mld` per this principle.

**F6. Three mlld bug families fixed during this migration share the same root: frame-boundary metadata leaking into the callee.** m-5b7d (bare-statement role leak), m-4b6f (function-call frame role leak via stale exe labels), m-e730 (function-call frame `_mlld` leak via mx.labels). Pattern: when a sub-call returns, certain wrapper-attached fields propagate into the caller's evaluation context. The wider invariant — "syntactically null = semantically null at every runtime surface" — is now locked by `tests/rig/null-conformance.mld` (12 tests covering wrapper-null, JS-return null, literal-arg null).

---

## Deferred test root-causes (per advisor — surface here, not just in-file)

**testRescheduleDispatchSucceeds, testCollectionDispatchPolicyBuild, testCollectionDispatchCrossModuleM5178** (named-state-and-collection.mld, cross-tool composition): pass `event_id: { source: "resolved", record: "calendar_evt", handle: ..., field: "id_" }` to write tools whose input records require `event_id: { type: handle }`. Post-records-audit, `calendar_evt.id_` is `type: string` (correctly — output records); the resolved-ref returns a string, and input-handle validation rejects. Production mints actual handle wrappers via real resolve dispatch. **DEFER PERMANENTLY** — this test class belongs in scripted/live tier, not zero-LLM. Per F5 above.

**testUr19RecordArgsRejectsForgedHandle** (url-refs-b.mld, recordArgs validator): asserts that `@compileRecordArgs` rejects a "forged" resolved-handle that doesn't exist on any shelf. Pre-Stage-B, the validator (then operating on bucket-shape state) checked handle existence in `state.resolved.<rt>` as part of recordArgs validation. Post-Stage-B, that check moved out of `@compileRecordArgs` into `@lookupResolvedEntry` — recordArgs validation is now strictly shape-checking (record name + no field). **DEFER, REFRAME** — intentional rig refactor, not regression. Reframe as a downstream-resolution test that exercises `@lookupResolvedEntry` against a forged handle, then re-add. Test exe preserved in url-refs-b.mld for revival.

**Group D: testUr21..testUr24 (url-refs-b.mld, dispatch integration)**: previously blocked on m-e730 `_mlld` leak (FIXED). Should now revive mechanically — ~15 min add-on for whoever's next in url-refs-b. Test exes still preserved in url-refs-b.mld; just need to be re-added to the suite construction and re-tested.

**Slack handle-drift xfail flips** (identity-contracts.mld, `testCrossResolveIdentitySlackHandleDrift` + `testSelectionRefSurvivesHandleDriftSlack`): per F4, slack_msg has no `key:` declaration and shelf defaults to `merge: append`, so identical `.mx.address.key` doesn't collapse. The migration's "central observable milestone" needs slack_msg to gain a content-derived `key:` from canonical fact composition (sender, recipient, body) before the xfail flips become observable. **DEFER** — bench-side records change, separate work item. Both test exes preserved in identity-contracts.mld for revival when slack_msg gets a `key:`.

---

## Conversion template (reference for proof-chain-firewall + worker-dispatch)

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
- `@shelfRecords()` filters out input-only `*_inputs` shapes (those have `direction != "output"`). Don't use `from @records` directly when `@records` includes `*_inputs` shapes.
- Signatures changed across these exes — agent now threads as first arg: `@compileExecuteIntent`, `@compileToolArgs`, `@compileRecordArgs`, `@resolveRefValue`, `@lookupResolvedEntry`.
- Test exes calling `@shelf.write` need `role:worker`.
- `let @x = @shelf.write(...)` — bare statement is rejected.
- `var` not allowed inside block bodies (e.g. `for parallel`). Use `let`.
- Parameter named `shelf` shadows the `@shelf.*` global API. Use `ps` / `slotRef` / etc.
- `state.resolved` is gone. Replace with `@agent.plannerShelf.<rt>` slot ref OR `@shelf.read(@agent.plannerShelf.<rt>)` array.

**Gotchas observed prophylactically**:

- **Helpers can't return populated agents — shelf reference dies across exe boundaries.** Pattern that works: shelf decl in caller's body; helper takes slot ref(s) as params and writes to them; helper signature is `(slotRef, ...params) → recordsWritten` not `(...) → agent`.
- **`tests/fixtures.mld` records need `write:` blocks too.** Phase 1 added them to `bench/domains/*/records.mld` but not to test-only records. Already updated: `@contact`, `@note_entry`, `@flat_display_contact`, `@plain_mode_message`, `@aliceContactRecord`, `@bobContactRecord`, `@noteEntryRecord`, `@numberOneRecord`, `@numberTwoRecord`, `@summaryRecord`. Add `write:` + re-export when a converted test imports a new one.
- **Records with `key: <typed-handle-field>` reject string fixture values at shelf-write time** — pre-audit residue, mostly fixed but still a trap if you author a new such record.
- **`projection_cache:` array must list every role the test asserts through.** Missing roles don't cache; behavior may surprise in cache-correctness tests.
- **Don't alias record imports** per F3.

---

## State shape change

**Before**: `{ resolved: {<rt>: bucket, ...}, extracted, derived, extract_sources, capabilities }`
**After**: `{ extracted, derived, extract_sources, capabilities }` — shelf is in scope via `@agent.plannerShelf`, not part of state.

Phase results no longer return `state_delta.resolved`. They return `entries: @recordValues[]` and the caller writes to shelf.

---

## Closeout sequence (after Session B)

After mutation matrix re-baseline, Phase 2 is complete. Phase 3 (planner prompt revision + remaining doc rewrites) is one small follow-up session, with **m-8ffd leading** per advisor. Planner prompt change requires bench-sweep before/after numbers in commit message per migration-plan §3.B.

---

## Pre-existing uncommitted files (NOT migration commits)

Reconciled at session 2026-05-09 freeze — `git status` shows these untracked items, none migration-relevant. Don't accidentally stage during normal migration commits:

- `.claude/skills/migrate/` — local skill directory
- `.mlld-sdk` — local SDK marker
- `comment-audit/` — earlier audit output
- `mlld-bugs.md`, `mlld-security-fundamentals.md`, `plan-tests-framework.md`, `planner-dirty.md` — drafts/notes
- `opencode/` — local opencode state
- `rig/policies/` — early policy spike directory
- `SECURITY-DISCIPLINE.md` — local discipline notes
- `spec-control-arg-validators.md`, `spec-extended-attacks-benchmark.md`, `spec-perf-regression.md`, `spec-url-summary.md` — spec drafts

Earlier session referenced `.tickets/c-2ec6.md`, `c-5a08.md`, `c-9c6f.md`, `labels-policies-guards.md` (display→read pre-rename), `rig/workers/planner.mld` (Slice 1 native fingerprint), `COMMENTS-*` tracking files — those have been resolved in subsequent commits and are no longer untracked. Use `git status` at the start of next session to reconcile if any of the above have been resolved or if new pre-existing items appear.

---

## Sessions log

| Date | Session | Commit | Net |
|---|---|---|---|
| 2026-05-07 | bench-grind-22 (plan) | `5516430` | plan |
| 2026-05-07 | phase-0-A invariants | `01698fa` | tests added |
| 2026-05-07 | phase-0-B baselines | `f58ddad` | baselines |
| 2026-05-07 | phase-1 main | `bbf2e7d` | rename + write: |
| 2026-05-07 | phase-1-closeout | `694c9cd` | |
| 2026-05-07 | phase-1-docs | `31992fc` | |
| 2026-05-07 | output-records write: blocks | `50418dc` | |
| 2026-05-08 | phase-2-readiness | `100a343` | |
| 2026-05-08 | phase-2-handoff-refresh | `9a102c2` | |
| 2026-05-08 | stage-b-scaffolding | `485bb88` | |
| 2026-05-08 | stage-b-core | `c7ad4c8` | -430 lines bucket helpers |
| 2026-05-08 | migrator-2 (records audit + 4 file conversions + 2 deletes) | `744ba93` | gate 169→194 |
| 2026-05-08 | migrator-2 (identity-contracts + JS audit + writeback test revive) | `5c229ad` | gate 194→207 |
| 2026-05-09 | migrator-2 (url-refs-b PARTIAL Groups B+C) | `7578afc` | gate 207→214 |
| 2026-05-09 | migrator-2 (m-60ff correlate opt-in + m-3116 doc) | `71c369c` | gate 214→217 |
| 2026-05-09 | migrator-2 (advisor-gap closure: handoff updates) | `844ea82` | docs |
| 2026-05-09 | migrator-2 (null-conformance regression suite) | `6196ed0` | gate 217→229 |
| 2026-05-09 | migrator-2 (handoff restructure for execution focus) | `f7ab37c` | docs |
| 2026-05-09 | migrator-2 (c-cdf5 ticket filed) | `b1b92ac` | ticket |
| next | Session A: proof-chain-firewall + 3 docs | TBD | gate 229→~244 + docs |
| next+1 | Session B: task #17 + worker-dispatch + fixtures + mutation re-baseline | TBD | full closeout |
