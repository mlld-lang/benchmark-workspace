# Rig v2 Status

Snapshot date: 2026-04-14

This file records where `clean/` stands against [PLAN.md](/Users/adam/mlld/clean/PLAN.md), what is currently verified, what remains blocked, and how the new mlld input-record/tool-catalog shift should be adopted in this repo.

## Summary

- The rig v2 codebase in `clean/rig/` is alive end to end in the legacy tool-shape implementation.
- The cheap deterministic suites are green:
  - `mlld --new /Users/adam/mlld/clean/rig/tests/index.mld` -> `summary: 40 pass / 0 fail`
  - `mlld --new /Users/adam/mlld/clean/bench/tests/workspace-tools.mld` -> `summary: 3 pass / 0 fail`
- The workspace harness path has already been proven on simple defended tasks:
  - `user_task_0` passed
  - `user_task_1` passed
  - `user_task_6` passed
- The main remaining functional issue before a broader workspace rerun is the legacy optional-control-arg case on workspace `create_calendar_event` (`participants` omitted should be allowed, but legacy shape still self-denies).
- Upstream mlld now implements the input-record/tool-catalog redesign. `supply` and field attrs are not in this version yet, so the migration plan here should target the shipped subset only.

## Status Against PLAN

### Step 1: Rig core skeleton with lifecycle emission

Status: complete

- `@rig.build` and `@rig.run` exist and the planner/phase loop/lifecycle path is in place.
- Host integration files and lifecycle emission are implemented.

### Step 2: Resolve phase

Status: complete

- Resolve worker dispatch works.
- Resolved records are stored and referenced correctly.
- Scalar-key and stringification edge cases have dedicated regressions.

### Step 3: Extract phase

Status: complete

- Extract worker runs.
- Planner visibility of named extracted state has been tightened so payload content does not leak back into the planner context.
- The worker/value path still reads full state when a later phase references extracted fields.

### Step 4: Derive phase

Status: complete

- Derive worker runs.
- Selection ref lowering is implemented as a shared primitive.
- Planner-facing state projection for named derived results is constrained the same way as extracted state.

### Step 5: Execute phase with compiled authorization

Status: complete in the legacy tool-shape implementation

- Intent compilation, policy build integration, selection lowering, and per-element control-arg proof checking are implemented.
- The remaining issue here is not a generic execute failure; it is the legacy optional-control-arg contract on workspace `create_calendar_event`.

### Step 6: Guards and retry

Status: substantially complete

- Guard and retry behavior exists.
- The repo has already been steered away from task-13-specific accommodations.
- Remaining cleanup here should happen only if it falls out of the input-record migration, not as benchmark-shaped prompt tuning.

### Step 7: First benchmark suite (workspace)

Status: partially complete

- Workspace records/tools/agent entrypoint exist.
- The host and adapter path are alive.
- Simple defended tasks have passed.
- Full workspace rerun should wait for the input-record migration of the optional-control-arg case, because that is the clean fix for the last known blocker.

### Step 8: Remaining suites

Status: not started

- Banking, Slack, and Travel still need to be migrated and rerun after workspace is stable on the new surface.

### Step 9: Measurement pass

Status: not started

- No fresh whole-suite measurement should be taken until workspace is rerun cleanly after the feature shift.

## What Is Locked In

- Native mlld values are preserved through the rig path; wrapper-stripping and normalize/unwrap helpers were removed from the design direction.
- Planner-visible named state no longer exposes extracted/derived payload values directly.
- Record/display projection and attestation-only planner summaries are part of the architecture now.
- Task-13-specific accommodations are explicitly out of scope and should not drive framework shape.
- Callability preservation across tool catalogs and phase filtering has dedicated regressions.

## Current Verified Test Status

Last re-run in this repo snapshot:

- `rig/tests/index.mld`: 40 pass / 0 fail
- `bench/tests/workspace-tools.mld`: 3 pass / 0 fail

These are the two fast suites that should be kept green during the feature-shift migration.

## Current Blocker

### Workspace `create_calendar_event` optional participants

This is the last issue that was actively being worked:

- Tool: `bench/domains/workspace/tools.mld` -> `create_calendar_event`
- Current legacy shape: `controlArgs: ["participants"]`
- Actual task shape: creating a personal event with no participants should be allowed
- Legacy behavior: when `participants` is omitted, execute/policy still treats the tool as a control-arg write and self-denies

The local workaround that synthesized internal `allow` for omitted optional control args has been removed. That was the wrong layer. The new input-record surface is the right fix.

## Plan For The New Feature Shift

The upstream shift is now available, but only the shipped subset should drive the repo plan:

- available now: input records, new catalog shape, labels handoff
- not available yet: `supply`, field attrs

That means this repo should migrate in a staged, mixed-shape way instead of trying to jump straight to the full final spec.

### Phase A: Lock the legacy baseline

1. Keep the current legacy-shape rig and workspace behavior committed and reproducible.
2. Do not reintroduce internal execute-worker hacks for omitted control args.
3. Keep the fast deterministic suites green while the metadata plumbing changes.

### Phase B: Teach rig to read the new catalog surface

Primary files:

- [rig/tooling.mld](/Users/adam/mlld/clean/rig/tooling.mld)
- [rig/intent.mld](/Users/adam/mlld/clean/rig/intent.mld)
- [rig/workers/execute.mld](/Users/adam/mlld/clean/rig/workers/execute.mld)
- [rig/runtime.mld](/Users/adam/mlld/clean/rig/runtime.mld)
- [rig/index.mld](/Users/adam/mlld/clean/rig/index.mld)

Plan:

1. Add input-record-aware metadata helpers in `rig/tooling.mld`.
   - Derive fact args from `inputs.facts`
   - Derive payload args from `inputs.data`
   - Derive optionality from `?` fields
   - Preserve legacy helpers as fallback during migration
2. Shift rig helpers that currently read `operation.controlArgs`, `operation.payloadArgs`, `optional`, `risk`, and `kind` so they can read the new top-level/catalog-native shape first and legacy shape second.
3. Move rig risk/kind semantics onto rig label conventions, since mlld no longer owns those fields.
4. Keep this change mechanical. Do not change planner behavior beyond what the new metadata surface requires.

### Phase C: Preserve write-payload coercion while the repo is mixed-shape

The old rig design assumes `payloadRecord` is the schema authority for write-preparation extract and execute-time payload casting.

Because the shipped mlld feature shift does not yet include attrs or the full final migration surface, treat payload coercion as a temporary mixed-shape concern:

1. Continue to support the current payload-cast path while legacy entries still exist.
2. For new-shape tools, decide explicitly whether rig:
   - derives payload structure from the new `inputs` record, or
   - keeps a temporary rig-local payload schema field until all write-preparation extract paths are redesigned
3. Make that decision once in rig helpers. Do not fork behavior ad hoc per suite.

This is the one migration point that needs deliberate design work, not just field renaming.

### Phase D: Migrate workspace first, starting with the blocker

Primary file:

- [bench/domains/workspace/tools.mld](/Users/adam/mlld/clean/bench/domains/workspace/tools.mld)

Order:

1. Migrate `create_calendar_event` first.
   - Express `participants` as an optional fact in the new input record.
   - Keep the tool semantics aligned with the real backend behavior: omitted participants means no notifications.
   - Add a regression that proves:
     - omitted optional fact -> allowed
     - present bare literal -> denied
     - present proof-bearing value -> allowed
2. Migrate the other workspace tools that do not depend on not-yet-shipped attrs.
3. Keep tools that still need legacy-only metadata on the legacy shape until attrs land.

The goal is mixed-shape compatibility, not a big-bang rewrite.

### Phase E: Update tests with the new surface

Primary files:

- [rig/tests/index.mld](/Users/adam/mlld/clean/rig/tests/index.mld)
- [rig/tests/fixtures.mld](/Users/adam/mlld/clean/rig/tests/fixtures.mld)
- [bench/tests/workspace-tools.mld](/Users/adam/mlld/clean/bench/tests/workspace-tools.mld)

Add or replace regressions for:

1. input-record fact/payload helper extraction
2. mixed-shape helper compatibility
3. optional fact omission on `create_calendar_event`
4. labels-as-rig-schema ingestion
5. planner/tool-doc rendering for the new catalog surface

The deleted optional-control-arg workaround test should come back only in its new form, pinned to input-record semantics rather than an internal execute escape hatch.

### Phase F: Rerun workspace, then continue PLAN.md

1. Re-run defended workspace canaries:
   - `user_task_0`
   - `user_task_1`
   - `user_task_6`
   - `user_task_12` (the current blocker)
2. If those are clean, run the full 40-task workspace suite on the cheap harness/model.
3. Only then move on to Step 8 suite migration for Banking, Slack, and Travel.
4. Save whole-suite measurement for after workspace is stable on the new surface.

## What Remains Deferred

Until upstream lands more of the spec, this repo should defer:

- `supply:` migration
- field-attribute migration (`exact`, `update`, `allowlist`, etc.)
- any benchmark-shaped changes motivated by task 13
- broad whole-suite measurement after every partial metadata refactor

## Immediate Next Task

Update the rig metadata helpers to understand `inputs: @record`, then migrate workspace `create_calendar_event` to the new shape and re-run the four workspace canaries above.
