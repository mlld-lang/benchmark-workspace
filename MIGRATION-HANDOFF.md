# Migration Handoff

Session breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end. For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state (2026-05-09)

**Gate**: 241/0/2 (the 2 xfails are c-9999 placeholders, not migration tests).
**Scripted suites at baseline**: banking 7/3, slack 13/1+1xpass, workspace 13/1, travel 10/0.
**Architecture**: Stage B core landed; `state.resolved` retired; shelf is the resolved-record store via `@agent.plannerShelf`. Output records `id_: { type: string, kind: ... }`; input records `type: handle`. m-shelf-wildcard + m-rec-perms-update fully consumed.

## Open mlld tickets (pointer only — see ~/mlld/mlld/.tickets/)

- `m-a582` — in_progress; Class 2 metadata-preservation; do not migrate Class 1 sites until landed.
- `m-b61d` — open (resolved in mlld working tree); session-seeded shelf bridge writes.

## What's next

1. **Task #6 — `tests/rig/worker-dispatch.mld` conversion** (~1-2 hours). 577 lines, mostly `exe llm` scripted-LLM with post-dispatch `state.resolved.*` reads. Convert with the mock-llm shelf scaffold from `d78dc3d` and the conversion template below.
2. **Task #7 — fixture migration** (~1-2 hours). 13 sites across 4 scripted suite files use `@stateWithResolved` (deprecated as of `10bfc7e`) or inline bucket entries. Per-site shape: real `@dispatchResolve` script step OR `role:worker` test exe + inline `@shelf.write`. Site count by suite: banking 3, slack 6, workspace 2, travel 2. These are the current pre-existing baseline fails; migrating clears them.
3. **Task #8 — mutation matrix re-baseline** (~10 min, post-#7). Verify `Overall: OK` on `tests/run-mutation-coverage.py`; capture in `tests/baselines/mutation-matrix.txt`.
4. **Phase 3** — `c-8ffd` (mixed authority) lands first as its own commit, then planner prompt revision with bench-sweep before/after numbers (separate commit).

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
