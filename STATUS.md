# Rig v2 Status

Snapshot date: 2026-04-18

This file records where `clean/` stands against [PLAN.md](/Users/adam/mlld/clean/PLAN.md) after the single-planner rewrite.

## Summary

- Clean rig now implements one persistent planner tool-use session per `@rig.run`.
- The outer planner loop, planner resume path, and per-turn planner prompt reconstruction are removed from the clean rig implementation.
- Planner actions now go only through the six rig-owned planner tools:
  - `resolve`
  - `extract`
  - `derive`
  - `execute`
  - `compose`
  - `blocked`
- Planner-visible tool results are statically typed and returned through the planner-tool wrapper surface.
- The clean authored tool surface remains one surfaced `var tools` catalog per suite.
- The old rig-side workaround layer is gone:
  - no `runtimeTools` sidecar on clean bench agents
  - no thin planner adapter exes
  - no runtime lookup hook for planner/runtime shadow catalogs

## Single-Planner Status

The architecture change itself is done.

Landed:

- one persistent planner session per run
- rig-owned planner tools only
- no outer planner loop
- no planner `resume` in rig orchestration
- no per-turn planner prompt reconstruction
- framework-owned tool-call budgets
- terminal `compose` / `blocked`

What remains is verification and final trimming, not more architectural migration.

- Re-run the real defended clean bench path on workspace, then challenge cases, then banking/slack/travel.
- Treat remaining failures as planner/tool-contract, host wiring, or real mlld runtime issues.
- Delete any last internal helper branch only if the live bench runs prove it unnecessary.

The short remaining-work checklist now lives in [SINGLE-PLANNER.md](/Users/adam/mlld/clean/SINGLE-PLANNER.md).

## Verified Now

These checks were re-run on the current clean rig code:

- `mlld clean/rig/tests/index.mld`
  - `summary: 77 pass / 0 fail`
  - This is the main invariant gate.
  - It includes the persistent-planner architectural assertions:
    - no `@runPhaseLoop`
    - no `@dispatchPlanner`
    - no planner `resume:`
    - no `<state_summary>` / `<execution_log>` planner prompt reconstruction

- Direct validation passes:
  - `mlld validate clean/rig/index.mld`
  - `mlld validate clean/rig/orchestration.mld`
  - `mlld validate clean/rig/runtime.mld`
  - `mlld validate clean/rig/lifecycle.mld`
  - `mlld validate clean/rig/session.mld`
  - `mlld validate clean/rig/workers/planner.mld`

## Status Against PLAN

### Steps 1-4

Status: complete enough to build on

- Core resolve / extract / derive / execute / compose worker dispatch exists.
- Input-record policy sections and surfaced catalog invariants are pinned in the rig test suite.
- The transparent `var tools` path is the authored path in clean agents and suite catalogs.

### Step 5: Delete the phase-loop planner architecture

Status: complete

Done:

- `rig/orchestration.mld` no longer runs an outer planner loop.
- `rig/workers/planner.mld` now owns one persistent planner session with provider tool use.
- `rig/prompts/planner.att` is a single-session prompt, not a per-turn reconstructed prompt.
- `rig/runtime.mld` and `rig/lifecycle.mld` no longer carry `planner_session_id` orchestration state.
- `rig/records.mld` no longer defines the per-turn planner decision record.

### Step 6: Structured tool errors, budgets, and terminal-tool discipline

Status: complete at the framework layer

Done:

- Planner-tool wrappers return structured status/error results.
- `maxIterations` is now interpreted as a planner tool-call budget.
- Repeated invalid planner tool calls are budgeted separately.
- `compose` is terminal.
- `blocked` is terminal.
- Planner tool calls after terminal state are rejected.

Still open:

- Exercise these paths more heavily under the real bench harness, not just the rig invariant suite.

### Steps 7-10: Final v2 surface and unified authored catalog

Status: complete on the clean authored surface

Done:

- Clean suite catalogs use the shipped v2 tool-entry fields:
  - `mlld`
  - `inputs`
  - `returns`
  - `labels`
  - `can_authorize`
  - `description`
  - `instructions`
  - `bind`
- Clean authored agents no longer carry planner/runtime split catalogs.
- The rig prompt/docs/tests assert the persistent single-planner model directly.
- Runtime dispatch now reads the authored tool entry directly; the only remaining special case is the core-supported `direct: true` whole-object planner-tool path.

Still open:

- Nothing architecturally open here on the authored surface. Any remaining cleanup is internal bench verification and optional helper trimming after the live runs.

### Step 11: Record hardening and sample-quality pass

Status: mostly complete, needs live bench confirmation

Done:

- Input-record policy sections are live.
- Handle typing, trusted/untrusted splits, and explicit `correlate` choices are authored across the migrated suite records.
- Planner-tool results are statically typed so the planner-facing tool surface stays explicit.

Still open:

- Run the full defended bench path and confirm the hardening choices behave correctly end to end.

### Step 12: Final cleanup and deletion

Status: in progress

Done:

- The clean implementation now treats the single planner session as the only acceptable planner architecture.
- `runtimeTools` sidecars and planner adapter wrappers are deleted from the clean rig path.
- Generated compatibility noise from verification runs is not part of the retained surface.

Still open:

- Re-run the real clean bench path for workspace, banking, slack, and travel.
- Delete any last internal helper branch that bench re-verification proves unnecessary.
- Sync any remaining current docs outside the rig contract set if they still describe the removed loop.

## What Is Left

The remaining work is bench verification and final trimming, not another architectural rewrite:

1. Re-run the clean defended bench path on workspace.
2. Re-run the documented challenge cases.
3. Re-run banking, slack, and travel.
4. Tune planner prompt/tool contracts only if the live harness reveals behavior gaps.
5. Delete any last internal helper branch that is still optional but unused after the real bench runs are green.
6. Do one final doc/status sync after the bench runs.

## Current Risk

The main remaining uncertainty is not the rig architecture. It is end-to-end planner behavior on the live clean bench harness:

- the persistent planner enters the new tool loop correctly
- the invariant suite is green
- full defended bench re-verification is still pending

So the next step is straightforward: run the clean bench path, inspect failures as planner/tool-contract issues first, and only file runtime bugs if the failure is clearly below rig.
