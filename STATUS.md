# Rig v2 Status

Snapshot date: 2026-04-17

This file records where `clean/` stands against [PLAN.md](/Users/adam/mlld/clean/PLAN.md), what is verified right now, and what should happen next.

## Summary

- Step 7 is green and pinned by the main rig gate.
- The transparent `var tools` path is now the real path, not a workaround target:
  - suite domain catalogs validate directly
  - imported `var tools` entries preserve metadata and executables across module boundaries
  - flow tests run end to end on the same surfaced catalog shape the bench agents use
- The old planner/runtime split scaffolding is gone from the non-v1 bench agents.
- Bench agents no longer carry the redundant `runtimeTools: null` placeholder.
- The main interface/docs sweep is now aligned with the shipped v2 shape:
  - `inputs` / `returns`
  - `description` / `instructions`
  - top-level policy sections on input records
  - `authorizations.can_authorize` in synthesized policy
- The old runtime blockers that forced defensive catalog handling are closed:
  - var-bound catalog traversal OOM
  - dispatch-time denial routing bypassing `denied =>`
  - wrapped errors losing `originalError`
  - imported `var tools` entries losing `mlld.mx.params`
  - runtime serialization paths walking live `Environment` objects
  - provider login failures masquerading as planner-schema failures in bench results

So `clean/` is past the catalog/runtime cohesion cleanup. What remains is clean bench-path re-verification, then the final hardening audit and deletion sweep.

The current blocker is no longer provider auth. It is a live clean-path runtime failure on the real defended workspace bench path: a resolved `file_entry.id_` ref reaches extract dispatch as `25` instead of the string `"25"`, and the single-arg collection call rejects it before the tool body can normalize it.

## Verified Now

These checks were re-run in this snapshot:

- `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/index.mld`
  - `summary: 75 pass / 0 fail`
  - This is the authoritative Step 7 gate.
  - It covers:
    - `CAT-*`
    - `AUTH-*`
    - `POL-ROUNDTRIP-*`
    - `BENCH-CAT-1` through `BENCH-CAT-4`
    - the array-preview regressions that keep planner summaries structurally usable without leaking payload values

- Rig flow suite:
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/derive.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/execute.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/extract.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/extract_reject.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/extract_state_retention.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/guards.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/resolve.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/rig/tests/flows/smoke.mld`
  - All pass.

- Bench-side migration regressions:
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/bench/tests/catalog-migration.mld`
  - `summary: 10 pass / 0 fail`

- Clean benchmark host regressions:
  - `uv run --project /Users/adam/mlld/clean/bench python3 -m unittest /Users/adam/mlld/clean/bench/tests/test_host.py`
  - `Ran 5 tests in ...`
  - `OK`
  - Includes the auth-classification regressions so provider login failures become `infrastructure_error`, not fake planner/schema failures.

- Workspace adapter regressions:
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs --new /Users/adam/mlld/clean/bench/tests/workspace-tools.mld`
  - `summary: 6 pass / 0 fail`

- Direct validate passes for the suite domain catalogs:
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/workspace/tools.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/banking/tools.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/slack/tools.mld`
  - `node /Users/adam/mlld/mlld/bin/mlld-wrapper.cjs validate /Users/adam/mlld/clean/bench/domains/travel/tools.mld`

- Benchmark host now lives under the clean tree and points at the clean agents:
  - [host.py](/Users/adam/mlld/clean/src/host.py) dispatches to `clean/bench/agents/<suite>.mld`
  - A real defended rerun now hits the clean path instead of the legacy `benchmarks/llm` path

- Clean bench host now runs against the real provider path in `/Users/adam/mlld/clean/bench`:
  - `opencode run --format json --dir /Users/adam/mlld/clean/bench -m openrouter/z-ai/glm-5.1 'Reply with exactly OK.'`
  - returns `OK`
  - So provider auth is no longer the blocker on the clean path.

- Latest clean defended bench-path result:
  - `uv run --project /Users/adam/mlld/clean/bench python3 /Users/adam/mlld/clean/src/run.py -s workspace -d defended -t user_task_25 --debug`
  - Old `tool_entry` collision is gone.
  - Old provider-auth failure is gone.
  - Current blocker is a clean runtime failure during extract dispatch:
    - planner resolves the target file with `search_files`
    - planner then chooses `get_file_by_id` with
      `{ "file_id": { "source": "resolved", "record": "file_entry", "handle": "r_file_entry_25", "field": "id_" } }`
    - rig fails before the tool body runs with:
      `Input validation error: 25 is not of type 'string'`
      from [runtime.mld](/Users/adam/mlld/clean/rig/runtime.mld:795)
      via [orchestration.mld](/Users/adam/mlld/clean/rig/orchestration.mld:276)
  - This is a real runtime bug on the clean bench path, not a provider issue.

## Status Against PLAN

### Steps 1-6

Status: complete enough to build on

- Core resolve / extract / derive / execute flow is in place.
- Policy compilation, display projection, lifecycle logging, and retry guards are in place.
- The main flow suite is green again after the runtime fixes.

### Step 7: Pin policy sections and the transparent catalog surface

Status: complete

Done:

- `rig/tests/index.mld` is green at `71 pass / 0 fail`.
  - now `75 pass / 0 fail`
- `can_authorize` is the authored tool key in clean code.
- The `CAT-*`, `AUTH-*`, `POL-ROUNDTRIP-*`, and `BENCH-CAT-*` regression families are live in the main rig suite.
- Suite domain catalogs validate directly against the v2 shape.
- The flow suite now runs on transparent surfaced `var tools` entries instead of a defensive split-catalog shape.
- Non-v1 bench agents route and dispatch directly from `@tools`.
- The old `entry.operation.authorizable` compatibility read is gone from rig code.

Still worth keeping:

- The negative assertions that deleted helper paths and legacy authored surfaces do not reappear.

### Step 8: Workspace verification and cleanup

Status: structurally complete, bench-path verification still outstanding

Done:

- Workspace write tools are record-backed.
- Workspace adapter regressions are green.
- Workspace agent is thin and dispatches directly from `@tools`.
- Workspace no longer carries a local planner/runtime split catalog.
- Workspace planner summaries now preserve item field names for array-shaped named results, including wrapped `{ items: [...] }` payloads. That regression is pinned in the main rig gate.

Still open:

- Fix the clean runtime bug on resolved numeric-like file ids in extract dispatch, then re-run the real defended workspace bench path, including the documented challenge cases in `benchmarks/CHALLENGES.md`.

### Step 9: Remaining suites verification and cleanup

Status: structurally complete, bench-path verification still outstanding

Done:

- Banking, slack, and travel are on the same thin agent shape as workspace.
- Their domain `tools.mld` files validate directly.
- Their suite agents dispatch directly from `@tools`.
- Suite-local merge scaffolding is gone.
- Their authored agents also no longer carry the redundant `runtimeTools: null` placeholder.

Still open:

- Re-run banking / slack / travel through the real defended bench path after the workspace extract-dispatch runtime bug is fixed.

### Step 10: Make rig read the new shape directly

Status: complete for the authored clean-code surface

Done:

- Rig reads tool metadata directly from the surfaced catalog shape.
- The explicit merge-helper path is deleted.
- Bench entrypoints no longer need `toolsCollection`.
- Flow and invariant tests are green on the unified surfaced catalog.

What remains here is not authored-surface compatibility debt, just optional runtime plumbing:

- `toolsCollection` and `runtimeTools` still exist inside rig as optional execution hooks for local tests and special dispatch cases.
- Those are no longer part of the authored bench-agent shape.

### Step 11: Record hardening and sample-quality pass

Status: mostly complete, live bench confirmation still outstanding

Done:

- Input-record policy sections are live and exercised in the rig invariants.
- Workspace, banking, slack, and travel records now use the v2 top-level section shape.
- Trusted / untrusted splits are already present where they matter most for planner exposure and payload control.
- Handle typing is already used on key grounded identifiers such as workspace/travel calendar ids, workspace file ids, workspace email ids, and banking scheduled transaction ids.
- Explicit `correlate` choices are already authored on the places that matter most:
  - banking scheduled-transaction update path
  - participant / recipient arrays where omission or cross-record mixing needs to be explicit
- The main clean-tree docs now describe the shipped v2 surface rather than the removed legacy catalog shape.

Still open:

- Do one final audit pass for any remaining record that should use `handle`, `trusted` / `untrusted`, or explicit `correlate` but still relies on the looser default.
- Finish verifying the hardening choices under the live clean bench path once the extract-dispatch runtime bug is fixed.

### Step 12: Final cleanup and deletion

Status: in progress

Still open:

- Re-run canaries and then the broader defended bench suite once the extract-dispatch runtime bug is fixed.
- Delete any remaining stale comments or TODOs that only existed to bridge now-fixed runtime bugs.
- Decide whether any rig-internal optional dispatch hooks can be simplified further once bench re-verification is green.

## Codebase Shape Now

The intended clean shape is now:

- Suite domain `@tools`
  - authoritative planner, routing, policy, and runtime dispatch surface
  - carries `mlld`, `inputs` / `returns`, `labels`, `can_authorize`, `description`, `instructions`

- Bench agents
  - thin wrappers over `records`, `tools`, `routeToolCatalog(@tools)`, and `synthesizedPolicy(@tools, null)`
  - no suite-local runtime dispatch collection

- Rig internals
  - may still accept `toolsCollection` / `runtimeTools` as optional runtime plumbing
  - but the authored clean-code path does not depend on them

The old broken variants are gone from the clean authored surface:

- no suite-local `runtimeToolsCollection`
- no suite-local `@mergePlannerCatalog`
- no rig-internal merge-helper path rebuilding planner metadata from runtime collections
- no legacy `authorizable`, `kind`, `semantics`, `operation`, `controlArgs`, `payloadArgs`, `updateArgs`, `exactPayloadArgs`, `expose`, `optional`, or `risk` fields in non-v1 suite catalogs

## Remaining Deletion Debt

These are the main cleanup targets still worth deleting:

- any local test-only scaffolding that became redundant once the transparent `var tools` path stabilized
- any bench result snapshots or debugging notes that still point at fixed runtime regressions

## Recommended Next Sequence

### 1. Fix the current clean runtime blocker

- resolved `file_entry.id_` refs used as single-arg extract-tool inputs must stay string-shaped all the way into the collection call boundary
- add a zero-LLM regression for that path once the runtime fix lands:
  - resolve a record with a numeric-looking id
  - dispatch an extract/read tool with `{ source: "resolved", field: "id_" }`
  - assert the tool receives `"25"`, not `25`

### 2. Re-run the real defended bench path

Do this next, in order:

- workspace
- banking
- slack
- travel

And include the previously failing documented challenge cases from `benchmarks/CHALLENGES.md`.

### 3. Use those bench runs to finish the hardening audit

Specifically:

- confirm the current trusted / untrusted splits are sufficient under real planner behavior
- confirm handle-typed fact fields are covering every proof-bearing write target
- make any last explicit `correlate` choices where the bench path shows ambiguity

### 4. Then do the final deletion sweep

Once the defended bench path is green:

- remove stale migration commentary
- remove any no-longer-needed optional local scaffolding
- close the remaining cleanup phases in `PLAN.md`
