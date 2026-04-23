---
id: c-3edc
status: open
deps: []
links: [c-d862]
created: 2026-04-21T22:00:57Z
type: epic
priority: 2
assignee: Adam
tags: [logging, observability, refactor]
updated: 2026-04-23T03:16:44Z
---
# Rig logging refactor: --trace + var session + curated hooks

# Rig Logging Plan

Two-channel observability for rig and the bench host:

- **Runtime trace** (`--trace`) — firehose of every runtime touchpoint. The mlld runtime owns this. Rig writes zero code for it.
- **Curated app events** (hooks + `append`) — a small set of domain-shaped events the bench host actually consumes. Rig owns six hooks; that's it.

The current rig logging stack (`lifecycle.mld` + `runtime.mld @appendLlmCall` + per-wrapper boilerplate in `planner.mld`) collapses substantially. Most of it was solving a problem the runtime now solves itself.

## What `--trace` covers (and why we lean on it)

The mlld runtime emits structured events for every observable touchpoint:

| Event | Carries |
|---|---|
| `llm.call` | `sessionId`, `provider`, `model`, `toolCount`, `resume`, `ok`, `error?`, `durationMs` |
| `session.seed` / `session.write` / `session.final` | `frameId`, `sessionName`, `path`, `previous`, `value` (redacted) |
| `guard.evaluate` / `.allow` / `.deny` / `.retry` / `.resume` | `phase`, `guard`, `operation`, `attempt` |
| `handle.issued` / `.resolved` / `.released` | `handle`, `valuePreview`, `sessionId` |
| `policy.build` / `.validate` / `.compile_drop` | `mode`, `valid`, dropped/repaired counts |
| `shelf.write` / `.read` / `.clear` / `.stale_read` | `slot`, `action`, `value` |
| `display.project` | `record`, `field`, `mode`, handle counts |
| `record.coerce` / `.schema_fail` | record, field, expected vs actual |

Every event also carries `RuntimeTraceScope` with `exe`, `operation`, `box`, `frameId`, `parentFrameId` — the last two enabling parent→child reconstruction of nested LLM calls. (See `core/types/trace.ts:86-94`.)

Filter levels (`core/types/trace.ts`):

- `off` — nothing
- `effects` — security/state-relevant events (this is the bench default)
- `verbose` — all events including reads, full content (no redaction); opt-in for debugging
- `handle` — handle-category events only

Sensitive content (anything carrying `secret`, `pii`, `untrusted`, `influenced`, etc.) is redacted at `effects` and shown only at `verbose`. `defaults.unlabeled: "untrusted"` makes unlabeled values redact automatically.

## Using `--trace` via the SDK

Both TS and Python SDKs accept the same options.

### Python (the bench host)

```python
result = client.execute(
    script,
    trace="effects",
    trace_file="bench-run.jsonl",   # optional file sink (NDJSON)
    trace_stderr=False,
)

# Post-run array of all events
for event in result.trace_events:
    if event.name == "llm.call":
        ...
```

`result.trace_events` is `list[TraceEvent]` (sdk/python/mlld.py:90, 1475). Each event has `name`, `category`, `level`, `data`, `scope`, `timestamp`. The same events stream live to `trace_file` as JSONL while the script runs.

### TypeScript (any in-process consumer)

```ts
const result = await client.execute(script, {
  trace: "effects",
  traceFile: "bench-run.jsonl",
  traceStderr: false,
});

result.traceEvents.forEach((evt) => {
  if (evt.name === "llm.call") { /* ... */ }
});
```

(sdk/types.ts:61-63, 129)

### Streaming (live observability during long runs)

```ts
for await (const evt of client.executeStream(script, { trace: "effects" })) {
  if (evt.type === "trace_event") {
    handleTrace(evt.traceEvent);
  }
}
```

(sdk/stream-execution.ts:121)

This matters for long bench runs where you want to see denials, slow LLM calls, or stuck phases in real time rather than after the run completes.

### Bench host wiring

In `clean/src/host.py`, the per-task call to mlld becomes:

```python
trace_path = run_dir / f"{task_id}.trace.jsonl"
result = client.execute(
    agent_script,
    trace="effects",
    trace_file=str(trace_path),
)
```

That's the entire LLM-call-timing setup. No rig-side code, no hooks, no `@appendLlmCall`. The trace file is the timing record.

## What `--trace` does NOT cover (and where hooks earn their keep)

Four gaps:

1. **Application-shaped events.** Trace emits `llm.call` keyed by exe name. The bench analyzer wants `{ phase: "resolve", iteration: 4, outcome: "ok", summary: {...}, ms: 8300 }`. That's domain semantics built from runtime observations.

2. **Curated streams.** Trace at `effects` is hundreds of events per task. The analyzer wants ~5-10 — one per phase boundary plus terminal. That's a projection.

3. **Out-of-band files at known paths.** `phase_state_file` for MCP-call attribution by the host: the host needs ONE small file at a known path saying "current phase = extract." Tailing the trace JSONL to derive it is roundabout.

4. **Composite events the runtime can't synthesize.** "Phase complete: 4 tools used, terminal=send_email, 8.3s." That's an aggregation across runtime events; the wrapper already has the structured return; one hook composes it.

These are the hook+append layer. Six hooks total — one per planner tool — each ~3 lines.

## Layer 2: `var session` migration (subsumes `rig/session.mld`)

The session-state primitive (spec-session-scoped-state.md) is a separate-but-aligned cleanup. Today rig hand-rolls a global shelf in `clean/rig/session.mld` (111 lines) plus per-wrapper init/reset/getter/setter calls. After migration:

```mlld
record @plannerRuntime = {
  data: [tool_calls: number, invalid_calls: number, terminal: string?, last_decision: string?]
}

var session @planner = {
  agent: object,
  query: string,
  state: object,
  runtime: @plannerRuntime
}
```

Wrapper exes attach with `@claude(@p, @cfg) with { session: @planner, seed: { agent: @a, query: @q } }`. Tool callbacks read/write via `@planner.runtime.tool_calls`, `@planner.increment("runtime.tool_calls", 1)`, etc.

Per-wrapper budget/counter/terminal-latch boilerplate collapses into guard middleware:

```mlld
guard @budget before tool:w = when [
  @planner.runtime.tool_calls >= 20 => deny "budget exhausted"
  * => allow
]

guard @count after tool:w = when [
  * => [
    @planner.increment("runtime.tool_calls", 1)
    @planner.write("runtime.last_decision", @mx.op.name)
    => allow
  ]
]
```

Final session state is observable post-call as `@result.mx.sessions.planner` and in `result.sessions[]` (SDK).

This deletes ~300+ lines across `session.mld`, `workers/planner.mld`, `workers/execute.mld`, and kills the m-5683 (state aliasing) + UT14 (null-callback) bug families structurally.

## Layer 3: Hooks + `append` for curated app events

`append` is the native NDJSON primitive (`docs/src/atoms/output/03-append.md`):

```mlld
append @event to "events.jsonl"   >> .jsonl auto-serializes JSON per line
```

No `js { JSON.stringify(...) }` wrapper, no `sh { printf >> "$file" }`. One directive.

Hooks fire on operation match (`docs/src/atoms/effects/18-hooks.md`):

```mlld
hook @phaseEnd after op:named:plannerResolve = [
  append {
    event: "phase_end",
    phase: "resolve",
    iteration: @planner.runtime.tool_calls,
    outcome: @output.outcome,
    summary: @output.summary
  } to "@agent.phaseLogFile"
  append { phase: "between" } to "@agent.phaseStateFile"
]
```

Six of these — one per planner tool (`plannerResolve`, `plannerExtract`, `plannerDerive`, `plannerExecute`, `plannerCompose`, `plannerBlocked`) — replace the manual emission scattered across `workers/planner.mld:194-232`.

Wrapper exes return structured `{ outcome, summary, sessionId }` instead of calling lifecycle exes by hand. The hook reads `@output` and writes the line.

### Phase state file for MCP attribution

Two `append` calls per phase: `before` writes the active phase, `after` resets to `between`.

```mlld
hook @phaseStart before op:named:plannerResolve = [
  append { phase: "resolve" } to "@agent.phaseStateFile"
]
```

The host opens `phase_state_file` at MCP call time and tags every MCP call with the current phase. No race against tailing the trace stream.

## What gets deleted from rig

After all three layers land:

| File | Today | After |
|---|---|---|
| `clean/rig/lifecycle.mld` | ~110 lines: JSON exe, sh-append exes, event constructors, reset helpers | ~30 lines: event-shape constructors only |
| `clean/rig/session.mld` | 111 lines: shelf + 4 slot records + 6 getter/setter exes + init/reset | ~10 lines: `var session` declaration + slot record |
| `clean/rig/workers/planner.mld` lines 194-232 | per-wrapper manual emission of plannerIteration/phaseStart/phaseEnd/between | hooks own it; wrappers shrink to outcome/summary computation |
| `clean/rig/runtime.mld:147` | `@appendLlmCall(...)` after every LLM call | gone — `--trace` emits `llm.call` automatically |
| `clean/rig/workers/*.mld` | per-wrapper budget/counter/terminal/log boilerplate | guard middleware idioms over `@planner` session state |

## The bench analyzer

A small post-run script (mlld or Python, ~50 LOC) reads the trace JSONL and produces a per-session timing rollup using `frameId` + `parentFrameId`:

```
for each llm.call event in run.jsonl:
  frame_id, parent, session_id, provider, model = event.scope, event.data
  duration_ms = event.data.durationMs
  store {frame_id, parent, session_id, duration_ms, ...}

for each frame:
  self_ms = wall_ms - sum(child wall_ms for child in direct children)

emit table sorted by self_ms desc:
  frame_id  parent  session_id  provider  model  wall  self  tool_count
```

Bottleneck pops out — is the planner slow thinking, or slow because each extract worker takes 30s?

This is the entire timing-analysis story. No bespoke instrumentation in rig.

## Implementation order

1. **Wire `trace` in the bench host.** One change to `clean/src/host.py`: pass `trace="effects", trace_file=<path>` to `client.execute(...)`. Verify `llm.call` events appear in the JSONL with `durationMs`, `frameId`, `parentFrameId`.

2. **Write the timing analyzer.** ~50 lines reading the trace JSONL. Land it next to the bench results aggregator. Validates the parent-frame chain works end-to-end before any rig refactor.

3. **Migrate to `var session @planner`.** Per spec-session-scoped-state.md §16. Delete `session.mld` getters/setters, wrapper init/reset calls, and the global shelf. Convert per-wrapper counters/budgets/terminal latches to guard middleware. This is the biggest deletion (kills bug classes too).

4. **Replace lifecycle emission with hooks.** Six hooks (one per planner tool), each ~3 lines using `append`. Delete `runtime.mld @appendLlmCall` (replaced by trace). Delete `lifecycle.mld` IO exes (replaced by `append`). Keep event-shape constructors.

5. **Drop `phaseLogFile` if redundant.** If the analyzer reads only the trace file, the curated `phase_log_file` may be redundant. Decide after the analyzer ships. `phase_state_file` stays — host needs the single-line current-phase file for MCP attribution.

## Where this lands

- Rig framework loses ~400+ lines of bookkeeping plus a known bug-class source (state aliasing, null callbacks).
- Bench host gains real LLM-call timing with parent/child nesting via one parameter change.
- App-level event emission becomes declarative (six hooks) instead of imperative (manual call sites scattered across wrappers).
- The runtime owns runtime observability; rig owns domain observability; the boundary is clean.

## References

- Trace subsystem: `~/mlld/mlld/core/types/trace.ts`, `~/mlld/mlld/spec-runtime-effect-tracing.md`
- Trace via SDK: `~/mlld/mlld/sdk/types.ts:61-63`, `~/mlld/mlld/sdk/python/mlld.py:633`
- Streaming trace: `~/mlld/mlld/sdk/stream-execution.ts:121`
- Session primitive: `~/mlld/mlld/spec-session-scoped-state.md`
- Hooks: `~/mlld/mlld/docs/src/atoms/effects/18-hooks.md`
- Append: `~/mlld/mlld/docs/src/atoms/output/03-append.md`
- Current rig logging: `~/mlld/clean/rig/lifecycle.mld`, `~/mlld/clean/rig/runtime.mld:147`, `~/mlld/clean/rig/workers/planner.mld:194-232`

