# c-63fe Phase B Memory Reproducer

c-8dff: deterministic, zero-LLM reproducer for the c-63fe Phase B memory hot path.

## Status: working — exercises Phase B with no LLM calls

Verified end-to-end: **6.8GB peak RSS, 9+ minutes wall, zero LLM calls, fully deterministic**. Drives the same Phase B settle/merge/cache/projection chain that triggers the c-63fe MCP cascade in real travel runs.

## What's here

- `fixtures/ut19-tool-script.json` — captured planner tool-call sequence from a real UT19 run (defended.71). 4 decisions: 2× `resolve_batch` (6 sub-resolves each) + 1× `derive` + 1× `compose`. Annotated with expected per-step state shape so reviewers can verify the script matches a real run.
- `mock-opencode.mld` — mock harness module. `exe llm @mockOpencode(prompt, config)` mirrors `@opencode`'s shape so the planner session binding works the same way the real harness does. `config.toolScript` carries the captured fixture.
- `run-ut19-mock.mld` — runnable test program that builds a rig agent and invokes `@mockOpencode` with `with { session: @planner, seed: {...} }` to seed the session for the planner-tool dispatch.
- `../../scripts/repro_c63fe_mem.py` — Python wrapper that wires the AgentDojo travel env + MCP command the same way `src/host.py` does, then invokes the mlld SDK to run the test program. Default 900s timeout.

## How to run

```bash
# Default: 12g heap, no tracing, 900s timeout
uv run --project bench python3 scripts/repro_c63fe_mem.py

# Smaller heap (the original failing config)
MLLD_HEAP=8g uv run --project bench python3 scripts/repro_c63fe_mem.py

# With memory tracing
MLLD_TRACE=verbose \
  MLLD_TRACE_FILE=/tmp/c63fe-mock-trace.jsonl \
  MLLD_TRACE_MEMORY=1 \
  uv run --project bench python3 scripts/repro_c63fe_mem.py

# Inspect trace peaks
jq -c 'select(.event|test("memory|phase|rss|heap"))' /tmp/c63fe-mock-trace.jsonl | tail
```

## Why this is worth the effort

Per c-63fe diagnosis (in_progress with gpt; opus + codex investigations filed in `.tickets/c-63fe.md`):

- Inner Python MCP calls finish in 1-11ms
- mlld/rig spends 5+ minutes between fast inner calls and the outer 500s opencode `mcpTimeoutMs`
- That gap is in `@resolveBatchWorker` Phase B (sequential settle, state merge, projection, planner_cache)
- Codex's spike measured 100×-215× speedup with delta-merge + incremental cache (the optimizations now in HEAD)

This reproducer replays UT19's exact Phase B work without LLM cost. mlld-dev gets:
- A fast iteration loop for memory profiling
- A regression test once the fix lands
- Reproducibility for any contributor (no API keys required)

## Architecture note

The mock doesn't exercise the OUTER `function-mcp-bridge` per-call socket lifecycle (path A in c-8dff design). The bridge cascade is downstream of Phase B's multi-minute tail, so profiling Phase B directly captures the trigger. If bridge-side profiling is later needed, the same fixture can drive a real opencode subprocess (path B).

## Why this is worth the effort

Per c-63fe diagnosis (in_progress with gpt; opus + codex investigations filed in `.tickets/c-63fe.md`):

- Inner Python MCP calls finish in 1-11ms
- mlld/rig spends 5+ minutes between fast inner calls and the outer 500s opencode `mcpTimeoutMs`
- That gap is in `@resolveBatchWorker` Phase B (sequential settle, state merge, projection, planner_cache)
- Codex's spike measured 100×-215× speedup with delta-merge + incremental cache (the optimizations now in HEAD)

A reproducer that exercises Phase B without LLM calls gives mlld-dev a fast iteration loop for memory profiling and a regression test once the fix lands.

## Linked

- c-8dff (this work)
- c-63fe (the bug being reproduced)
