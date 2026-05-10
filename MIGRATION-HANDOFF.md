# Migration Handoff

Session breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end. For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state (2026-05-10)

**Gate**: 261/0/2 (the 2 xfails are c-9999 placeholders, not migration tests). Worker-dispatch suite (+20 tests) wired back into `tests/index.mld` after Task #6 conversion.
**Scripted suites at baseline**: banking 7/3, slack 13/1+1xpass, workspace 13/1, travel 10/0.
**Architecture**: Stage B core landed; `state.resolved` retired; shelf is the resolved-record store via `@agent.plannerShelf`. m-shelf-wildcard + m-rec-perms-update fully consumed.

## What's next

**Plan for the batch from the start.** Phase 2 plan calls for Task #7 + Phase 2 closeout gates as one commit class. Don't split mid-session — write fixture migrations + mutation matrix re-baseline + per-key cache test + xfail strips + slack security canary + bench utility sweep into a single coherent landing. Estimated 2 sessions if batched, 3 if not.

1. **First commit before site conversions: strip the slack xpass marker.** `testInstructionChannelLabelNotPromoted` in `tests/scripted/security-slack.mld:679` is grouped with `xfail: true` (ticket c-fb58) but currently passes — Phase 2 structural milestone. Flip the group's `xfail: true` flag (line 680) and verify the test moves from xpass to pass. Standalone commit, separate from any site conversion. Do NOT conflate with `testCrossResolveIdentitySlackHandleDrift` / `testSelectionRefSurvivesHandleDriftSlack` — those are deferred because `slack_msg` needs a content-derived `key:` declaration (bench-side records work, different gate; see "Deferred test classes" below).

2. **Task #7 — fixture migration** (~1-2 hours). 13 sites across 4 scripted suite files use `@stateWithResolved` (deprecated as of `10bfc7e`) or inline bucket entries. Per-site shape: real `@dispatchResolve` script step OR `role:worker` test exe + inline `@shelf.write`. Site count by suite: banking 3, slack 6, workspace 2, travel 2. Banking baseline currently 7/3 — the 3 correlate fails surface as "minted 0 handles" fixture-level errors, confirming the work is fixture-side. **The work should be mechanical.** If a site fails in a shape that doesn't match the bucket→shelf conversion template (handoff §"Conversion template"), that's a real finding — bounded 30-min investigation window, then file an mlld ticket if upstream. Don't paper over with workarounds.

3. **Task #8 — Phase 2 closeout gates** (in same commit class as #7). Per migration-plan.md Phase 2 gate list:
   - Mutation matrix re-baseline: `tests/run-mutation-coverage.py` → `Overall: OK`, capture in `tests/baselines/mutation-matrix.txt`.
   - **Per-key cache invalidation test**: check `tests/rig/shelf-integration.mld` groups 1, 3, 4 first — they may already cover this property under different names. If covered, cite the existing test in the gate doc rather than writing a duplicate. Phase 2 plan calls for "explicit synthetic test"; the gate may already be met structurally.
   - xfail markers stripped from `tests/rig/identity-contracts.mld` for handle-drift cases that now pass uniformly (Phase 2 plan §0.A.4).
   - Slack security canary: `gh workflow run bench-run.yml -f suite=slack -f attack=direct` + `important_instructions`; expect 0 ASR.
   - Bench utility floor: full 4-suite sweep within ±2 of 78/97 baseline.

4. **Phase 3** — `c-8ffd` (mixed authority) lands first as its own commit, then planner prompt revision with bench-sweep before/after numbers (separate commit), then remaining doc pass.

**Discipline reminder for ticket-state uncertainty.** When a previous handoff carries an mlld ticket reference and you can't immediately verify its state, verify (read the ticket file, confirm the fix commit) before your handoff lands — don't carry the question forward. "Ticket I'm not sure about" is exactly the kind of stale cruft the no-fixed-bug-history rule targets.

---

## Conversion template (reference for #6 + #7 + future shelf-shape work)

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

**Required gotchas**:

- Shelf scope expires at exe-body exit. Each test exe declares its own shelf inline.
- Records used in shelves need `write: { role:worker: { shelves: { upsert: true } } }`.
- `@shelfRecords()` filters out input-only `*_inputs` shapes (`direction != "output"`). Don't use `from @records` directly.
- Agent threads as first arg: `@compileExecuteIntent`, `@compileToolArgs`, `@compileRecordArgs`, `@resolveRefValue`, `@lookupResolvedEntry`.
- Test exes calling `@shelf.write` need `role:worker`.
- `let @x = @shelf.write(...)` — bare statement is rejected.
- `var` not allowed inside block bodies. Use `let`.
- Parameter named `shelf` shadows the `@shelf.*` global API. Use `ps` / `slotRef` / etc.
- `state.resolved` is gone. Replace with `@agent.plannerShelf.<rt>` slot ref OR `@shelf.read(@agent.plannerShelf.<rt>)` array.
- **Helpers can't return populated agents.** Shelf reference dies across exe boundaries. Pattern: shelf decl in caller's body; helper takes slot ref(s) as params and writes to them.
- `tests/fixtures.mld` records need `write:` blocks too (already added to existing fixtures; add when authoring new ones).
- `projection_cache:` array must list every role the test asserts through.
- Don't alias record imports: `import { @url_ref as @x }` then `as record @x` bakes the alias into `.mx.address.record` and shelf.write rejects.

## State shape

`{ extracted, derived, extract_sources }` — shelf is in scope via `@agent.plannerShelf`, not part of state. Phase results return `entries: @recordValues[]`; the caller writes to shelf.

## Deferred test classes (preserved in source files; not migration-blocking)

- **Cross-tool dispatch composition** in `named-state-and-collection.mld` — DEFERRED PERMANENTLY to scripted/live tier (per F5 in `bench/ARCHITECTURE.md` "Test tier boundaries"). Production mints handles via real `@dispatchResolve`; zero-LLM can't reproduce without deep stubbing.
- **`testUr19RecordArgsRejectsForgedHandle`** — REFRAME: handle-existence check moved from `@compileRecordArgs` to `@lookupResolvedEntry`. Test preserved in `url-refs-b.mld` for revival as a downstream-resolution test.
- **`url-refs-b.mld` Group D (`testUr21..testUr24`)** — was blocked on m-e730 (FIXED). Should revive mechanically (~15 min add-on for whoever's next in url-refs-b).
- **`testCrossResolveIdentitySlackHandleDrift` + `testSelectionRefSurvivesHandleDriftSlack`** — DEFER: needs `slack_msg` to gain a content-derived `key:` from canonical fact composition (sender, recipient, body). Bench-side records change; preserved in `identity-contracts.mld`.

---

## Sessions log

| Date | Session | Commit | Net |
|---|---|---|---|
| 2026-05-07 | phase-0-A invariants | `01698fa` | tests added |
| 2026-05-07 | phase-1 main | `bbf2e7d` | rename + write: |
| 2026-05-08 | stage-b-core | `c7ad4c8` | -430 lines bucket helpers |
| 2026-05-08 | migrator-2 (records audit + conversions) | `744ba93` | gate 169→194 |
| 2026-05-09 | migrator-2 (identity-contracts + writeback) | `5c229ad` | gate 194→207 |
| 2026-05-09 | migrator-2 (url-refs-b B+C) | `7578afc` | gate 207→214 |
| 2026-05-09 | migrator-2 (null-conformance suite) | `6196ed0` | gate 217→229 |
| 2026-05-09 | migrator-3 Session A (proof-chain-firewall) | `e5d3c21` | gate 229→241 |
| 2026-05-09 | migrator-3 Session A (docs + archive) | `3151e88` | doc closeout |
| 2026-05-09 | migrator-3 Session B Task #17 (mock-llm + dispatch role:worker) | `d78dc3d` | mock-llm shelf seed |
| 2026-05-09 | migrator-3 Session B (security-fixtures cleanup) | `10bfc7e` | bucket-era stripping |
| 2026-05-10 | Task #6 worker-dispatch conversion | (pending commit) | gate 241→261 (+20 tests) |
