# Rig v2 Build Plan

Build rig v2 from scratch in `~/mlld/clean/rig/` and its consumer in `~/mlld/clean/bench/`. When complete, move to `~/mlld/rig/` and `~/mlld/bench/`.

This is a write plan, not a rewrite plan. No old code is in scope. The existing rig v1 at `~/mlld/rig/` is a reference only — cite patterns, don't migrate them.

## What We're Building

- `~/mlld/clean/rig/` — rig v2 framework
- `~/mlld/clean/bench/` — benchmark agents + Python host using rig v2

When v2 benchmarks at baseline across all 4 suites, `mv ~/mlld/rig ~/mlld/rig-v1-archive && mv ~/mlld/clean/rig ~/mlld/rig` (same for bench). Import paths stay the same post-move.

## Specs (Read These First)

- `~/mlld/clean/rig/ARCHITECTURE.md` — why the system is structured this way
- `~/mlld/clean/rig/INTERFACE.md` — public surface (frozen)
- `~/mlld/clean/rig/PHASES.md` — persistent planner tool-use implementation contract
- `~/mlld/clean/rig/SECURITY.md` — invariants that must hold
- `~/mlld/clean/rig/EXAMPLE.mld` — minimal toy agent end-to-end
- `~/mlld/clean/bench/ARCHITECTURE.md` — how benchmark consumes rig
- `~/mlld/clean/bench/INTERFACE.md` — what each suite provides
- `~/mlld/clean/SPIKES.md` — pointers to reference implementations

## Cross-Cutting Work

These deliverables don't fit a single step — they cut across the whole build. Scope and design them up front; implement them incrementally across steps; verify at step exits.

### Display projection

Applies to every planner-visible tool result and every worker box dispatch.

Deliverables:
- Helper that renders a record value through its `role:X` display mode
- Planner tool wrappers that return only:
  - `->` clean attestations, or
  - `=> record` values that are projected through `role:planner`
- Worker LLM calls inside boxes with `display: "role:worker"`
- Unit coverage in `rig/tests/index.mld` for at least: planner sees role:planner projection, worker sees role:worker projection, omitted fields are actually omitted, and tainted tool-worker data does not leak back to the planner through a wrapper result

First appears in Step 1 (persistent planner tool-use spike). Extended in Step 2-4 as each planner-facing wrapper is added. Locked by Step 5 when the old state-summary path is deleted.

### Planner prompt and tool surface

Generates the planner's initial system prompt and the planner-facing rig-owned tool surface from:
- tool docs (derived from tool catalog metadata)
- operation docs for planner-authorizable writes (`description`, `instructions`, arg signatures, `can_authorize` roles, policy sections)
- source-class rules and tool-use discipline
- terminal-tool rules for `compose` and `blocked`

Deliverables:
- Tool docs renderer from the v2 catalog shape
- Operation docs renderer from the v2 catalog shape
- Planner prompt that assumes one continuous tool-use conversation, not per-turn reconstruction
- Rig-owned planner tool wrappers for `resolve`, `extract`, `derive`, `execute`, `compose`, and `blocked`

The planner does not receive a reconstructed per-turn state summary or execution-log prompt section. The conversation and tool results are the execution history.

### Policy synthesizer

Converts the tool catalog into a `policy` object at `@rig.build` time. Algorithm spelled out in `PHASES.md` §Base Policy Synthesis.

Deliverables:
- Synthesizer function that walks the tool catalog and emits the base policy
- Override merge logic (additive union, locked rule preservation)
- Build-time validation (synthesized policy is well-formed, `@policy.build` accepts it)
- Invariant test: known catalog input produces expected synthesized policy

Timing:
- **Step 1 does NOT require the synthesizer.** The Step 1 invariant test "policy build" is a baseline assertion that `@policy.build` (the underlying mlld runtime primitive) accepts a hand-constructed minimal policy — verifying the runtime contract, not the rig synthesizer. This is the same assertion v1 spike 34 has; it catches runtime regressions in `@policy.build` itself.
- **Step 4 is when the synthesizer becomes a real deliverable.** Execute dispatch needs a synthesized policy from the tool catalog to call `@policy.build` with real authorization intent. The Step 4 invariants ("known catalog input produces expected synthesized policy") verify the rig synthesizer specifically.

You can write the synthesizer earlier if convenient — it's pure transformation with no runtime dependencies — but the plan treats Step 1's "policy build" assertion and Step 4's "synthesizer" as distinct work items.

### Framework-internal records

Records that rig uses internally for its own typed data (tool wrapper results, phase attestations, host integration). Not exposed to apps.

Deliverables:
- Planner tool result / terminal result records
- Phase result record (attestation shape per worker)
- Lifecycle event records (for NDJSON serialization)

Populated in Step 1; refined per step as each worker adds its phase result shape.

### Error surfaces

Clear exception types from `@rig.build` and `@rig.run` with messages that point at the specific problem.

Deliverables:
- `@rig.build` errors: malformed record, malformed tool declaration, missing payloadRecord reference, can_authorize: false on a tool also in the planner-authorizable list, ref to an undefined record
- `@rig.run` errors: planner tool-call budget exhaustion, repeated invalid tool-call budget exhaustion, terminal tool misuse after completion, compiled policy rejects all options, phase worker threw unhandled, host integration file path not writable
- Error messages include the offending name (tool key, record name, arg name) not just the category

Appears incrementally. Step 1 should produce clear build-time errors. Step 4 should produce clear compile-time authorization errors.

## Build Order

Each step produces something runnable. Don't proceed to the next step until the current one works end-to-end for its scope.

### Step 1: Persistent planner skeleton with lifecycle emission

**Goal:** `@rig.build(config)` + `@rig.run(agent, query)` work end-to-end for a trivial case using exactly one planner LLM session with provider tool use. No outer planner loop, no per-turn prompt reconstruction, no planner resume. **Phase lifecycle emission works from day one.**

**Files:**
- `rig/index.mld` — public surface, `@rig.build`, `@rig.run`
- `rig/orchestration.mld` — single-session runner
- `rig/workers/planner.mld` — initial planner prompt + planner-facing tool surface
- `rig/workers/compose.mld` — compose worker used behind the planner-facing `compose` tool
- `rig/prompts/planner.att` — initial planner prompt for persistent tool use
- `rig/prompts/compose.att` — compose prompt
- `rig/records.mld` — framework-internal tool-result / terminal-result records
- `rig/lifecycle.mld` — NDJSON event emission to host-configured `phase_log_file`; live pointer write to `phase_state_file`

**Add:**
- Persistent planner call with `tools: @plannerTools`
- Planner-facing `compose` and `blocked` tools
- Terminal session state for `complete` and `blocked`
- Lifecycle emission per planner tool invocation (`planner_iteration`, `phase_start`, `phase_end`)
- Tool-call result contract: planner tool wrappers return only clean attestation or planner-projected record output

**Exit:** `mlld rig/tests/flows/smoke.mld` produces a `complete` terminal through one planner session that calls `compose` and exits. `phase_log_file` contains valid `planner_iteration` and `phase_start`/`phase_end` events. `phase_state_file` reflects the current phase during execution and returns to the `between` sentinel at completion. `mlld rig/tests/index.mld` starts as a skeleton with at least the baseline assertions (mlld runtime `@policy.build` accepts a minimal hand-constructed policy, tool metadata access works, thin-arrow strict mode doesn't leak, planner tool wrappers do not leak tainted worker data back to the planner). **The rig policy synthesizer is not required in Step 1** — it's a Step 4 deliverable. The Step 1 "policy build" assertion verifies the underlying runtime primitive, not the synthesizer.

### Step 2: Resolve as a planner-facing rig tool

**Goal:** The persistent planner can ground records via the planner-facing `resolve` tool. Resolved values are proof-bearing, and the planner only sees clean results.

**Add:**
- `rig/workers/resolve.mld` — resolve dispatch
- Planner-facing `resolve` wrapper in `rig/workers/planner.mld`
- `rig/prompts/resolve.att` — resolve worker prompt
- State storage for resolved records (rig-internal, keyed by handle/instance key)
- Tool catalog validation in `@rig.build` for read tools
- Ref resolution for `{ source: "resolved", record, handle, field }`
- Planner-visible resolve result contract:
  - `->` attestation by default
  - planner-projected record output only when explicitly needed

**Reference:** v1 resolve patterns at `~/mlld/rig/workers/resolve.mld` — keep the worker semantics, not the outer-loop structure.

**Exit:** `mlld rig/tests/flows/resolve.mld` with a synthetic `get_contacts` tool completes within one planner session as `resolve` → `compose`. Compose cites the resolved contact by name via a `resolved` ref. `rig/tests/index.mld` includes an invariant proving the planner-facing resolve tool result applies `role:planner` display and does not leak omitted fields.

### Step 3: Extract and derive as planner-facing rig tools

**Goal:** The persistent planner can coerce tainted content into typed payloads and compute derived results over typed inputs, while the planner itself remains clean.

**Add:**
- `rig/workers/extract.mld` — extract dispatch, schema validation, `@cast` coercion, extracted provenance tagging
- `rig/workers/derive.mld` — derive dispatch, schema validation, provenance tagging
- Planner-facing `extract` and `derive` wrappers in `rig/workers/planner.mld`
- `rig/prompts/extract.att` — extract worker prompt
- `rig/prompts/derive.att` — derive worker prompt
- State storage for extracted and derived results
- Ref resolution for `{ source: "extracted", name, field }` and `{ source: "derived", name, field }` — payload-only
- Source-scope enforcement: extract only reads the source named in the tool call
- **Extract cannot produce selection refs**. If the worker tries, rig rejects the output.
- **Derive selection ref validation** — when derive returns a selection ref, rig validates the backing ref points to an instance in the derive input set with original proof
- Planner-visible tool result discipline:
  - extract returns attestation only
  - derive returns attestation only
  - neither may return raw extracted or derived payload content to the planner

**Reference:** spike 35 (provenance firewall), spike 36 (intent compiler), spike 41 (schema authority), spike 42 (selection-ref boundary).

**Exit:** `mlld rig/tests/flows/extract.mld` and `mlld rig/tests/flows/derive.mld` complete within one planner session. `rig/tests/index.mld` includes explicit invariants proving:
- an extract worker that processed tainted content does not leak that taint back to the planner through the planner-facing tool result
- an extract worker attempting to emit a selection ref is rejected
- derive can return validated selection refs without leaking payload content

### Step 4: Execute as a planner-facing rig tool with compiled authorization

**Goal:** The persistent planner can perform writes through the planner-facing `execute` tool with compiled per-step authorization from typed source-class refs.

**Add:**
- `rig/workers/execute.mld` — execute dispatch, single-write enforcement, compiled policy application
- Planner-facing `execute` wrapper in `rig/workers/planner.mld`
- `rig/prompts/execute.att` — execute worker prompt
- `rig/intent.mld` (real implementation) — compiles typed source-class args into bucketed intent
- Policy synthesizer integration with `@policy.build`
- Write-tool operation declaration validation in `@rig.build`
- Source class resolution at execute compile time:
  - `resolved` → include in `resolved` bucket with factsource
  - `known` → include in `known` bucket with `{ task: query }` verification
  - `extracted` → payload-only; reject for control args
  - `derived` → payload-only; reject for control args
  - `selection` → lowers to backing resolved instance; proof carried through; valid for both control and payload positions
  - `allow` → only valid for tools with no control args; reject on tools with control args
- Per-element control-arg checking for array-typed control args
- Payload record coercion: `@cast` applied to payload-arg subset only; control args and bind-default args merged after cast
- Selection ref lowering as a cross-phase primitive shared by resolve, extract, derive, execute, and compose arg resolution

**Reference:** spike 36 (intent compiler), spike 37 (records + ops surface).

**Exit:** `mlld rig/tests/flows/execute.mld` with a synthetic `append_note` write tool completes within one planner session as `resolve` → `execute` → `compose`. A second test exercises the provenance firewall: an execute with `{ source: "derived", ... }` in a control arg position is rejected. A third test shows selection refs working correctly for derive → control arg. `rig/tests/index.mld` covers the firewall, selection ref lowering, and per-element array proof as dedicated assertions — these must pass zero-LLM.

### Step 5: Delete the phase-loop planner architecture

**Goal:** Remove the obsolete architecture once the persistent planner path is working. There is no supported outer planner loop after this step.

**Delete / change:**
- Per-turn planner decision schema and parser path
- Planner retry prompt path and schema-failure-after-retry terminal
- Planner prompt reconstruction from `state_summary` and `execution_log`
- Planner `resume` threading and `planner_session_id` as correctness machinery
- Loop-counter-based planner orchestration
- Any helper whose only job was to rebuild planner context between planner turns

**Files:**
- `rig/orchestration.mld`
- `rig/workers/planner.mld`
- `rig/runtime.mld`
- `rig/prompts/planner.att`
- `rig/records.mld`

**Exit:** The planner architecture in clean rig is unambiguously one persistent tool-use session. No clean rig code path can run the old outer-loop planner model. `rig/tests/index.mld` includes explicit assertions that the planner path does not pass `resume` and does not rely on a per-turn planner state-summary builder.

### Step 6: Structured tool errors, budgets, and terminal-tool discipline

**Goal:** The planner repairs itself in-session through structured planner-tool errors, while the framework enforces hard budgets and terminal semantics.

**Add:**
- Planner-tool error contract for invalid args, unknown tools, policy rejection, and worker failure
- Total planner tool-call budget owned by rig (the existing `maxIterations` config is reinterpreted as a tool-call budget)
- Consecutive invalid tool-call budget owned by rig
- Terminal-tool discipline:
  - `compose` is terminal
  - `blocked` is terminal
  - any subsequent planner tool call after terminal state is a framework error

**Rule for this step:**
- The planner repairs through tool results inside the same session
- The framework owns the budgets and termination
- There is no outer-loop retry path for planner decisions

**Exit:** `mlld rig/tests/flows/guards.mld` is replaced or rewritten as persistent-planner tool-error coverage. `rig/tests/index.mld` includes invariants for:
- tool-call budget exhaustion
- repeated invalid-tool-call exhaustion
- `compose` terminal behavior
- `blocked` terminal behavior
- framework rejection of any planner tool call after terminal state

### Step 7: Pin policy sections and the transparent catalog surface

**Goal:** Now that mlld ships the v2 input-record policy sections and the catalog/runtime P0s are fixed, lock rig and bench onto the final shipped surface before any more suite verification. This is the point where the plan stops tolerating deprecated schema shape, split planner/runtime catalogs, or compatibility wording as anything other than deletion debt.

**New upstream surface to adopt immediately:**
- Top-level input-record policy sections:
  - `exact`
  - `update`
  - `allowlist`
  - `blocklist`
  - `optional_benign`
- Tool-catalog auth field:
  - `can_authorize`
- Transparent `var tools` behavior:
  - keyed access preserves authored metadata
  - runtime dispatch uses the same catalog object the planner sees
- Existing field syntax only:
  - `name: type`
  - `name: type?`
- No field-level attr bags, no `name[?]: type` shorthand, no parallel compatibility surface in clean code

**Add in rig immediately after upstream lands:**
- Direct readers for the new policy sections in rig helpers that inspect tool inputs
- Direct reads of `can_authorize` from the authored tool entry; no legacy planner-surface alias
- Removal of planner/runtime catalog split workarounds that existed only because `var tools` was not transparent
- Declare-time validation tests for bad section targets and malformed section values
- Runtime enforcement tests in spec order:
  - `allowlist`
  - `blocklist`
  - `exact`
  - `update`

**Regression suite additions (zero-LLM unless otherwise noted):**
- Migration shape:
  - `IR-1`: migrated tools reject legacy schema reintroduction
  - `IR-2`: control/payload derivation comes from input records, not duplicate legacy keys
  - `IR-3`: migrated tools do not re-declare schema in `@toolsCollection`
  - `MIG-1`: every migrated tool has an input record
  - `MIG-2`: no tool mixes `inputs:` with legacy `operation:`
  - `MIG-3`: every exe parameter is covered by `facts`, `data`, or `bind`
  - `MIG-4`: record field names match exe parameter names
- Policy sections:
  - `POL-ALLOW-*`: allowlisted values pass; non-allowlisted values fail
  - `POL-BLOCK-*`: blocked values fail with the right error; non-blocked values pass
  - `POL-EXACT-*`: exact fields only accept task-supported literals/verbatim values
  - `POL-UPDATE-*`: update fields require an actual update-set, not an empty dispatch
  - `POL-OPT-*`: `optional_benign` is accepted only on valid optional input fields
- Catalog/runtime cohesion:
  - transparent `var tools` readback preserves `inputs`, `can_authorize`, and other authored metadata
  - builder-produced allowlist/blocklist authorizations round-trip through invocation unchanged
  - no separate plain-object planner catalog exists for migrated suites
  - `can_authorize` round-trips through build/policy synthesis/routing with the authored roles preserved
  - built agents can execute through the same catalog object the planner docs were derived from
  - direct keyed access and `mx.entries` agree on tool-entry metadata for migrated tools
- Existing invariants to pin now because later cleanup depends on them:
  - `CORR-*`
  - `SEM-*`
  - `TR-*`
  - `WR-*`
  - `DK-2`
  - `SHIM-*`

**Additional regression coverage to add in this step because of the recent fixes:**
- `CAT-1`: transparent `var tools` preserves input-record identity on keyed readback
- `CAT-2`: transparent `var tools` preserves `can_authorize`, `bind`, labels, and prompt-doc metadata on keyed readback
- `CAT-3`: `mx.entries` and direct keyed access return equivalent tool-entry metadata for migrated tools
- `CAT-4`: a built agent can use the same authored catalog for planner docs and runtime dispatch with no shadow planner catalog
- `AUTH-1`: `can_authorize: false` lands in synthesized deny policy and the tool is absent from planner-authorizable operations
- `AUTH-2`: string and array `can_authorize` role declarations synthesize the expected planner-authorizable role map
- `AUTH-3`: no clean authored tool entry uses the legacy `authorizable` key
- `POL-ROUNDTRIP-1`: builder-produced allowlist authorization accepts a matching dispatched value at invocation time
- `POL-ROUNDTRIP-2`: builder-produced allowlist authorization rejects a non-matching dispatched value at invocation time
- `POL-ROUNDTRIP-3`: builder-produced blocklist authorization rejects a blocked dispatched value at invocation time
- `POL-ROUNDTRIP-4`: builder-produced exact/update constraints survive invocation unchanged after policy synthesis
- `BENCH-CAT-1`: no clean suite domain/agent keeps a planner/runtime split catalog once the transparent surface is available

**Rule for this step:**
- Do not preserve deprecated input-policy functionality defensively.
- Do not preserve the planner-catalog/runtime-catalog split once the transparent `var tools` surface exists.
- Do not use `authorizable` as an authored tool-catalog key in clean code.
- If a new top-level section replaces an old field, the old field becomes deletion debt, not a compatibility target.
- The only explicitly deferred input-record feature remains `supply:`.

**Exit:**
- Rig tests explicitly cover each top-level policy section and the migration invariants
- Rig tests explicitly cover the transparent single-catalog tool surface and builder/enforcement agreement for allowlist/blocklist constraints
- No clean suite keeps a shadow planner catalog or a companion runtime bridge solely to preserve metadata/readback
- No clean-code examples use field attr bags or `name[?]: type`
- The plan for migrated tools is now unambiguous: input record is the schema source; top-level policy sections are the policy source; the tool catalog is the single authored source for both planner and runtime metadata

### Step 8: Workspace end-to-end verification and cleanup

**Goal:** Workspace becomes the first fully verified clean suite on rig v2. The migration work is already done; this step is about removing residual bridge/workaround code, running the real harness path, and proving the clean shape holds end to end.

**Python host (port from v1 with minimal changes):**
- `src/host.py` — MlldAgent class, task log, results output. Update rig import path. Add `phase_log_file` and `phase_state_file` allocation, paths passed via MCP env.
- `src/run.py` — CLI entry. Preserve AgentDojo timeshifting: load via `get_shifted_suite(...)`, not raw `get_suite(...)`.
- `src/mcp_server.py` — MCP wrapper. Unchanged from v1 unless phase attribution needs updates.
- `src/date_shift.py` — suite adapter. Unchanged from v1.

**Phase lifecycle consumption in host:**
- Read `phase_log_file` NDJSON events
- Read `phase_state_file` current pointer
- Attribute MCP calls to the correct worker based on `phase_state_file` at call time
- Surface `session_id` and `session_ids` as top-level JSONL fields (from execution log)
- Results format: keep debug field shape compatible with v1 analysis scripts where practical, but do not reintroduce loop architecture to satisfy that compatibility. `execution_log` and `phase_events` are the source of truth; `planner_iterations` may exist only as a host-derived view over planner tool invocations.

**Attack task support:**
- Agent entrypoint is unchanged between benign and attack runs
- Injection content enters through the MCP server (via AgentDojo fixtures)
- Verify records correctly label injected data fields as `untrusted`
- Verify `untrusted-llms-get-influenced` rule fires on influenced data paths

**Workspace domain migration:**
- `bench/domains/workspace/records.mld`
  - Keep the shipped input-record shape only
  - Express input policy through top-level sections, not legacy fields
  - Harden trust/display/handle choices where they are now load-bearing
- `bench/domains/workspace/tools.mld`
  - Keep every workspace tool on `inputs: @record`
  - Use `can_authorize`, not legacy auth keys
  - Delete any remaining duplicated schema metadata or runtime-only bridge structure that only survived the earlier `var tools` bug
- `bench/agents/workspace.mld`
  - Keep the agent entrypoint small and unchanged in role
  - Collapse any planner/runtime catalog duplication now that the same catalog can serve both purposes

**Reference:** existing v1 suite at `~/mlld/benchmarks/llm/domains/workspace/`.

**Exit:**
- A simple lookup-and-answer task passes on the dev harness without framework errors (pick a workspace task that reads a single record and composes from it; do not use `user_task_13` or any instruction-following task as the canary, and do not gate on `user_task_31` because the Hawaii packing-list evaluator is brittle on exact wording — see "Explicitly out of scope" below)
- Host uses the date-shift adapter for suite loading
- Results JSONL includes `session_id`, `execution_log`, and `phase_events` populated (non-empty)
- Workspace contains no duplicated tool-catalog surface across planner/runtime paths
- Workspace uses top-level policy sections wherever they apply; no `updateArgs` / `exactPayloadArgs` remain in workspace once those sections are live
- Workspace has deterministic regression coverage proving the clean agent entrypoint does not need a shadow planner catalog or runtime bridge catalog
- Workspace runs on the persistent planner tool-use path only; no clean workspace code path relies on planner resume or per-turn planner prompt reconstruction
- Full 40-task workspace suite on the dev harness/model confirms the framework path is clean (no framework-level failures; task-level utility numbers are informational on the cheap model)
- Final measurement run: full 40-task workspace suite on Sonnet 4 (`--harness claude --model claude-sonnet-4-20250514`). 0% ASR on injection tasks. Utility target set after the run — do not pre-commit a percentage that pressures accommodation of excluded tasks.

### Step 9: Remaining suites verification and cleanup

Banking, slack, and travel are already migrated onto the new surface. This step is to finish the same cleanup and real-run verification that workspace goes through, in that order.

**Banking specifics:**
- Strict control/payload separation (id vs recipient vs amount)
- `correlate: true` where cross-record mixing is the attack class (`update_scheduled_transaction` and similar)
- Express verbatim payload requirements through the top-level `exact` section, not `exactPayloadArgs`
- Express partial-update requirements through the top-level `update` section, not `updateArgs`
- `update_password` should be `can_authorize: false` (hard-deny in synthesized policy)

**Slack specifics:**
- Literal-source extract — webpage fetch must work as a first-phase extract without requiring prior resolve
- Derive for ranking (most active user, largest channel) with selection refs into write args
- Target-carry bugs to avoid: `External_0` (not `external_channel`), `Eve` (not `eve`)

**Travel specifics:**
- Multi-domain derive (hotels + restaurants + cars in one task) — biggest stress test for derive generality
- Booking operations in their own policy category (not `destructive`) — structural decision from prior iteration
- Recommendation-hijack tasks accepted as misses (advice phase out of v2 scope)

**Suite-wide migration rule:**
- Input records are the single schema source
- Top-level policy sections are the single input-policy source
- The tool catalog is the single authored source for planner and runtime metadata
- No suite adds defensive wrappers, bridge catalogs, or mixed-shape helpers to preserve old metadata once the new surface is available

**Exit:**
- All 4 suites run end-to-end on the dev harness (`--harness opencode --model openrouter/z-ai/glm-5.1`) with no framework failures
- Per-suite dev-harness runs confirm the framework path is clean (utility numbers will be lower on the cheap model — that's expected; the measurement is that the flow runs)
- All 4 suites express exact/update-style policy through the new top-level sections, not legacy fields
- All 4 suites use a single authored tool catalog shape with no planner/runtime bridge duplication
- All 4 suites run through the persistent planner tool-use architecture only
- Per-suite deterministic checks prove the clean single-catalog shape remains in place after migration
- Final measurement pass on Sonnet 4: 0% ASR on all injection tasks
- Utility targets are set after the first clean Sonnet 4 run, excluding tasks that require instruction-following over tainted content or recommendation evaluation against influenced content (see "Explicitly out of scope"). Do not pre-commit numeric targets that pressure accommodation of excluded tasks.

### Step 10: Make rig read the new shape directly

**Goal:** Remove the "new shape translated back into fake legacy operation objects" architecture. This is where the implementation becomes clean rather than merely migrated.

**Files:**
- `rig/tooling.mld`
- `rig/intent.mld`
- `rig/runtime.mld`

**Add / change:**
- Read `facts`, `data`, `bind`, `correlate`, and the top-level policy sections directly from input records
- Make `@toolSemantics` render `description` and `instructions` as separate structured sections
- Simplify `@mergedToolEntry` so it disappears as a compatibility shim and leaves one direct tool-entry path
- Remove synthetic legacy schema translation for tools that already have `inputs: @record`
- Remove runtime lookup paths that assume a separate planner catalog and `toolsCollection` bridge
- Read `can_authorize` directly throughout the rig surface; legacy authored `authorizable` does not survive in clean code

**Rule for this step:**
- Do not keep fallback branches for replaced schema fields "just in case"
- If a suite is migrated, rig reads the migrated shape directly
- No wrapper/normalize layer that strips structured values or hides the real contract
- No planner/runtime catalog merge layer once both sides already share the same authored entry

**Exit:**
- Rig no longer conceptually depends on legacy operation schema for migrated tools
- Rig no longer conceptually depends on a separate runtime bridge catalog for migrated tools
- Description and instructions remain structurally separate in planner-facing docs
- Policy compilation clearly uses the new top-level sections, not compatibility translation

### Step 11: Record hardening and sample-quality pass

**Goal:** Make the migrated sample app exemplary, not merely functional.

**Files:**
- All suite `records.mld`
- `rig/EXAMPLE.mld`

**Tasks:**
- Split `data:` into `{ trusted, untrusted }` where meaningful
- Convert proof-bearing worker-return ids to `handle`
- Make `correlate:` explicit on semantically important records instead of relying on defaults everywhere
- Verify display-key behavior with `DK-1` / `DK-2`
- If `role:*` display keys are the real canonical form, standardize on them in one sweep
- Ensure examples and records use only the existing mlld optional syntax: `name: type?`

**Exit:**
- Records express trust, proof, and correlation intentionally
- Example and suite records reflect the best version of the feature set, not a half-migrated compromise

### Step 12: Final cleanup and deletion of replaced surfaces

**Goal:** Delete every deprecated surface that now has a real replacement. The target here is a clean implementation, not defensive coexistence.

**Delete after Steps 8-11 are complete:**
- Synthetic legacy `@toolOperation` path
- Mixed-shape branches in `@mergedToolEntry` that only exist for migrated tools
- Shadow plain-object planner catalogs introduced as a workaround for broken `var tools` metadata readback
- Companion runtime `var tools` bridge catalogs introduced only to preserve dispatch semantics during the P0 bug window
- Planner decision schema / parse / retry machinery from the outer-loop architecture
- Planner prompt reconstruction from `state_summary` and `execution_log`
- Planner `resume` threading and `planner_session_id` run-state
- Loop-counter planner orchestration and any helpers that only existed to rebuild planner context between planner turns
- Legacy fallback reads for:
  - `controlArgs`
  - `payloadArgs`
  - `sourceArgs`
  - `expose`
  - `optional`
  where `inputs: @record` already replaces them
- Legacy authored tool key `authorizable`
- Legacy input-policy fields replaced by top-level sections:
  - `updateArgs`
  - `exactPayloadArgs`

**Also in this step — primitive migration (new mlld primitives replace rig workarounds):**

Four mlld primitives landed that replace rig-side compensations. Migrate rig onto them and delete the workarounds:

1. ~~**Session migration**~~ ✓ (`var session` replaces shelf-based `session.mld`):
   - `session.mld` collapsed from 111 lines to ~25 lines
   - `workers/planner.mld` wrappers use `@planner.*` session accessors
   - `runPlannerSession` attaches session via `with { session: @planner, seed: {...} }` directly on the provider call (`@opencode`/`@claude`), reads final state from `@raw.mx.sessions.planner`
   - Test invariants restructured to use `exe llm` session frames
   - Deleted: shelf declaration, 4 slot records, `@slotValue`, `@resetPlannerSession`, `@initializePlannerSession`, all getter/setter exes, the global shelf singleton
   - Bugs found + fixed: `var tools` collection dispatch didn't propagate session frames (m-87eb); session must attach to provider call not routing wrapper
   - Gate must stay green throughout
2. ~~**Wrapper factory extraction**~~ ✓ (session + guards replace copy-paste boilerplate):
   - `@settlePhaseDispatch` extracted: shared error-path/budget/runtime/finish logic
   - Four non-terminal wrappers collapsed from ~30 to ~15 lines each (net +35/-215)
3. **Delete `direct: true`** (default object dispatch makes it unnecessary):
   - Strip `direct: true` from all six planner-tool entries in `workers/planner.mld`
   - Simplify dispatch branching in `runtime.mld` `@callToolWithOptionalPolicy`
   - **Blocked**: runtime.mld dispatch doesn't yet recognize `inputs: @record` as implying object dispatch
4. **Delete optional-fact workarounds** (optional fact omission in `@policy.build` makes them unnecessary):
   - Delete `@omittedOptionalControlIntent`, `@allControlArgsOptional`, `@omitUnknownTargetRules`, and the `optionalControlArgsOmitted` branch from `workers/execute.mld`
   - **Blocked**: `@policy.build` doesn't accept `{ allow: [op] }` for tools where all control args are optional and omitted
5. **Simplify tool-catalog helpers** (reflection completeness reduces crawler complexity):
   - Collapse or delete `@pairsToObject`, `@toolCatalogObject`, `@toolEntryObject`, and most `@tool*Args` helpers in `tooling.mld`

**Also in this step — review-derived cleanup (independent of primitive migration):**

6. ~~**Delete stale guards**~~ ✓: `guards.mld` deleted entirely (309 lines, unreferenced by any module)
7. **Prompt split**: `@rig.build` accepts optional `prompts:` config for suite addendum templates; move domain-specific rules out of `rig/prompts/planner.att` into `bench/domains/<suite>/prompts/`; per-tool knowledge goes in tool entry `instructions:` field
8. **Delete `@phaseToolDocs`**: provider `<tool_notes>` auto-injection already covers per-tool docs; spike to confirm coverage first, then delete redundant prompt-body rendering from `tooling.mld` and `workers/planner.mld`
9. **MCP coercion audit**: classify `_coerce_tool_args` rules in `src/mcp_server.py` as (a) generic normalization, (b) AgentDojo-specific overfitting, or (c) planner-mistake masking; keep (a) with labels, delete (b) and (c)

**Also in this step (from the original plan):**
- Extract the framework label schema from inline rig code into a declarative schema file
- Add `LS-*` tests for unknown/conflicting/missing framework labels

**Explicit non-goal of this step:**
- Do not preserve deprecated functionality or old cruft defensively
- Do not invent interim substitutes for `supply:`

**Exit:**
- Deprecated replaced surfaces are gone, not merely unused
- Remaining compatibility debt is explicit and limited to truly deferred features, chiefly `supply:`
- Rig and bench present a single coherent modern shape

### Step 12b: Prompt education and pattern testing

**Goal:** Get the planner to reliably use the rig tool-use protocol by improving prompt clarity and validating via isolated pattern tests. This is the main utility lever — the framework is correct but the planner doesn't exercise it efficiently.

**Context:** Full-suite baseline on GLM 5.1 (post session-migration, post OOM fix, budget=25): workspace 38-42%, banking 37-44%, slack 24-38%, travel 5%. The framework path is clean (no crashes, no infra errors). Failures are dominated by planner-quality: resolved-ref confusion, wrong-phase tool calls, and repeated failed executes. See `tmp/investigation-planner-looping.md` for the full diagnosis.

**Pattern tests (isolated, ~$0.01 each, ~30s per run):**

Build standalone tests at `rig/tests/patterns/` that exercise one planner behavior pattern each. Each test sets up a minimal agent (1-2 tools, simple task) and runs one planner session on GLM 5.1. Iterate on the prompt until the pattern passes reliably.

Patterns to test:
1. **resolve → execute with resolved ref** — the #1 failure. Task: "look up contact Alice, send her an email." Planner must resolve contact → construct `{ source: "resolved", handle: "r_contact_...", field: "email" }` → execute send_email.
2. **resolve → resolve with resolved ref** — using a resolved value as arg to another resolve. Task: "get channels, read messages from general." Planner must resolve channels → use resolved channel handle as arg to read_channel_messages.
3. **source-backed extract from state** — extract typed payload from a resolved record. Task: "get the email, extract its body." Planner must resolve email → extract source from resolved state.
4. **derive → execute with selection ref** — derive selects among resolved values. Task: "find cheapest hotel, book it." Planner must resolve hotels → derive cheapest → execute with selection ref.
5. **wrong-phase recovery** — model corrects after 1 wrong-phase error (not 4). Task: call a resolve tool via extract, verify model switches within 2 attempts.

**Prompt restructure:**

After patterns 1-5 pass reliably, restructure `rig/prompts/planner.att`:
- **Core framework prompt** (rig-owned): phase rules, ref grammar, terminal rules, budget discipline. Generic. No suite knowledge.
- **Suite addendum** (bench-owned, via `@rig.build({ prompts: { plannerAddendum: ... } })`): domain-specific rules currently at planner.att:65-66. Move to `bench/domains/<suite>/prompts/planner-addendum.att`.
- **Per-tool knowledge** stays in tool entry `instructions:` field. The provider `<tool_notes>` mechanism delivers these to the LLM alongside the tool schema.

**Error message improvements:**

Improve the structured error messages that tool wrappers return on common mistakes:
- `known_value_not_in_task_text` → include "This value came from a prior resolve. Use { source: 'resolved', record: '<type>', handle: '<handle>' } instead of { source: 'known' }."
- Wrong-phase tool call → after 2nd repetition, auto-route through the correct phase instead of returning another error.
- `control_ref_requires_specific_instance` → include "You passed a family ref. Pick a specific handle from your prior resolve results."

**Exit:**
- All 5 pattern tests pass reliably on GLM 5.1 (3/3 runs each)
- Planner prompt split into rig generic + suite addendum
- No task-shaped rules remain in `rig/prompts/planner.att`
- Error messages guide the model to the correct ref shape on first correction
- Full-suite rerun shows measurable improvement (target: workspace >60%, slack >40%)

### Step 13: Cutover

**Goal:** Replace v1 with v2 after the clean migration and deletion work is finished.

**Steps:**
1. Verify v2 passes all 4 suites at baseline with the clean migrated shape
2. `mv ~/mlld/rig ~/mlld/rig-v1-archive`
3. `mv ~/mlld/clean/rig ~/mlld/rig`
4. `mv ~/mlld/benchmarks ~/mlld/benchmarks-v1-archive`
5. `mv ~/mlld/clean/bench ~/mlld/benchmarks`
6. Update import paths in any external consumers
7. Rerun full suite to confirm paths are clean
8. Update documentation

## Implementation Notes

### Don't co-locate v1 patterns with v2 files

When referencing a v1 pattern, read it from `~/mlld/rig/` and write the v2 equivalent fresh in `~/mlld/clean/rig/`. Don't copy-paste and then edit — the shape is different enough that copying causes drift.

### Use spike code as reference, not copy source

The spikes show the primitives working. The real implementation in rig v2 will be different because it's integrated with the persistent planner tool-use architecture. Cite the spike, understand the mechanism, implement cleanly in v2.

### Test at each step

Every step produces a runnable test. Don't proceed without passing the test. If a test requires a primitive that isn't built yet, the step is incorrectly scoped — split it.

### No transitional coexistence

v2 files don't reference v1 files. v2 tests don't run against v1 code. The only v1 artifact that matters is the spike directory, and that's read-only reference material.

Where a shipped v2 surface replaces an old field or helper, delete the old surface after migration. Do not keep deprecated input-policy fields, duplicate schema metadata, or mixed-shape helper branches around defensively.

### Keep it small

The full rig v2 framework target: ~1200 lines of mlld. Each benchmark suite: ~400 lines. Full bench Python host: ~700 lines (mostly unchanged from v1). Total: ~4000 lines. If any one file grows past 400 lines, it's probably doing too much.

### Contract tests (zero-LLM regression guard)

First-class requirement, not a spike. Rig v2 ships with `rig/tests/index.mld` — a deterministic integration smoke modeled on `~/mlld/rig/spike/34-integration-smoke/smoke.mld`. Runs in <1 second with zero LLM calls. Each assertion is named after the invariant it verifies.

Coverage must include at least:
- `@policy.build` runtime primitive: accepts a minimal hand-constructed policy, returns `valid: true` (Step 1 baseline — verifies runtime, not the synthesizer)
- Rig policy synthesizer: known tool catalog input produces expected synthesized policy (Step 4 — verifies the rig-layer synthesis)
- Tool collection round-trips through runtime parameter binding
- `.mx.params`, `.mx.controlArgs`, `.mx.factsources` accessible on exes
- Cross-module exe `.mx.labels` round-trip
- `@toolDocs` renders control-arg annotations correctly
- Top-level policy sections round-trip from record declaration into rig enforcement (`allowlist`, `blocklist`, `exact`, `update`, `optional_benign`)
- Thin-arrow strict mode: exe with only `->` does not leak tool-slot value
- Persistent planner tool-use path does not pass `resume`
- Planner-facing extract / derive tool results do not leak tainted payload content
- `compose` and `blocked` are terminal planner tools
- Tool-call budget exhaustion and repeated invalid-tool-call exhaustion terminate cleanly
- Selection ref lowering returns the expected resolved ref
- Provenance firewall: `{ source: "derived", ... }` in control-arg position is rejected at compile
- `allow` on a tool with controlArgs is rejected at planner intent validation
- Source class mismatch: attempting to reference an extracted value as `{ source: "resolved", ... }` is rejected
- Per-element proof check: array control arg with one element missing proof is rejected

Each assertion gets a short name (e.g., `firewall-derived-to-control`, `lowering-selection-ref`, `strict-thin-arrow`). A failure names the contract directly, not "some integration broke."

This test runs on every rig v2 change — PR checks, pre-commit, and before every benchmark run. The rig v1 pattern where `@mlld/rig` has a CLAUDE.md rule "first action: run the integration smoke" carries forward to v2 as `rig/tests/index.mld`.

### Test taxonomy

Three test kinds, each with a distinct purpose:

1. **Invariant tests** (`rig/tests/index.mld`) — zero-LLM deterministic assertions on individual primitives. Fast. Run on every change. Described above.
2. **Flow tests** (`rig/tests/flows/<phase>.mld`) — stub LLM, run the persistent planner tool-use session, verify end state. Run per implementation step as listed in Step 1-6 exit criteria. Catch integration bugs across planner tools and worker dispatch.
3. **Benchmark runs** (`bench/...`) — real LLM, real evaluation. Run at Step 8+ to measure utility and security against AgentDojo.

The first two require no network and no credentials. A failing rig change should be caught by (1) or (2), not discovered in (3).

### Lifecycle emission is not a nice-to-have

Phase lifecycle events ship in Step 1, not Step 5. Missing emission turned the previous benchmark run into hours of misdiagnosis. The host expects events; rig produces them. That contract is baseline, not deferred work.

Canonical event names (frozen): `planner_iteration`, `phase_start`, `phase_end`. The v1 host may still expect legacy names like `planner_step` — that's migration debt on the v1 host, not a rig concern. The v2 bench host uses canonical names (spike 43).

### Harness adapter

The default development harness is `@mlld/opencode` with `openrouter/z-ai/glm-5.1` as the default model. This is the cheap iteration path — every test, every canary run, every per-step flow verification runs on this by default.

```
--harness opencode --model openrouter/z-ai/glm-5.1
```

Spike 43 proved the provider/session primitives and lifecycle plumbing on opencode. The persistent tool-using planner path is proven in Step 1-4 implementation and must be green on the cheap harness before any suite verification.

Sonnet 4 (`--harness claude --model claude-sonnet-4-20250514`) is the measurement harness — used for:
- Final per-step exit verification when cheap harness passes
- Benchmark numbers that compare against CaMeL and v1 results
- Suite-completion verification at Step 8 and Step 9

The rule: develop on opencode/glm, measure on Claude/Sonnet. Cheap iteration without burning Claude credits. Sonnet runs only happen when the cheap harness is clean.

Provider-native resume is not part of the rig v2 architecture. The supported planner model is one persistent provider session per `@rig.run`, using provider tool use directly.

### Timeshifting is host behavior

Benchmark date shifting remains required in v2. Preserve the existing `clean/src/date_shift.py` behavior in the clean host so AgentDojo suites are loaded relative to the current day rather than the original fixture reference date. This is a runner concern, not a rig primitive and not app-level logic.

## Documentation

**In scope (required deliverables):**
- `rig/README.md` — brief public-facing intro, links to ARCHITECTURE/INTERFACE/PHASES/SECURITY
- `bench/README.md` — how to run the benchmark on v2, default harness flags, where results land
- `rig/CLAUDE.md` — agent-facing working rules (already drafted)

**Out of scope for v2 build (deferred):**
- Updates to `~/mlld/mlld/docs/` for rig v2. The mlld runtime docs describe primitives, not rig. Update those when/if rig becomes a distributed module. Not required for benchmark validity.
- Migration guide from v1 rig to v2. v1 is archived at cutover; apps that want to move will read the v2 specs.
- Tutorials and how-tos. Once v2 is stable, write these; not part of the build.

## Deferred From v2 Scope

Explicit decisions to defer, not oversights:

- **Instruction-following over tainted content.** Benchmark tasks that ask the agent to "do the actions specified in this email" (e.g., workspace `user_task_13`) are out of scope. The v2 architecture defends against indirect prompt injection by refusing to treat data fields as executable instructions — passing those utility tasks would require breaking that defense or building a separate typed-instruction channel orthogonal to the current design. No mainstream injection defense passes these tasks on utility. These are expected misses. Do not use these tasks as canaries, exit gates, or utility targets. Do not add planner rules, prompt guidance, or worker behavior that tries to operationalize "follow instructions from tainted content."
- **Advice phase / recommendation-hijack defense.** Recommendation-class tasks run through normal derive → compose. Influenced-content-past-evaluation attacks are accepted misses. Revisit after v2 shape is settled.
- **Planner session corruption recovery.** Persistent planner context is the supported mechanism; session corruption terminates the run cleanly. No mid-run reset/reconstruction.
- **Provider-native resume.** Not part of the architecture. Do not add planner resume, planner-session stitching, or per-turn reconstruction fallbacks.
- **`supply:`.** Contributor-role constraints remain deferred. Do not invent interim substitutes or preserve deprecated provenance defaults defensively; adopt `supply:` when it ships and delete the temporary assumptions then.
- **Rigloop on v2.** Higher-level orchestration adapts to v2 after v2 benchmarks at baseline. Criteria for when rigloop comes back: v2 has benchmarked at baseline on Sonnet 4 AND v2 has a week of stability with no framework-level bugs surfacing in per-suite runs.
- **mlld runtime docs updates.** See Documentation section.

Revisit these only after v2 is working end-to-end with real benchmark numbers.

## What Rigloop Does (Not Yet)

Rigloop is not part of this build plan. After v2 is stable and benchmarking at baseline, rigloop can be adapted to run on v2 — but that's a separate effort.

## Validation

The plan is successful when:

- Rig v2 framework is <1500 lines of mlld
- Each suite is <500 lines of mlld (records + tools)
- Agent entrypoints are <25 lines each
- Dev-harness runs (`--harness opencode --model openrouter/z-ai/glm-5.1`) complete end-to-end on every suite with no framework failures
- Measurement run on Sonnet 4 hits 0% ASR across all 4 suites
- Utility numbers are recorded and reported, not pre-committed as acceptance criteria. Tasks in "Explicitly out of scope" are expected misses and do not factor into success.
- Deprecated input-policy fields replaced by top-level sections have been deleted, not left in compatibility mode
- Security invariants from `SECURITY.md` have assertions in `rig/tests/index.mld`
- Every spike referenced in `SPIKES.md` has corresponding v2 coverage (either in invariants or flow tests)
- Phase lifecycle events fire from Step 1 onward
- Every deliverable in the Cross-Cutting Work section is complete

## What Makes This Tractable

- The spikes already prove the primitives work. No research phase.
- The interface is frozen. No architectural drift during build.
- The build order is linear. Each step has a runnable exit.
- The old code isn't in scope. No deletion deadlock.
- The total code is small. ~4000 lines across framework + suites.

An agent or focused human should be able to execute this in days, not weeks.
