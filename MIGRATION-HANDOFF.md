# Migration Handoff

Session-passing breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end.

For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state (2026-05-09)

**Gate**: 241/0/2. The 2 xfails are `template/known-broken/intentionallyFails` and `template/known-broken/intentionallyThrows` (ticket c-9999) — test framework placeholders, not deferred migration tests. Scripted suites at baseline: banking 7/3, slack 13/1+1xpass, workspace 13/1, travel 10/0.

**Session A**: DONE. proof-chain-firewall converted, security doc archived, ARCH docs updated.

**Session B (Task #17)**: DONE. Mock-llm shelf-aware seed shipped; `@dispatchResolve` and the rigTransform dispatchers tagged `role:worker`; security-fixtures bucket-era cleanup.

**Architecture**: Stage B core landed; `state.resolved` is gone, shelf is the resolved-record store via `@agent.plannerShelf`; output records use `id_: { type: string, kind: ... }` post-audit; input records keep `type: handle`. m-shelf-wildcard + m-rec-perms-update both fully consumed.

---

## Next priorities (ordered)

### Session A — DONE except for the closeout commit

1. ~~**`proof-chain-firewall.mld`**~~ — DONE, commit `e5d3c21`. 12 tests added; gate 229→241.

2. ~~**`rig/ARCHITECTURE.md`**~~ — DONE (uncommitted). Added a "State Surface" section cross-referencing `mlld-security-fundamentals.md` §6 (shelves) + §7 (sessions) + §4.4 (identity). Updated "Separation of Concerns" to mention shelf-backed state. Updated the References section to point at `mlld-security-fundamentals.md`. **No F1–F6 promotion** here — content lives in mlld-security-fundamentals.md (cross-reference only), not in rig/ARCHITECTURE.md.

3. ~~**`bench/ARCHITECTURE.md`**~~ — DONE (uncommitted). Fixed stale `display:` / `{ref:}` syntax in the example record. Updated "What Stays / What Goes" to reflect bucket→shelf collapse. Added a new "Records authoring principles" section that cross-references mlld-security-fundamentals.md §4.4–4.7, §6.6, §7 and lists 5 clean-side authoring principles (the F1/F2/F4 content in cross-reference form, plus F3 alias warning). Added a new "Test tier boundaries" section promoting F5 (cross-tool dispatch composition belongs in scripted/live, not zero-LLM) as a permanent principle. Cites the named-state-and-collection.mld deletions as canonical examples.

4. ~~**`mlld-security-fundamentals.md`**~~ — Scope changed (per advisor). The new doc already covers F1/F2/F4 in §4.4–4.7, §6.6–6.9, §7. Session A #4 became `git mv labels-policies-guards.md archive/` + grep stragglers + update them. DONE (uncommitted): `DEBUG.md`, `bench/domains/workspace/records.mld`, `rig/workers/advice.mld`, `migration-plan.md`, `.claude/skills/migrate/SKILL.md` updated.

### Session B — Task #17 DONE; #6 / #7-migration / #8 remain

5. ~~**Task #17: shelf-aware seed for scripted-LLM tests**~~ DONE (`d78dc3d`). `tests/lib/mock-llm.mld` `@runScriptedQuery` and `@runWithState` declare a per-call shelf inline mirroring `@runPlannerSession`. Plus `rig/workers/resolve.mld` tagged `@dispatchResolve` / `@dispatchFindReferencedUrls` / `@dispatchGetWebpageViaRef` as `role:worker`, parallel to `@dispatchExecute`.

   **Files + lines**:
   - Source-of-truth pattern: `rig/workers/planner.mld:1242-1315` (`@runPlannerSession` full body — shelf decl + thread onto agent + session bind)
   - Edit target #1: `tests/lib/mock-llm.mld:63 @runWithState(agent, query, script, seedState)` — currently passes `agent` straight into `@mockOpencode`'s `seed:`; needs the shelf decl + agent threading inline before the `@mockOpencode` call
   - Edit target #2: `tests/lib/mock-llm.mld:56 @runScriptedQuery(agent, query, script)` — same shape, no `seedState`

   **The fix**: ~20 lines per consumer mirroring planner.mld:1256. Declare `shelf @plannerShelf from @shelfRecords(@rawAgent.records ?? {}) with { versioned: true, projection_cache: ["role:planner"] }`, then `let @agent = { ...@rawAgent, plannerShelf: @plannerShelf }`, then call `@mockOpencode` with the shelf-bearing agent in the seed.

   For fixture preload of records that USED to live in `state.resolved`: lead with running real `@dispatchResolve` setup steps from the test's script (production path; records enter shelf with proper factsource minting). A direct `@shelf.write` helper IS acceptable as escape hatch for narrow tests where dispatch is not the subject — must use the same `=> record @def + @shelf.write` path production uses, and must label in source as a fixture primitive with a comment naming what production path it bypasses. Don't revive bucket-shaped state.

   **DO NOT** add a hook to the `@planner` session schema. Sessions and shelves are separate primitives that happen to share lifetime in the planner case (per F2 below).

   Scope discipline: ~20 lines for the shelf decl wrapper. If it grows beyond that — refactoring the session primitive, adding cross-cutting test infra — stop and reconsider scope.

6. **`worker-dispatch.mld`** (~1-2 hours, post-#17) — 577 lines, mostly `exe llm` scripted-LLM. Post-dispatch `state.resolved.*` reads everywhere. Convert with the new mock-llm shelf scaffold from #5. Some non-scripted tests may convert standalone earlier; needs assessment.

7. **`security-fixtures.mld` shelf-resolved fixtures + 4 scripted suite consumers** — partially done.

   `tests/lib/security-fixtures.mld` cleanup landed in `10bfc7e`: `@stateWithExtracted` / `@stateWithDerived` no longer emit deprecated `resolved: {}` and `capabilities: { url_refs: {} }` fields. `@stateWithResolved` and `@stateResolvedAndExtracted` are stubbed to return the post-Stage-B empty state shape with deprecation notes — they no longer construct bucket-shape state.

   **Remaining Task #7 work (~1-3 hours, optional for Stage B closeout)**: 13 sites across the 4 scripted suite files use bucket-shape pre-seeding (inline `_rig_bucket` literals or read `state.resolved.<rt>.by_handle` from a real resolve setup call). Each test that depends on resolved-record handles needs to:

   - convert the test exe to `role:worker`,
   - declare a shelf inline at test-body scope,
   - pass the shelf-bearing agent through a NEW helper (e.g. `@runScriptWithAgent(agent, query, script, state)`) that does NOT redeclare the shelf,
   - read handles via `@shelf.read(@ps.<rt>)` instead of `state.resolved.<rt>.by_handle`.

   Sites by suite: banking 3 (`testUpdateScheduledTxExtractedRecipientRejected`, `testCorrelateCrossRecordMixingDenied`, `testCorrelateSameRecordAccepted`), slack 6, workspace 2, travel 2. **The current pre-existing baseline fails (banking 7/3, slack 13/1+1xpass, workspace 13/1) are these tests** — they were failing before Stage B and continue to fail in the same shape post-Stage-B. Migrating them clears those baseline fails and may flip the slack xpass.

   This is migration completeness work — not Stage B closeout blocking. Defer-or-do is a scope call.

8. **Mutation matrix re-baseline** (~10 min, post-#7). The 3 baseline-fails (banking B3, slack handle test, workspace extract-empty) clear once the fixture-shelf-seed is in place. `uv run --project bench python3 tests/run-mutation-coverage.py` → verify Overall: OK → capture snapshot in `tests/baselines/mutation-matrix.txt`.

### Phase 3 (separate work, after Stage B closes)

9. **c-8ffd (mixed authority — synthesizedAuthorizations reads catalog can_authorize while policy.build enforces record write:)** should LEAD Phase 3 per advisor. It's a security-posture fix: currently bench tools' two surfaces happen to agree by hand; nothing prevents future drift. **Lands as its own commit, separate from item 10** — bundling means the planner-prompt bench sweep can't attribute which change moved which numbers.

10. Planner prompt revision (per migration-plan §3.B). Bench-sweep before/after numbers in commit message; revert if utility regresses beyond ±2 of baseline.

---

## Open external dependencies (low priority — don't block on)

- **mlld m-e5e0 follow-up** (low priority): `@parse.address` wrapped-null comparison ergonomics. Currently using `.isDefined()` workaround; not blocking.

---

## Where the F-findings landed

The records-as-policy / shelf-architecture principles that were holding here as session notes have all been promoted or retired. For future reference:

- **F1 / F2 / F4** (handle vs string-with-kind, sessions vs shelves, key-driven merge semantics) → `mlld-security-fundamentals.md` §4.4–4.7, §6.6, §7. Cross-referenced from `bench/ARCHITECTURE.md` "Records authoring principles".
- **F3** (don't alias record imports) → `bench/ARCHITECTURE.md` "Records authoring principles" §5. Closed mlld bug `m-0904`.
- **F5** (cross-tool dispatch composition belongs in scripted/live tier) → `bench/ARCHITECTURE.md` "Test tier boundaries" section.
- **F6a** (frame-boundary metadata leak class — `m-5b7d`, `m-4b6f`, `m-e730`) → closed mlld bugs; no clean-side doc real estate needed.
- **F6b** (null-conformance invariant) → `tests/rig/null-conformance.mld` is the load-bearing artifact. mlld primitives doc already covers the invariant. No further action.

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

After mutation matrix re-baseline, Phase 2 is complete. Phase 3 (planner prompt revision + remaining doc rewrites) is one small follow-up session, with **c-8ffd leading** per advisor. Planner prompt change requires bench-sweep before/after numbers in commit message per migration-plan §3.B.

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
| 2026-05-09 | migrator-2 (c-60ff correlate opt-in + xfail limitation doc) | `71c369c` | gate 214→217 |
| 2026-05-09 | migrator-2 (advisor-gap closure: handoff updates) | `844ea82` | docs |
| 2026-05-09 | migrator-2 (null-conformance regression suite) | `6196ed0` | gate 217→229 |
| 2026-05-09 | migrator-2 (handoff restructure for execution focus) | `f7ab37c` | docs |
| 2026-05-09 | migrator-2 (c-cdf5 filed → closed; runner.mld try-wrap) | `b1b92ac` + `84a5cd9` | gate 229/0/1→229/0/2 |
| 2026-05-09 | migrator-3 (Session A: proof-chain-firewall conversion) | `e5d3c21` | gate 229→241 |
| 2026-05-09 | migrator-3 (Session A: docs + security-doc archive) | TBD | doc closeout |
| next | Session B: task #17 + worker-dispatch + fixtures + mutation re-baseline | TBD | full closeout |
