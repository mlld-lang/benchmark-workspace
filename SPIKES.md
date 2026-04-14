# Spike Index

The existing rig v1 spikes at `~/mlld/rig/spike/` encode key design patterns. Implementations of rig v2 should cite these, not reinvent them.

## De-Risking Spikes for Rig v2

These six spikes were built specifically to prove v2 primitives work.

### 35-derive-provenance-firewall

**What it proves:** dynamic derive can stay useful without becoming a control-arg authorization hole.

**Location:** `~/mlld/rig/spike/35-derive-provenance-firewall/SCIENCE.md`

**Use when implementing:** derive worker dispatch, source class compilation for execute args, anywhere a derive or extract result might be referenced in an authorization.

**Key result:** derive/extract origin values carry distinct provenance; raw scalars cannot mint control-arg proof; selection refs to resolved instances preserve original fact proof.

### 36-planner-intent-compiler

**What it proves:** the planner-facing execute schema can shrink while still preserving source class explicitly.

**Location:** `~/mlld/rig/spike/36-planner-intent-compiler/SCIENCE.md`

**Use when implementing:** the `intent.mld` module that compiles typed planner decisions into bucketed `@policy.build` input.

**Key result:** source class (`resolved`, `known`, `extracted`, `derived`, `selection`, `allow`) can be expressed as typed refs in planner output; rig compiles these into the right bucket without heuristic inference.

### 37-records-and-ops-surface

**What it proves:** a toy app can complete a benign `resolve → derive → execute → compose` flow with only records + tool catalog as the app surface.

**Location:** `~/mlld/rig/spike/37-records-and-ops-surface/SCIENCE.md`

**Use when implementing:** the `@rig.build(config)` entry point, state storage generation from records, op docs generation from tool catalog.

**Key result:** no shelf.mld, no standalone contracts.mld, no policy.mld required for a working defended flow.

### 38-advice-gate-over-derive

**What it proves:** derive can prepare recommendation inputs without laundering influenced content, while the advice gate preserves the clean path.

**Location:** `~/mlld/rig/spike/38-advice-gate-over-derive/SCIENCE.md`

**Status for v2:** **Reference only — not implemented in v2.** The advice phase is deferred from v2 scope. Spike retains value as the reference for future work when advice-gate defense is built. For v2, recommendation tasks run through normal derive → compose; recommendation-hijack attacks are accepted misses.

### 39-phase-lifecycle-emission

**What it proves:** the benchmark host's expected lifecycle contract is stable and future-proof enough to support new phase types (derive, extract) without host-side changes.

**Location:** `~/mlld/rig/spike/39-phase-lifecycle-emission/SCIENCE.md`

**Use when implementing:** phase lifecycle emission from rig to the host's phase log file, in Step 1 of the build plan.

**Key result:** adding a new worker type doesn't require host-side changes; the emission format is extensible via a new `worker` string value.

### 40-parallel-ownership-drill

**What it proves:** a lightweight ownership protocol can make rewrite fanout operationally safe enough to use.

**Location:** `~/mlld/rig/spike/40-parallel-ownership-drill/SCIENCE.md`

**Use when implementing:** not directly applicable to rig v2 code — this spike covers migration process, not target architecture.

## Phase 0B Spikes (Post-Architecture-Correction)

These three spikes settled open questions that emerged when the architecture was corrected to keep extract as a distinct phase.

### 41-payload-record-driven-extract

**What it proves:** the schema authority for write-preparation extract can start at `tool.operation.payloadRecord`. No standalone contract registry is needed. Execute casts only the payload-arg subset; control args and bind-default args are merged separately. `exactPayloadArgs` still fire at execute.

**Location:** `~/mlld/rig/spike/41-payload-record-driven-extract/SCIENCE.md`

**Use when implementing:** the extract worker (Step 3) and the execute compile path (Step 5). This spike is why `contracts.mld` can die as a standalone catalog.

**Key result:** passed. Schema authority starts at `payloadRecord`. Execute applies `@cast` to the payload-arg subset only, then merges in control args and bind args.

### 42-extract-selection-ref-boundary

**What it proves:** extract cannot produce selection refs without creating a laundering path. Selection is a public execute-time source class, but as a **producer** it must be derive-only.

**Location:** `~/mlld/rig/spike/42-extract-selection-ref-boundary/SCIENCE.md`

**Use when implementing:** the extract worker output validation (Step 3) and the derive worker output validation (Step 4). If an extract worker's output contains a selection ref, rig rejects the output.

**Key result:** passed with a MIXED criterion — extract-produced selection refs are a laundering path. Rule: selection refs stay public as a source class; derive is the only producer.

### 43-llmcall-harness-protocol

**What it proves:** the new rig contract works with `@mlld/opencode` using prompt-disciplined JSON plus `@parse.llm`. Session IDs are available. Malformed output has a usable retry shape. One structural retry works. Lifecycle events emit cleanly.

**Location:** `~/mlld/rig/spike/43-llmcall-harness-protocol/SCIENCE.md`

**Use when implementing:** the planner and worker LLM call wrappers throughout. Confirms Claude is not the only supported harness for v2.

**Key result:** passed on the local opencode path for no-tool protocol behavior. Caveat: the live v1 host still expects legacy naming (`planner_step`); v2 host uses canonical names (`planner_iteration`, `phase_start`, `phase_end`). Tool-using path on opencode is not fully proven but not a blocker — it's an early Step 1/2 implementation check.

## Legacy Spikes Worth Preserving

These pre-v2 spikes encode working patterns that rig v2 implementation should cite.

### 03-display-projection-shelf

**What it proves:** `@<record>.mx` exposes display schema to user code; per-role display modes work as expected.

**Location:** `~/mlld/rig/spike/03-display-projection-shelf/`

**Use when implementing:** display projection at worker boundaries, role-based rendering of state into the planner prompt. Directly relevant to the resolve phase display contract.

### 04-thin-arrow-channel

**What it proves:** `->` and `=->` return channels have expression-scoped taint; strict mode prevents fallback leaks.

**Location:** `~/mlld/rig/spike/04-thin-arrow-channel/`

**Use when implementing:** worker return expressions for resolve, extract, derive, execute, compose.

### 06-handle-roundtrip-shelve

**What it proves:** handle-bearing values survive shelf I/O roundtrips — labels, factsources, and display projections are preserved.

**Location:** `~/mlld/rig/spike/06-handle-roundtrip-shelve/`

**Use when implementing:** state storage for resolved records. Rig v2 doesn't use a user-facing shelf, but internally it uses the same primitives, and handle preservation is load-bearing for cross-phase ref resolution.

### 01-cross-phase-shelf-derived-bucket

**What it proves:** `@policy.build` accepts `known` entries via registry walk; values minted in prior phases auto-upgrade when referenced by value.

**Location:** `~/mlld/benchmarks/spikes/01-cross-phase-shelf-derived-bucket/`

**Use when implementing:** execute phase authorization compilation, the `known → resolved` auto-upgrade path in `@policy.build`. Relevant to how resolved refs carry proof through from prior phases.

### 02-tooldocs-vs-toolnames

**What it proves:** `@toolDocs` renders per-tool arg lists with policy-derived classification, generated from tool metadata.

**Location:** `~/mlld/benchmarks/spikes/02-tooldocs-vs-toolnames/`

**Use when implementing:** auto-generated op docs for the planner prompt. Rig v2's tool catalog metadata feeds directly into this path.

### 34-integration-smoke

**What it proves:** 13 cross-module contracts the runtime must hold (policy compilation, tool dispatch, label flow, strict mode, substrate exemption, controlArgs metadata, toolDocs rendering).

**Location:** `~/mlld/rig/spike/34-integration-smoke/`

**Use when implementing:** regression coverage. Port the relevant assertions to rig v2's test suite.

## Spike Summaries

- Phase 0 de-risking: `~/mlld/tmp/phase0-spikes-summary.md`
- Phase 0B corrections (extract, selection, harness): `~/mlld/tmp/phase0b-spikes-summary.md`

## What Spikes Don't Cover

The spikes prove primitives work. They do not replace:

- End-to-end integration with the benchmark host (phase_log_file wiring is sketched in spike 39 but needs full integration)
- Multi-suite validation (each spike is one synthetic scenario)
- Performance characterization (spikes are correctness probes, not benchmarks)
- Prompt quality under Sonnet 4 load (spikes often use Haiku or synthetic LLM responses)

Rig v2 implementation must add coverage for these.
