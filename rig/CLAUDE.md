# CLAUDE.md — @mlld/rig

## First action: run the invariant tests

Before touching anything in this repo, run:

```bash
mlld ~/mlld/rig/tests/index.mld
```

Target: under 1 second. Zero LLM cost. Assertion-named output so a failure tells you exactly which invariant regressed.

If the invariant tests are red, fix that before doing anything else.

## What this repo is

`@mlld/rig` is a mlld framework for defended capability-oriented agents. It owns the secure mechanics (phase loop, state, auth compilation, display projection, lifecycle emission) while apps declare records + tools.

See `ARCHITECTURE.md`, `INTERFACE.md`, `PHASES.md`, `SECURITY.md` for the architecture.

## Key paths

- `index.mld` — public surface, `@rig.build` and `@rig.run`
- `orchestration.mld` — phase loop, context build, worker dispatch
- `runtime.mld` — state helpers, tool dispatch primitives
- `intent.mld` — planner intent validation and source-class compilation
- `lifecycle.mld` — phase event emission and state pointer writes
- `workers/` — phase workers (planner, resolve, extract, derive, execute, compose)
- `prompts/` — `.att` prompt templates per worker
- `guards.mld` — structural decision validation
- `tooling.mld` — tool catalog helpers, op doc generation, policy synthesis
- `records.mld` — framework-internal records
- `tests/index.mld` — invariant tests (zero-LLM)
- `tests/flows/` — flow tests (stub LLM, per phase)

## Implementation principles

### Value handling

**Use mlld field access, not JS walkers.** `@val.field`, `@val.mx.field`, `@val[key]`, `@val.mx.data[key]` preserve wrappers and metadata. A JS helper that recursively strips `metadata`, `_mlld`, `type`, `text`, or `data` fields is a red flag — the presence of a `wrapperLike` check or a `normalize(value)` recursion means you're stripping exactly what the runtime needs.

**Preserve wrappers across boundaries.** Values flow through state, worker dispatches, and policy compilation carrying factsources, labels, and display metadata. A value that loses its wrapper mid-flow breaks the security model silently. The executable boundary is responsible for consuming the value — callers pass native values; the tool's typed parameter signature handles conversion once, at the edge.

**JS is appropriate for:** pure transformations on plain data (NDJSON serialization, scalar coercion, string formatting), narrow metadata reads via `value.mx.field`, file system operations, test stubs.

**JS is wrong for:** anywhere a value might need its wrapper downstream, "normalizing" or "plainifying" values, iterating record fields to rebuild objects, scalar unwrapping at dispatch.

### llm-first orchestration

**Keep the orchestration dumb.** Strategy lives in prompts, records, tool declarations, and execution log attestations. The orchestration is a loop that calls LLMs and dispatches workers; it does not reason about tasks.

**Structured decisions, not prose parsing.** Planner output is JSON validated against a schema. Worker output is typed attestation or record coercion. Regex on LLM prose to infer intent is an anti-pattern.

**One next action per iteration.** The planner returns one decision; the orchestration dispatches one worker; workers perform one unit of work. Multi-step tasks are planner-managed sequences.

**Typed state carries context, not conversation.** Resolved records, extracted/derived results, and execution log attestations are the authoritative carriers of cross-phase context.

**Display projection at boundaries, not in helpers.** Projection applies at prompt serialization and at LLM call bridges. Orchestration helpers should not preemptively strip data fields.

### Source class and proof

**Source class is authoritative. Never infer it.** Planner emits typed refs (`resolved` / `known` / `extracted` / `derived` / `selection` / `allow`). Rig validates the declared class against state provenance. A relabeled ref is rejected at compile.

**Selection refs are derive-only producers.** Only derive can mint selection refs; extract cannot. Rig validates that the backing ref points to an instance in the derive input set with original proof.

**Control args need proof-bearing values.** Only `resolved`, `known` (task-text-verified), or `selection` (rig-validated) can fill control args. `extracted` and `derived` scalars are payload-only.

**`->` is expression-scoped taint, not sanitization.** Security comes from what the expression contains plus display projection at record boundaries — not from the arrow syntax.

### Phase architecture

**Workers own their phase.** Each worker module implements its dispatch: context build, LLM call, output validation, state write. Orchestration calls `@dispatchResolve(...)`, `@dispatchExtract(...)`, etc.

**Each phase has one job:**
- **Resolve** obtains proof-bearing records via `=> record` coercion
- **Extract** reads tainted content and coerces to a typed payload (not proof-bearing; cannot produce selection refs)
- **Derive** reasons over typed inputs (can produce validated selection refs)
- **Execute** is one write under compiled authorization — no multi-write workers, no shelf scope
- **Compose** presents typed state; does not compute

### Schema and contract authority

**Write-payload schemas live with the write tool.** `tool.operation.payloadRecord` is the schema authority for write-preparation extract. No standalone contract catalog.

**Apps declare records + tools.** No shelf authoring, no policy wiring, no standalone contracts file. If a suite seems to need these, rig is missing a primitive — file a rig issue.

**Rig synthesizes policy from the tool catalog.** Suites provide overrides only for genuine additive extensions.

**Record authors match tool signatures exactly.** Payload record field types match the exe signature. Array args get array payload fields. Control-arg checking runs per-element on array-typed args.

### Test discipline

**Three test kinds:**
1. `tests/index.mld` — zero-LLM invariant assertions. Runs on every change.
2. `tests/flows/<phase>.mld` — stub-LLM flow tests.
3. `bench/...` — real benchmark runs.

A failing rig change should be caught by (1) or (2). If (3) discovers a bug not covered by (1)/(2), add an invariant test.

**Any benchmark failure that reveals a runtime or framework issue gets a zero-LLM invariant test before the fix is considered done.** Sequence: reproduce → write invariant test (fails) → fix → invariant test passes.

**Invariants must be falsifiable.** A good invariant test can distinguish "the protection is real" from "the protection is missing." Build a weakened fixture (no factsources, wrong provenance) and assert the protection fails there. If both real and weakened cases produce the same result, the test isn't testing what you think.

**Dev on cheap, measure on expensive.** Use the cheap harness for all iteration. Higher-capability runs are measurement passes — used only after the cheap harness confirms the flow is clean.

### Drift response

**When you find an anti-pattern, pin it with an invariant test.** The test is the lock against reintroduction. Write the test that fails first, then fix the code until it passes.

**Prefer deleting over patching.** A "fixed" helper is still a place for the anti-pattern to regrow. Replace callers with mlld native syntax.

**Name the drift explicitly in commits.** "Fix X" is worse than "Remove wrapper-strip from X." Future readers need to know what was wrong and why the change is correct.

### Scope

**Keep it small.** Any single file growing past ~400 lines is probably doing too much. Split it or simplify.

**Don't overfit to specific tasks.** If a contract name sounds like a task answer, a planner rule says "for case X do Y," or a guard checks a task-specific string, it's overfit. Primitives solve categories of tasks, not specific ones.

### Writing style

**Timeless comments.** Comments describe the code as it is now, not its history. No "previously this did X, now it does Y," no "added for ticket Z," no tombstones for removed code. Deleted code leaves no trace in comments.

**No backward-compatibility scaffolding.** When replacing an implementation, delete the old one. Don't keep shims, don't alias old names, don't branch on legacy shapes. The replacement is the implementation.

**Explain why when non-obvious.** Well-named identifiers carry the what. Comments exist for invariants, non-obvious constraints, and decisions a reader would otherwise reverse. If removing the comment wouldn't confuse someone reading the code cold, don't write it.

**No narrative in code.** Code is not a story. Don't describe what the reader is about to see. Don't announce sections with press-release language. Just name things well and let the code speak.

## Working rules

- This module is imported by `bench/agents/*.mld` — changes affect all benchmark suites.
- Runtime changes in `~/mlld/mlld/` that touch policy, shelf, handles, substrate exemption, or tool dispatch must pass `tests/index.mld` before merging.
- Apps declare records + tools. They do not author shelf, policy, or orchestration. If a suite seems to need one of these, rig is missing a primitive — file a rig issue.
- Per-suite domain content belongs in `bench/domains/<suite>/`, not here.
