# Rig v2 Implementation Remediation

The current implementation has a structural problem: `orchestration.mld` (3091 lines) is built around JS helper functions that strip mlld StructuredValue wrappers. This contradicts the security model — those wrappers carry factsources, labels, and display projections.

This document specifies what to keep, what to simplify, what to rewrite, and what to expand. The architecture in `ARCHITECTURE.md`, `INTERFACE.md`, `PHASES.md`, `SECURITY.md`, and `PLAN.md` is unchanged. This is execution remediation only.

## Status by file

### KEEP AS-IS

| File | Lines | Why |
|---|---|---|
| `rig/index.mld` | 113 | Clean public surface matching `INTERFACE.md` exactly |
| `rig/records.mld` | 84 | Correct framework-internal records with `validate: "demote"` |
| `rig/lifecycle.mld` | 113 | Correct host integration via `sh {}` for file I/O; no normalization |
| `rig/tooling.mld` | (small) | Verify it has no normalize-style helpers; if clean, keep |
| `rig/guards.mld` | (small) | Verify guards use mlld field access; if clean, keep |
| `rig/prompts/*.att` | — | Verify they reference `role:planner`/`role:worker` correctly; assume clean unless found otherwise |
| `rig/tests/index.mld` | — | Keep the test entry pattern; assertions need to grow |
| `rig/tests/fixtures.mld`, `helpers.mld` | — | Keep test infrastructure |

### SIMPLIFY

#### `rig/intent.mld` (currently 941 lines)

**Status:** Logic is correct in security-critical paths. Specifically `@factAttestations` and `@constraintEqValue` correctly extract factsources from `value.metadata.factsources` before plainification. The proof chain into `@policy.build` works.

**What to remove:**
- `@plainRef`, `@refFieldValue` — these are JS helpers doing the same `wrapperLike` strip as orchestration. Replace with mlld field access at every call site.
- `@constraintEqValue` JS implementation — this can stay JS since it's producing a value for `@policy.build` consumption (which expects plain `eq` values), BUT it should be exactly that: extract the value, no recursive normalize. ~10 lines, not 35.

**What to keep:**
- `@factAttestations` — it correctly reads `value.metadata?.factsources`. This is the right pattern for accessing metadata in JS. Keep it; treat as the model for any other metadata-reading helpers.
- The multi-fallback field access patterns in `@resolvedEntryFieldValue` (`@entry.value.mx.data[fieldKey]` then `@entry.value.data[fieldKey]` then `@entry.value[fieldKey]`) — these handle real wrapper-shape variation across module boundaries. Keep them.
- The bucket and named-state unwrap helpers (`@stateBucketObject`, `@namedStateEntry`) — they only unwrap one level of the bucket container, leaving entry values native. Correct shape.

**Target line count:** ~500 lines (cut ~45%).

### REWRITE FROM SCRATCH

#### `rig/orchestration.mld` (currently 3091 lines)

The file is contaminated by the wrapper-stripping pattern at every layer. Surgical fixes won't work because callers depend on the stripped output shape.

**Delete entirely:**
- `@plainValue`, `@objectField`, `@valueField`, `@bridgeArgValue`, `@mergePlainObjects`, `@pickPlainFields`, `@hasNonNullFieldValue`, `@normalizedIdentifierFieldValue`, `@runtimeArgValue`, `@runtimeScalarText`, `@finalizeCollectionDispatchArgs`, `@setNamedStateField`, `@displayModeEntry`, `@extractPreviewFields`, `@stateHandle`, `@correlatedControlArgsCheck`, `@constraintEqArgs`, `@refSource`, `@nonComposeDecisionArgIssues`, `@dispatchArgsForExecute`, `@idLikeArgName`
- Any other helper whose body contains `wrapperLike =`, `value.metadata !== undefined`, or recursive `normalize(value)` patterns

**Keep functionally** (rewrite cleanly using mlld field access):
- `@validateConfig` — validates the config from `@rig.build`. Use `@config.records.isDefined()`, not `@objectField(@config, "records")`.
- `@synthesizedPolicy` — the policy synthesizer. Walks the tool catalog and builds the policy object. Use mlld iteration; no JS recursion.
- `@runPhaseLoop` — the loop. Calls planner, dispatches workers, accumulates execution log.
- `@stubLlmResponse` — for tests; this CAN be JS since it returns plain test fixtures.
- `@llmSessionId`, `@normalizeSessionId` — session ID extraction. Should be 5-line helpers, not normalize-recursive-strip patterns.
- `@logLlmCall`, `@llmCallEntry` — debug logging. These can serialize plain output via `| @pretty` or a single `JSON.stringify` at the file boundary. Don't recursively strip values.

**Move into workers:**
- All phase-specific dispatch logic. Resolve worker owns resolve dispatch. Extract worker owns extract dispatch. Etc.
- The orchestrator calls `@dispatchResolve(state, decision)`, `@dispatchExtract(state, decision)`, etc. Each worker module exports its dispatch function.

**Cross-cutting work that stays in orchestration:**
- Phase loop control flow
- State store read/write helpers (using mlld field access throughout)
- Planner context build (assembling the planner prompt from state, log, tool docs)
- Lifecycle event emission calls (delegates to `lifecycle.mld`)
- Execution log append

**Target line count:** 600-800 lines.

### EXPAND

Workers should grow from shells (11-40 lines) to phase implementations (100-200 lines each).

#### `rig/workers/resolve.mld`

**Add:**
- `@dispatchResolve(state, decision, agent)` — the full resolve dispatch
- Worker LLM call inside box with `display: "role:worker"` and read-tool subset
- Tool result coercion via `=> record`
- State write of resolved records
- Attestation construction

**Reference:** the resolve-dispatch logic currently in orchestration.mld. Extract it; rewrite using mlld field access; remove all wrapper-stripping.

#### `rig/workers/extract.mld`

**Add:**
- `@dispatchExtract(state, decision, agent)` — the full extract dispatch
- Source content pre-read (via mlld access on the state ref)
- Worker LLM call inside box with `tools: []` and `display: "role:worker"`
- Result schema validation (use record `@cast` against the planner-supplied schema or the write tool's `payloadRecord`)
- Reject any selection_refs in extract output (extract cannot produce them — see SECURITY.md §4)
- Storage under `extracted.<name>` with provenance metadata

**Currently has 40 lines** — the most filled-in worker. Use as the template shape for the others.

#### `rig/workers/derive.mld`

**Add:**
- `@dispatchDerive(state, decision, agent)` — the full derive dispatch
- Source pre-read across multiple sources
- Worker LLM call inside box with `tools: []`
- Result schema validation
- **Selection ref validation**: each selection_ref in the worker output must point to an instance in the derive input set with original proof. Reject invalid selection refs.
- Storage under `derived.<name>` with provenance metadata

#### `rig/workers/execute.mld`

**Add:**
- `@dispatchExecute(state, decision, agent)` — the full execute dispatch
- Calls `@compileExecuteIntent(state, decision, agent.tools)` to compile typed args into bucketed intent + payload
- Calls `@policy.build(intent, tools, { task: query })`
- If valid: dispatch the write tool with the compiled policy fragment merged into the agent base policy
- If invalid: return denial attestation with issues
- Result handling and state update for write outputs

**Critical:** the dispatched arg values must keep their wrappers. Don't strip them via JS helpers. The runtime needs `correlate-control-args` and any per-dispatch checks to see factsources.

#### `rig/workers/planner.mld`

**Add:**
- `@dispatchPlanner(context, agent)` — the planner LLM call
- Box with `display: "role:planner"` and the planner tool subset
- Decision schema validation (against `@plannerDecision`)
- Single retry on schema failure with hint prompt
- Returns the validated decision

#### `rig/workers/compose.mld`

**Add:**
- `@dispatchCompose(state, decision, agent)` — the compose call
- Source pre-read (with display projection applied)
- Box with `tools: []` and `display: "role:worker"`
- Returns `=-> @composedText`

## Discipline rules for the rewrite

These apply to all touched files, not just rewrites.

### Field access

- Use mlld field access: `@val.field`, `@val.mx.field`, `@val[key]`
- Do NOT define a JS helper that takes a value and returns a "field" via recursive walking
- mlld's field access auto-handles wrapper unwrapping while preserving metadata

### Iteration

- Use mlld `for @item in @list`, `@list.map(@fn)`, `@list.filter(@fn)`
- Do NOT iterate in JS that returns plain objects; that strips metadata from each item

### Object construction

- Use mlld object literals: `{ key: @value, other: @other }`
- Use spread: `{ ...@base, key: @value }`
- Do NOT build objects in JS by walking keys and calling `normalize(value)` per entry

### When JS is appropriate

- Pure transformations on already-plain data (NDJSON serialization, scalar arithmetic, string formatting)
- Reading metadata via `value.metadata?.factsources` — explicit, narrow access for one purpose
- Writing to file system (already isolated in `lifecycle.mld`)
- Stubbing LLM responses for tests

### When JS is wrong

- Anywhere you might pass a value that needs to keep its wrapper for downstream security checks
- Anywhere the input could be a record (instead, coerce via `@cast` or use mlld field access)
- Anywhere you're "normalizing" or "plainifying" — that's a sign you're stripping metadata

### `.keep` for explicit metadata access

If a JS block legitimately needs `.mx` metadata, the value must be passed with `.keep`:

```mlld
exe @readFactsources(value) = js {
  // value.data is the underlying value
  // value.mx is the metadata
  return value.mx?.factsources ?? [];
}

let @sources = @readFactsources(@someValue.keep)
```

Use this only where genuinely needed. Default is mlld field access.

## Verification before continuing

After the rewrite, before continuing to Step 7 (workspace suite):

1. **Invariant test for proof chain.** Add to `tests/index.mld`:
   - Synthetic record with a fact field
   - Manually create a state entry with that record's value
   - Call execute compile path with `{ source: "resolved", record, handle, field }`
   - Assert the compiled intent has `attestations: ["fact:..."]` for the value
   - This proves factsources survive the resolved → execute path

2. **Invariant test for correlate-control-args.** Add to `tests/index.mld`:
   - Two records with different `instanceKey` values
   - Try to dispatch a write tool with `correlateControlArgs: true` mixing one record's id with another's recipient
   - Assert dispatch is denied with the correlate-control-args error
   - This proves dispatch-time checks see factsources

3. **Invariant test for derived → control-arg rejection.** Add to `tests/index.mld`:
   - Compile execute intent with `{ source: "derived", name, field }` in a control arg position
   - Assert the compilation rejects with `provenance_firewall_violation` or similar
   - This proves the firewall is structural

4. **Line count check.**
   - `wc -l rig/orchestration.mld` should be ≤ 800
   - `wc -l rig/intent.mld` should be ≤ 600
   - Total framework: `wc -l rig/*.mld rig/workers/*.mld` should be ≤ 1500

5. **Wrapper-strip pattern audit.**
   - `grep -c "wrapperLike\|value.metadata !== undefined" rig/*.mld rig/workers/*.mld`
   - Should return 0 outside `intent.mld`'s `@factAttestations` (the legitimate metadata reader)

If any of these fail, the rewrite isn't done.

## Order of operations

1. Add the 3 invariant tests above to `tests/index.mld` (they will fail against current code; that's fine — they pin the requirements)
2. Rewrite `orchestration.mld` from scratch
3. Expand each worker
4. Simplify `intent.mld`
5. Run `tests/index.mld` — invariants must pass
6. Run `tests/flows/*.mld` — flow tests must pass on the dev harness (`--harness opencode --model openrouter/z-ai/glm-5.1`)
7. Only then proceed to Step 7 (workspace suite)

## What success looks like

- `orchestration.mld` is one orderly file with no normalize-recursive helpers
- Workers are the unit of phase work
- The proof chain from resolve → execute is verifiable in invariant tests
- The framework total is under 1500 lines
- The wrapper-strip pattern appears nowhere except `@factAttestations` (which reads metadata correctly)

## What this is not

- Not a redesign. Architecture, interface, security model, build plan are unchanged.
- Not an apology for the current code. The drift is concrete and the fix is concrete.
- Not optional. Continuing to build on the current orchestration.mld will compound the security regression risk and burn the line budget before workspace ports.
