# Persistent Planner Session and Worker Dispatch

How rig orchestrates a task. This is the implementation contract for the single persistent planner session: one planner LLM call owns the tool loop, rig-owned planner tools dispatch the workers, and lifecycle/state mutation happen inside those wrappers.

## The Session

```
build_context(agent, query)
  → planner_prompt, planner_tools, planner_display

planner_llm_call(planner_prompt, tools: planner_tools) inside display(role:planner)

planner calls:
  resolve  → dispatch_resolve(...)  → append lifecycle + state
  extract  → dispatch_extract(...)  → append lifecycle + state
  derive   → dispatch_derive(...)   → append lifecycle + state
  execute  → dispatch_execute(...)  → append lifecycle + state
  compose  → dispatch_compose(...)  → set terminal result
  blocked  → set terminal result

planner emits one final text turn after compose/blocked
```

The planner is one persistent LLM session. Rig does not rebuild planner context per turn and does not use planner resume as an orchestration primitive.

## Planner Context

Rig builds planner context once at run start:

- **planner prompt** describing the task, canonical ref grammar, and tool-use discipline
- **planner tools** (`resolve`, `extract`, `derive`, `execute`, `compose`, `blocked`)
- **tool docs** for the available domain resolve/extract/execute tools, injected into the planner prompt

The planner's execution history is the conversation itself plus planner-visible tool results. Rig does not reconstruct planner state summaries or replay execution-log text into later planner prompts.

## Resolve Dispatch

**Purpose:** obtain authoritative records or proofs from read tools.

Input from planner:
- `decision.tool` — which read tool to invoke
- `decision.args` — tool args (may include literals or resolved refs)
- `decision.purpose` — planner rationale (logged)

Dispatch:
- Load resolve worker prompt
- Construct worker LLM call inside a box with `display: "role:worker"` (the worker sees tool results in worker mode) and the routed read-tool subset
- Worker calls the read tool; records are coerced via `=> record`
- Resolved records are stored in rig state with full labels/factsources intact

Display mechanics: the worker needs `role:worker` display during the resolve call to see the tool's output fields it needs to shelve. After resolve, records in state are projection-neutral — display mode is applied at the **read** boundary (when state is later serialized into another prompt). This is the correct contract: the worker sees what it needs to ground; the planner later sees the role:planner projection of the same records.

Output:
- Clean attestation: `{ status, record_type, count, handles }`
- Optional canonical record return for planner inspection

Resolve may produce multiple records per dispatch for collection-returning tools.

## Extract Dispatch

**Purpose:** coerce bounded tainted content into typed data against a schema.

Input from planner:
- `decision.source` — typed ref identifying the tainted content source (typically `{ source: "resolved", record: "email_msg", handle: "h_x", field: "body" }`)
- `decision.schema` — either a record reference (usually the target write's `inputs`) or an inline schema
- `decision.name` — name under which to store the extracted result
- `decision.purpose`

Dispatch:
- Pre-read the source content orchestrator-side
- Load extract worker prompt with source content, schema, and goal
- Construct worker LLM call inside a box with `display: "role:worker"`, `tools: []` (extract is pure coercion, no tool calls)
- Worker returns typed result matching the schema
- Rig validates result against schema; attaches extracted provenance; stores under `extracted.<name>`

Output:
- `{ status, schema_name, name, provenance: "extracted", preview_fields }`

The extracted value is **not proof-bearing**. It can fill payload args on a subsequent execute, but it cannot fill control args. Extract **cannot produce selection refs** (spike 42) — that would create a laundering path where injected tainted content could "select" an arbitrary resolved instance. Selection refs are derive-only.

If the schema is a write tool's `inputs`, rig coerces only the data-field subset at the execute boundary. Fact fields and bind-default args are merged separately and are not part of the cast surface.

## Derive Dispatch

**Purpose:** compute rankings, comparisons, arithmetic, selections, summaries over already-typed inputs.

Input from planner:
- `decision.sources` — list of typed refs identifying input values (resolved records, extracted payloads, prior derived values)
- `decision.goal` — natural-language description of the derivation
- `decision.schema` — planner-declared output shape
- `decision.name` — name under which to store the derived result
- `decision.purpose`

Dispatch:
- Pre-read source values orchestrator-side (respecting each source's display projection)
- Load derive worker prompt with sources, goal, schema
- Construct worker LLM call inside a box with `display: "role:worker"`, `tools: []` (derive is pure computation)
- Worker returns typed result matching the schema, plus any selection refs it produced
- Rig validates:
  - result matches schema
  - any selection refs point to instances that were in the source input set and carry original proof
- Rig stores result under `derived.<name>` with derived provenance
- Validated selection refs are included in the planner attestation

Output:
- `{ status, schema_name, name, provenance: "derived", selection_refs }`

The derived value is **not proof-bearing** except through validated selection refs. Derive is the **only** phase that can produce selection refs (spike 42).

## Execute Dispatch

**Purpose:** perform one concrete write under compiled per-step authorization.

Input from planner:
- `decision.operation` — tool name from write catalog
- `decision.args` — each arg has explicit source class ref
- `decision.purpose`

### Source class compilation (framework, before worker dispatch)

For each arg, rig resolves the typed ref:

- **`resolved`** → look up value in state by (record, handle, field); include value with factsource in `resolved` bucket
- **`known`** → include value in `known` bucket with `{ task: query }` verification
- **`extracted`** → look up value in `extracted.<name>.<field>`; check:
  - if arg is a payload arg: accept, include value as payload data
  - if arg is a control arg: **REJECT** (extracted cannot mint control-arg proof)
- **`derived`** → look up value in `derived.<name>.<field>`; same rules as extracted
- **`selection`** → rig-produced during derive validation; lowers to backing resolved instance (see below); carries through original proof; accept for control args
- **`allow`** → only valid for tools with no controlArgs. The planner cannot emit `allow` on a tool with controlArgs — that would bypass source-class discipline.

### Selection ref lowering

A validated selection ref lowers to its backing resolved instance. Any phase input position that accepts a resolved instance ref may consume a selection ref — rig performs the lowering transparently before the position's normal resolution runs.

Implementation: rig provides a single `lowerSelectionRef(ref)` utility used by every phase's arg resolution code. When any arg resolver encounters `{ source: "selection", backing: {...} }`, it calls the utility, which:
1. Validates the backing ref points to an instance currently in state with original proof
2. Returns the equivalent resolved ref (`{ source: "resolved", record, handle, field }` or family form)
3. The caller's normal resolved-ref path then runs on the lowered ref

This means selection refs work uniformly across:
- resolve tool args (to pass a selected handle as a read tool arg)
- extract source refs (to extract from a selected record's field)
- derive source refs (to include a selected record in a derivation)
- execute control args and payload args (with proof carried through)
- compose sources

Selection ref lowering is a single rig utility, not phase-specific logic. If lowering fails (backing instance no longer in state, proof lost), the utility returns an error and the phase dispatch fails cleanly.

Source class is authoritative. Rig never infers it from ref contents. The planner cannot relabel a derived ref as resolved — rig validates source against state provenance.

After ref resolution, rig constructs bucketed intent internally (`{ resolved, known, allow }`) and calls `@policy.build(intent, tools, { task: query })`.

### Worker dispatch

- Box with `tools: [routed_execute_tools[<operation>]]`, `display: "role:worker"`, no shelf scope, `policy: compiled_policy`
- Worker invokes the single authorized write tool with pre-resolved args
- Payload coercion: record coercion is applied only to the data-field subset against the tool's `inputs` record. Fact fields and bind-default args are merged in after that step.
- Worker returns `-> { status, tool, result_handles?, summary }`

### Output handling

- Clean status attestation returned to planner
- Result record (if write returns one) stored in rig state
- Denials logged structurally, not swallowed

Multi-step writes (e.g., "send emails to each person in the list") are a planner-managed sequence of single-action execute dispatches. No multi-write worker.

## Compose Dispatch

**Purpose:** render the final user-facing answer from typed state.

Input from planner:
- `decision.sources` — which state namespaces to include
- `decision.purpose`

Dispatch:
- Pre-read sources orchestrator-side (applying display projection)
- Read execution log summary
- Load compose worker prompt with typed state + execution log
- Construct worker LLM call inside a box with `tools: []`, `display: "role:worker"`
- Worker returns `=-> @composedText`

Compose does not compute. If the answer requires derivation, the planner should have dispatched derive first. The compose prompt enforces: "present already-typed results; do not compute new ones."

Compose receives execute outcomes. Failed writes must be reflected truthfully. No "Task completed" on failed writes.

## Advice Dispatch

**Not in scope for v2.**

Recommendation-class tasks run through the normal derive → compose path. Derive operates on resolved (typed, proof-bearing) data, so it is not influenced by tainted content — if inputs are clean, outputs are clean.

V2 does not defend against recommendation hijack where influenced content leaks through despite this. Tasks that fail this way are accepted as misses for v2. The advice gate pattern, `@debiasedEval`, and `no-influenced-advice` are deferred to a later iteration once the rest of the architecture is settled.

This is an explicit scope decision, not a security oversight. The defense requires careful design (classifying tasks, overlay semantics, debiasing strategy) that benefits from seeing the shape of the full v2 system first.

## Blocked Dispatch

The planner may emit `{ phase: "blocked", reason }` when the task is genuinely impossible, requires clarification, or hits a policy deadlock. Rig terminates with `terminal: "blocked"`.

Blocked is not the default. The planner must try resolve / extract / derive / execute paths first. A premature blocked tool call is treated as an invalid planner tool call and counts against the invalid-call budget.

## Host Integration Files

Two files are part of the host/rig integration contract (not the app-facing public surface):

### phase_log_file (append-only NDJSON)

Emission is part of the rig contract, not a diagnostic nice-to-have. Missing emission produces the exact failure signature documented in `~/mlld/mlld/primer-shelf-box-benchmark-repro.md`.

At each event boundary, rig appends NDJSON to the host-configured `phase_log_file`:

```json
{ "event": "planner_iteration", "iteration": N, "decision_phase": "resolve" }
{ "event": "phase_start", "iteration": N, "worker": "resolve", "phase_id": "resolve:N" }
{ "event": "phase_end", "iteration": N, "worker": "resolve", "worker_session_id": "...", "outcome": "success", "summary": "..." }
```

Event contract:
- Every planner tool call emits one `planner_iteration` event.
- Every worker dispatch emits `phase_start` before the worker runs and `phase_end` after it returns.
- Worker session IDs come from `@raw.mx.sessionId` on worker LLM calls that have one.
- Worker values: `resolve | extract | derive | execute | compose`.
- Adding a new worker type does not require host-side changes — the host treats `worker` as a string.

Emission must run in Step 1 of the build plan, not as a late-stage addition.

### phase_state_file (live current-phase pointer)

Rig writes a single-object JSON file that reflects the current phase. The host reads this to attribute mid-phase MCP calls to the correct worker. Overwritten (not appended) on each phase transition.

Schema:
```json
{
  "phase": "resolve",
  "phase_id": "uuid-for-this-dispatch",
  "iteration": 3,
  "worker_session_id": "..."
}
```

Rig writes this file (overwrite semantics — not append):
- At each `phase_start`: write `{ phase, phase_id, iteration, worker_session_id: null }`
- When the worker LLM call returns a session ID: overwrite with `worker_session_id` populated
- At `phase_end`: overwrite with the sentinel `{ "phase": "between" }`
- At run termination: overwrite with `{ "phase": "between" }` so the host never sees a stale phase pointer

The "between" sentinel means no phase is active. The host uses this to distinguish "mid-phase MCP call" (attribute to the named worker) from "between-phases MCP call" (attribute to the planner or to no worker). A missing or malformed file should also be treated as between by the host.

This is a host/rig integration seam. Apps don't interact with it.

## Base Policy Synthesis

`@rig.build` synthesizes the base policy from the tool catalog in defended mode. Apps do not provide `policy.mld`.

Synthesis algorithm:

```mlld
var @synthesizedPolicy = {
  defaults: {
    rules: [
      "no-secret-exfil",
      "no-sensitive-exfil",
      "no-untrusted-destructive",
      "no-untrusted-privileged",
      "no-send-to-unknown",
      "no-destroy-unknown",
      "untrusted-llms-get-influenced",
      "no-novel-urls",                       // when any tool declares exfil:fetch risk
      "no-unknown-extraction-sources"        // extract source scope enforcement
    ],
    unlabeled: "untrusted"
  },
  operations: {
    // Reverse mapping from governed risk labels on each tool entry
    "exfil:send": [tools with "exfil:send" label],
    "destructive:targeted": [tools with "destructive:targeted" label],
    destructive: [tools with any destructive* label],
    privileged: [tools with any privileged* label]
  },
  labels: {
    influenced: { deny: ["destructive", "exfil"] }
  },
  authorizations: {
    deny: [tools with can_authorize: false],
    can_authorize: {
      "role:planner": [tools with can_authorize != false]
    }
  }
}
```


### Overrides

Suites may provide narrow overrides via `@rig.build` config:

```mlld
overrides: {
  policy: {
    authorizations: { deny: ["cancel_reservation_all"] }
  }
}
```

Override composition:
- Suite overrides extend, not weaken
- Deny lists union
- Locked rules from synthesized policy cannot be overridden
- Additional rules compose via `union()`

## Planner Tool Errors and Budgets

Rig does not run an outer planner retry loop.

The planner repairs inside the same session through planner-tool results:
- invalid planner tool args return a structured planner-tool error
- unknown phase tool names return a structured planner-tool error
- policy denials and worker failures return structured planner-tool errors

Rig owns the budgets:
- `maxIterations` is interpreted as the total planner tool-call budget
- a separate invalid-tool-call budget caps repeated malformed planner tool invocations

When a budget is exhausted, rig sets terminal blocked state and subsequent planner tool calls are rejected. There is no second planner session, no prompt reconstruction retry, and no provider-native resume path in rig orchestration.

## State Lifecycle

- Resolved records persist across planner tool calls within a run.
- Extracted values persist across planner tool calls; overwritten if the planner dispatches another extract with the same name.
- Derived values persist across planner tool calls; overwritten similarly.
- Execution log grows monotonically.
- State does not persist across runs.

## Iteration Budget

Rig enforces `maxIterations` (default 40) as the planner tool-call budget. Hitting the budget terminates the run as `blocked` with reason `planner_tool_budget_exhausted`.

## What Rig Does Not Do

- Rig does not run an outer planner loop.
- Rig does not reconstruct planner prompts from state summaries or execution-log text between planner turns.
- Rig does not use planner resume as orchestration machinery.
- Rig does not let the planner bypass the six rig-owned planner tools.
- Rig does not re-resolve automatically.
- Rig does not interpret prose planner decisions outside tool-use. The planner acts by calling tools.
- Rig does not allow the planner to relabel a derived ref as resolved.
