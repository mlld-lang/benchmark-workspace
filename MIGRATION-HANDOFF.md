# Migration Handoff

Session breadcrumb for the records-as-policy + bucket→shelf migration. Read at session start. Update at session end. For the full plan, see `migration-plan.md`. For onboarding, use `/migrate` skill.

---

## Current state (2026-05-10)

**Gate**: 261/0/2. **Scripted baseline**: banking 7/3, slack 13/1+1xpass, workspace 13/1, travel 10/0.
**Architecture**: Stage B core landed; `state.resolved` retired; shelf is the resolved-record store via `@agent.plannerShelf`.

## Blocker on Task #7

**m-6dc0 (filed 2026-05-10)** — adding `role:worker` to ANY exe in a scripted-LLM module regresses unrelated tests in the same module. Repro: 1-line change in `tests/scripted/security-slack.mld` flips `inviteUserKnownInTaskTextAccepted` from PASS to FAIL even though the regressed test carries no role annotation. `compileExecuteIntent ok=true` but downstream layer rejects → likely policy.build module-level role-context leakage. Doesn't affect zero-LLM `tests/rig/*.mld` (those use `exe role:worker @testFoo` freely). Fully blocks the conversion template's `role:worker` test exe pattern in scripted suites.

## What's next

1. **Wait on m-6dc0**, then resume Task #7 Path B (convert all ~10 active sites to real shelf seeds). Site count: banking 3, slack 3 (incl. deferred slack_msg), workspace 3, travel 1.
2. **Per-site Path B discipline** (per user direction this session): if a converted site reveals "passing because empty seed → wrong-layer rejection," re-xfail with a comment naming the actual gap, OR file a separate c-XXXX clean-side ticket if a defense should exist. Don't bundle missing-defense fixes into the migration commit.
3. **Task #8 closeout gates** (in same commit class as #7): mutation matrix re-baseline; per-key cache gate already met (`tests/rig/shelf-integration.mld` Group 4 "projection-cache-per-key" — explicit Phase 2 gate per its own ticket note); strip xfail markers in `tests/rig/identity-contracts.mld` for handle-drift cases that pass uniformly; slack security canary; bench utility 4-suite sweep within ±2 of 78/97.
4. **Phase 3** — `c-8ffd` (mixed authority) lands first as own commit, then planner prompt revision with bench-sweep before/after, then doc pass.

## Conversion template (reference)

```mlld
exe role:worker @testFoo() = [
  let @sh = @shelfRecords(@records)
  shelf @ps from @sh with { versioned: true, projection_cache: ["role:planner"] }
  let @v = { ... } as record @records.<rt>
  let @w = @shelf.write(@ps.<rt>, @v)
  let @handle = `r_<rt>_@v.mx.address.key`
  let @agent = { ...@rawAgent, plannerShelf: @ps }
  ...
]
```

**Required gotchas** (additions in italics):

- Shelf scope expires at exe-body exit; declare inline per test exe.
- Records used in shelves need `write: { role:worker: { shelves: { upsert: true } } }`.
- `@shelfRecords()` filters out input-only `*_inputs` shapes; don't use `from @records` directly.
- Test exes calling `@shelf.write` need `role:worker` (and trip m-6dc0 in scripted-LLM modules).
- `let @x = @shelf.write(...)` — bare statement is rejected.
- `var` not allowed inside block bodies. Use `let`.
- Parameter named `shelf` shadows `@shelf.*` global API. Use `ps` / `slotRef`.
- *Handle derivation: ``r_<rt>_@v.mx.address.key`` (NOT `@w.mx.address.handle` — that field is null).*
- *Use `@records.<rt>` for the record def (avoid module-level individual record imports — verified harmless but redundant).*
- `tests/fixtures.mld` records need `write:` blocks too.
- `projection_cache:` array must list every role the test asserts through.
- Don't alias record imports: `import { @url_ref as @x }` then `as record @x` bakes the alias into `.mx.address.record`.

## State shape

`{ extracted, derived, extract_sources }` — shelf is in scope via `@agent.plannerShelf`, not part of state.

## Deferred test classes (preserved in source files; not migration-blocking)

- **Cross-tool dispatch composition** in `named-state-and-collection.mld` — DEFERRED PERMANENTLY to scripted/live tier (F5 in `bench/ARCHITECTURE.md`).
- **`testUr19RecordArgsRejectsForgedHandle`** — REFRAME: handle-existence check moved from `@compileRecordArgs` to `@lookupResolvedEntry`; preserved in `url-refs-b.mld`.
- **`url-refs-b.mld` Group D (`testUr21..testUr24`)** — was blocked on m-e730 (FIXED). Should revive mechanically (~15 min).
- **`testCrossResolveIdentitySlackHandleDrift` + `testSelectionRefSurvivesHandleDriftSlack`** — DEFER: needs `slack_msg` content-derived `key:` declaration. Preserved in `identity-contracts.mld`.

## Ticket-state discipline

When a previous handoff mentions an mlld ticket and you can't immediately verify its state, verify (read the ticket, confirm the fix commit) before your handoff lands.

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
| 2026-05-10 | Task #6 worker-dispatch conversion | `ca3e3b3` | gate 241→261 (+20 tests) |
| 2026-05-10 | xpass investigation + revert; m-6dc0 filed | `fbd6d58` | xpass corrected |
