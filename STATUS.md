# Rig v2 Status

Snapshot date: 2026-04-16

This file records where `clean/` stands against [PLAN.md](/Users/adam/mlld/clean/PLAN.md), what is verified right now, and what should happen next.

## Summary

- Step 7 is green and is now pinned by the main rig gate.
- The old `var tools` blocker is gone:
  - domain `tools.mld` files validate directly
  - `var tools` no longer forces suite-local planner/runtime split scaffolding
- All four non-v1 suite agents are back to the intended thin shape:
  - `tools: @tools`
  - `routedTools: @routeToolCatalog(@tools)`
  - `toolsCollection: @toolsCollection`
  - `runtimeTools: null`
- Domain `@toolsCollection` exports are now minimal runtime dispatch collections:
  - `{ tool_name: { mlld: @tool_exe } }`
  - planner/catalog metadata stays on `@tools`
- The rig-internal merge layer is gone:
  - `@mergePlannerCatalog`
  - `@plannerCatalogForAgent`
  - `@routedToolsForAgent`
  - `@mergedToolEntry`
- The old OOM and denial-routing blockers are also closed. There is no remaining runtime workaround tied to them in clean code.

So the repo is past the catalog/runtime cohesion cleanup. The remaining work is bench re-verification, then the record-hardening and final deletion passes.

## Verified Now

These checks were re-run in this snapshot:

- `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/index.mld`
  - `summary: 68 pass / 0 fail`
  - This is the authoritative Step 7 gate.
  - It covers:
    - `CAT-*`
    - `AUTH-*`
    - `POL-ROUNDTRIP-*`
    - `BENCH-CAT-1` through `BENCH-CAT-4`

- `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/bench/tests/catalog-migration.mld`
  - `summary: 10 pass / 0 fail`

- `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/bench/tests/workspace-tools.mld`
  - `summary: 6 pass / 0 fail`

- Direct validate now passes for the domain tool catalogs:
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/workspace/tools.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/banking/tools.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/slack/tools.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/travel/tools.mld`

- Rig internals validate after the merge-helper deletion:
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/rig/tooling.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/rig/orchestration.mld`

## Status Against PLAN

### Steps 1-6

Status: complete enough to build on

- Core resolve / extract / derive / execute flow is in place.
- Policy compilation and display projection are in place.
- The planner/worker loop is no longer carrying catalog-shape workaround logic from the earlier runtime bugs.

### Step 7: Pin policy sections and the transparent catalog surface

Status: complete

Done:

- `rig/tests/index.mld` is green and is the required regression gate.
- `can_authorize` is the authored tool key in clean code.
- The `CAT-*`, `AUTH-*`, `POL-ROUNDTRIP-*`, and `BENCH-CAT-*` regression families are live in the main rig suite.
- Direct validation of the suite domain catalogs now agrees with the runtime shape.
- The prior `var tools` interface gap that forced defensive split-catalog workarounds is closed.

Still worth keeping:

- The negative assertions that the old split helpers do not reappear.

### Step 8: Workspace verification and cleanup

Status: structurally complete, pending bench-path re-verification

Done:

- Workspace write tools are record-backed.
- Workspace adapter regressions are green.
- Workspace agent is thin.
- Workspace no longer carries suite-local runtime merge scaffolding.

Still open:

- Re-run the real workspace canary / harness path in this cleaned shape.

### Step 9: Remaining suites verification and cleanup

Status: structurally complete, pending bench-path re-verification

Done:

- Banking, slack, and travel are on the same thin agent shape as workspace.
- Their domain `tools.mld` files validate directly.
- Their domain `@toolsCollection` exports are minimal runtime collections.
- Suite-local runtime merge scaffolding is gone.

Still open:

- Re-run banking / slack / travel through the real bench path in this cleaned shape.

### Step 10: Make rig read the new shape directly

Status: substantially complete

Done:

- Rig no longer rebuilds planner metadata by merging runtime collections back into the authored catalog.
- The explicit merge helper path has been deleted from `clean/rig/tooling.mld`.
- `clean/rig/orchestration.mld` now carries the runtime collection directly rather than synthesizing a merged planner/runtime catalog.

Still open:

- Remove any remaining legacy fallback reads that only exist for deprecated authored surfaces, especially the old `entry.operation.authorizable` compatibility branch in `clean/rig/tooling.mld`.

### Step 11: Record hardening and sample-quality pass

Status: partially landed

Done:

- Top-level input-record policy sections are live and exercised in the rig invariants.

Still open:

- Trust-refinement pass across suite records using explicit `trusted` / `untrusted` data sections where meaningful
- Handle-typing pass for fact fields that should never accept fabricated plain strings
- Explicit `correlate` choices where authored clarity is better than relying on defaults
- Final sample-quality documentation polish once the bench path has been re-run

### Step 12: Final cleanup and deletion

Status: not complete

Still open:

- Delete the remaining deprecated compatibility reads in rig internals
- Re-run canaries and then the broader bench suite
- Remove any cleanup TODOs that were only waiting on the runtime fixes that have now landed

## Codebase Shape Now

The intended clean split is now:

- `@tools`
  - authoritative planner/catalog surface
  - contains metadata, input records, labels, and `can_authorize`
- `@toolsCollection`
  - runtime dispatch collection only
  - contains `mlld: @exe` entries

That split is intentional and no longer a defensive workaround. It keeps the planner surface rich and the dispatch surface minimal without duplicating schema metadata across both.

The old broken variants are gone:

- no suite-local `runtimeToolsCollection`
- no suite-local `@mergePlannerCatalog`
- no rig-internal planner/runtime merge helper path

## Remaining Deletion Debt

These are the main cleanup targets still worth deleting:

- legacy authored-surface compatibility in `clean/rig/tooling.mld`:
  - fallback reads from `entry.operation.authorizable`
- any residual deprecated terminology in clean docs that is not intentionally historical
- any helper logic that only exists for pre-v2 catalog surfaces once the bench runs are green

## Recommended Next Sequence

### 1. Re-run the real bench path

Do this next, in order:

- workspace canaries
- banking
- slack
- travel

That confirms the cleaned catalog/runtime shape works in the actual harness path, not just the deterministic rig tests.

### 2. Then delete the remaining deprecated compatibility branches

Specifically:

- remove the legacy `entry.operation.authorizable` fallback path from `clean/rig/tooling.mld`
- keep `can_authorize` as the only authored clean-code surface

### 3. Then do the record-hardening pass

- trust refinement
- handle typing
- explicit correlate choices

### 4. Then run the broader suite and close the plan

Once the bench path and hardening pass are green:

- run the broader bench verification
- remove any final stale comments / deletion notes
- mark the remaining cleanup phases complete
