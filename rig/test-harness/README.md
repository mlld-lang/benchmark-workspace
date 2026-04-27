# c-63fe Phase B Memory Reproducer

c-8dff: deterministic, zero-LLM reproducer for the c-63fe Phase B memory hot path.

## What's here

- `fixtures/ut19-tool-script.json` — captured planner tool-call sequence from a real UT19 run (defended.71). 4 decisions: 2× `resolve_batch` (6 sub-resolves each) + 1× `derive` + 1× `compose`. Annotated with expected per-step state shape so reviewers can verify the script matches a real run.
- `mock-opencode.mld` — mock harness module exporting `@mockPlannerRun(agent, query, script)`. Drives the planner-tool dispatch directly without an LLM. Inner Python MCP server (`src/mcp_server.py`) still spawns and returns real AgentDojo data.
- `run-ut19-mock.mld` — runnable test program that builds a rig agent and calls `@mockPlannerRun` with the UT19 fixture.
- `../../scripts/repro_c63fe_mem.py` — Python wrapper that wires the AgentDojo travel env + MCP command the same way `src/host.py` does, then invokes the mlld SDK to run the test program.

## Status: foundation in place, session-scoping blocker for completion

The fixture, mock dispatch logic, and Python wrapper all work end-to-end (12.9s wall, no crashes). **But the planner-tool dispatch returns `error` because the planner session isn't seeded with the agent/query context the planner exes expect.**

### The blocker

`rig/session.mld` defines:

```mlld
var session @planner = {
  agent: object?,
  query: string?,
  state: object,
  runtime: @plannerRuntime
}
```

`@planner.set(...)` is only valid inside a `with { session: @planner }` block. The real planner uses this on the LLM call itself:

```mlld
exe @plannerLlmCallStub(prompt, config, agent, query) =
  @llmCall("stub", @prompt, @config) with {
    display: "role:planner",
    session: @planner,
    seed: { agent: @agent, query: @query, state: @emptyState(), runtime: @emptyPlannerRuntime() }
  }
```

The `with` scopes the session to the duration of `@llmCall`. Inside that scope, the OUTER MCP bridge invokes planner-tool exes (from `planner.mld`) via callbacks, and those exes can read `@planner.agent`, `@planner.query`, etc.

For our mock, we want the session scope to span the entire script dispatch (multiple steps, no LLM call). Two attempts both failed:

1. **`with` on the mock function** — `exe @mockPlannerRun(...) = [...] with { session: @planner, seed: ... }`. The session scope didn't reach the imported planner-tool exes (different module).
2. **Explicit `@planner.set(...)` in the mock body** — failed with "Method not found: set on planner". The `set` method only exists inside an active session-binding scope.

This is an mlld semantics question worth a human/mlld-dev decision: does the session reference shared between modules need explicit threading? Is there a way to "enter" a session from outside an `exe llm`?

### Options for whoever picks this up

**Option 1**: figure out the right session-scoping shape so `@planner.set` works in our mock context. Probably needs an mlld primitive or a documented pattern.

**Option 2**: drive the mock through the real `@runPlannerSession` (in `rig/workers/planner.mld`) using the existing stub harness with `stubResponses` configured as a sequence of tool_call decisions. The planner's tool-loop would interpret them and trigger Phase B naturally. Requires understanding the stub harness's response format.

**Option 3**: skip the `@planner` session entirely. Refactor the planner-tool exes to take agent/query/state as explicit parameters instead of reading from session. Bigger change but removes the mock blocker AND would simplify testing.

## How to run (when fixed)

```bash
# Default: 12g heap, no tracing
uv run --project bench python3 scripts/repro_c63fe_mem.py

# With memory tracing
MLLD_TRACE=verbose \
  MLLD_TRACE_FILE=/tmp/c63fe-mock-trace.jsonl \
  MLLD_TRACE_MEMORY=1 \
  uv run --project bench python3 scripts/repro_c63fe_mem.py

# Inspect peaks
jq -c 'select(.event|test("memory|phase|rss|heap"))' /tmp/c63fe-mock-trace.jsonl | tail
```

## Why this is worth the effort

Per c-63fe diagnosis (in_progress with gpt; opus + codex investigations filed in `.tickets/c-63fe.md`):

- Inner Python MCP calls finish in 1-11ms
- mlld/rig spends 5+ minutes between fast inner calls and the outer 500s opencode `mcpTimeoutMs`
- That gap is in `@plannerResolveBatch` Phase B (sequential settle, state merge, projection, planner_cache)
- Codex's spike measured 100×-215× speedup with delta-merge + incremental cache (the optimizations now in HEAD)

A reproducer that exercises Phase B without LLM calls gives mlld-dev a fast iteration loop for memory profiling and a regression test once the fix lands.

## Linked

- c-8dff (this work)
- c-63fe (the bug being reproduced)
