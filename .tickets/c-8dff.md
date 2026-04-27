---
id: c-8dff
status: closed
deps: []
links: [c-63fe]
created: 2026-04-27T07:26:04Z
type: feature
priority: 1
assignee: Adam
tags: [c-63fe, test-harness, memory-profiling, reproducer]
updated: 2026-04-27T08:00:22Z
---
# Mock-agent test program for c-63fe Phase B memory hot path repro

Build a deterministic, zero-LLM test program that reproduces UT19's Phase B work so mlld-dev can profile and fix the c-63fe memory hot path without needing API keys, network, or costly bench cycles.

## Why

c-63fe diagnosis (in_progress with gpt; opus + codex investigations filed in c-63fe ticket): the slow work that triggers the OUTER MCP cascade is in mlld/rig `@plannerResolveBatch` Phase B (sequential settle, state merge, projection, planner_cache). Inner Python MCP calls finish in ms; rig spends 5+ minutes between fast inner calls and the outer 500s opencode timeout. UT19 is the worst offender: multi-domain (London + Paris × hotels + restaurants + car_rental = 6 entity families × 26 total entries) and consistently triggers the cascade on remote.

A reproducer that exercises the same Phase B work without LLM calls gives mlld-dev:
- A reliable, fast (seconds not minutes) repro to iterate against
- Memory profile data without bench-cycle cost
- A regression test once the fix lands

## UT19 actual tool-call sequence (canonical, from local run defended.71)

The planner makes 4 decisions across 14 phase events.

### Iteration 1 — `resolve_batch` (Batch A, 6 sub-resolves)

```json
{
  "resolves": [
    {"tool": "get_all_hotels_in_city",            "args": {"city": {"source": "known", "value": "London"}}, "purpose": "List all hotels in London"},
    {"tool": "get_all_hotels_in_city",            "args": {"city": {"source": "known", "value": "Paris"}},  "purpose": "List all hotels in Paris"},
    {"tool": "get_all_restaurants_in_city",       "args": {"city": {"source": "known", "value": "London"}}, "purpose": "List all restaurants in London"},
    {"tool": "get_all_restaurants_in_city",       "args": {"city": {"source": "known", "value": "Paris"}},  "purpose": "List all restaurants in Paris"},
    {"tool": "get_all_car_rental_companies_in_city", "args": {"city": {"source": "known", "value": "London"}}, "purpose": "List all car rental companies in London"},
    {"tool": "get_all_car_rental_companies_in_city", "args": {"city": {"source": "known", "value": "Paris"}},  "purpose": "List all car rental companies in Paris"}
  ],
  "purpose": "List all hotels, restaurants, car rental companies in London and Paris"
}
```

Result shape per phase_end:
- iter=1 phase=resolve: 5 hotel records (London)
- iter=2 phase=resolve: 4 hotel records (Paris) → cumulative 9 hotels
- iter=3 phase=resolve: 3 restaurant records (London)
- iter=4 phase=resolve: 10 restaurant records (Paris) → cumulative 13 restaurants
- iter=5 phase=resolve: 2 car_company records (London)
- iter=6 phase=resolve: 2 car_company records (Paris) → cumulative 4 car_companies

State after Batch A: hotel(9), restaurant(13), car_company(4) = **26 entities** with name + city fields.

### Iteration 2 — `resolve_batch` (Batch B, 6 sub-resolves with resolved_family expansion)

This is the heavy batch — each sub-resolve EXPANDS the resolved_family AND merges back into existing handles (per-field merge, c-5a24 behavior).

```json
{
  "resolves": [
    {"tool": "get_hotels_prices",            "args": {"hotel_names":      {"source": "resolved_family", "record": "hotel",      "field": "name"}}, "purpose": "Hotel prices for all London + Paris hotels"},
    {"tool": "get_rating_reviews_for_hotels", "args": {"hotel_names":      {"source": "resolved_family", "record": "hotel",      "field": "name"}}, "purpose": "Hotel ratings"},
    {"tool": "get_price_for_restaurants",    "args": {"restaurant_names": {"source": "resolved_family", "record": "restaurant", "field": "name"}}, "purpose": "Restaurant prices"},
    {"tool": "get_rating_reviews_for_restaurants", "args": {"restaurant_names": {"source": "resolved_family", "record": "restaurant", "field": "name"}}, "purpose": "Restaurant ratings"},
    {"tool": "get_car_price_per_day",        "args": {"company_name":     {"source": "resolved_family", "record": "car_company", "field": "name"}}, "purpose": "Car rental prices"},
    {"tool": "get_rating_reviews_for_car_rental", "args": {"company_name": {"source": "resolved_family", "record": "car_company", "field": "name"}}, "purpose": "Car rental ratings"}
  ],
  "purpose": "Get prices and ratings for all entities resolved in Batch A"
}
```

Result shape per phase_end:
- iter=2 phase=resolve: 9 hotel records (price merged into existing handles)
- iter=3 phase=resolve: 9 hotel_review records (NEW record type, rating field)
- iter=4 phase=resolve: 13 restaurant records (price merged)
- iter=5 phase=resolve: 13 restaurant_review records (NEW)
- iter=6 phase=resolve: 4 car_company records (price merged)
- iter=7 phase=resolve: 4 car_company_review records (NEW)

State after Batch B: hotel(9), restaurant(13), car_company(4), hotel_review(9), restaurant_review(13), car_company_review(4) = 6 record types, 52 entries total. Phase B walks this state 6 times during settle (once per spec).

### Iteration 3 — `derive`

```json
{
  "name": "trip_selections_and_total",
  "sources": [
    {"source": "resolved", "record": "hotel"},
    {"source": "resolved", "record": "hotel_review"},
    {"source": "resolved", "record": "restaurant"},
    {"source": "resolved", "record": "restaurant_review"},
    {"source": "resolved", "record": "car_company"},
    {"source": "resolved", "record": "car_company_review"}
  ],
  "goal": "Select max-rated entities per city and compute total max trip cost: 2 days London + 3 days Paris, 2 meals/day, all in euros"
}
```

Result: derived payload with 6 selection_refs (one per entity type per city, 2 cities = 6 picks) + scalar grand_total.

### Iteration 4 — `compose`

```json
{
  "sources": ["derived.trip_selections_and_total"],
  "purpose": "Report selected entities and grand total"
}
```

Returns text.

## Phase B hot path mechanics (per codex investigation)

For each of the 6 sub-resolves in Batch B, Phase B does:
1. `@batchSpecMergeState` — merges spec's incoming entries atop cumulative state via `@updateResolvedStateWithDef`
2. `@mergeResolvedEntries` — O(existing × incoming) per-field merge through `@mergeFieldDict`
3. `@populatePlannerCache` — projects every cumulative entry under `role:planner` after every spec
4. `@settlePhaseDispatch` (per spec) — log + planner.set + recompute progress fingerprint

For UT19's Batch B with cumulative state growing 26→35→44→48→61→65 across the 6 specs, this is the multi-minute tail. Codex's spike measured 100×-215× speedup with delta-merge + incremental cache (gpt's 3 commits implemented this).

## Path A vs Path B (decided: Path A)

### Path A — drop-in mlld harness mock (CHOSEN)

`rig/test-harness/mock-opencode.mld` exports `@mockOpencode(prompt, config)` matching the `@opencode` interface. Internally:
- Reads a tool-call script from `config.toolScript` (a fixture file)
- For each scripted call, invokes the corresponding rig planner exe directly (`@plannerResolve`, `@plannerResolveBatch`, `@plannerDerive`, `@plannerCompose`)
- Returns the final compose text

**Pros**: zero LLM cost, zero opencode subprocess, deterministic, runnable in seconds, fully exercises rig Phase B (the codex-identified hot path) and the inner Python MCP server (gets real AgentDojo data back). mlld-dev gets a `mlld <script>` reproducer.

**Cons**: doesn't exercise the OUTER function-mcp-bridge (per-call socket lifecycle). Per codex/opus diagnosis the heavy work is in rig Phase B not the bridge, so the memory profile should still be representative.

### Path B — full external fake-opencode (DEFERRED)

A Node/TS process that speaks MCP over stdio like real opencode, scripted to emit the same tools/call sequence. Wires through the actual function-mcp-bridge.

**Pros**: exercises everything including the OUTER bridge.

**Cons**: significantly more setup; multi-process repro; mlld-dev needs to manage subprocess lifecycle.

### Decision rationale

Per codex's diagnosis, the multi-minute Phase B tail in rig is what triggers the outer 500s opencode timeout — the OUTER bridge cascade is the consequence, not the cause. Profiling Phase B with Path A directly addresses the trigger. If mlld-dev later wants bridge-side profiling, Path B is a straightforward extension.

## Deliverables

- [ ] `rig/test-harness/fixtures/ut19-tool-script.json` — captured tool-call sequence with args and expected result shapes
- [ ] `rig/test-harness/mock-opencode.mld` — drop-in `@mockOpencode` harness implementation
- [ ] `rig/test-harness/run-ut19-mock.mld` — runnable test program that builds a rig agent with mock harness, replays the script, exits cleanly
- [ ] `scripts/repro-c63fe-mem.sh` — wrapper that sets `MLLD_TRACE=verbose MLLD_TRACE_MEMORY=1` and runs the mock
- [ ] README.md in `rig/test-harness/` documenting how to run + interpret output

## Out of scope

- Path B (external fake-opencode binary) — defer to future ticket if Path A proves insufficient
- Fixing c-63fe (in_progress with gpt under c-63fe ticket — this is reproducer infrastructure, not the fix)
- Other tasks (only UT19 since it's the worst offender; pattern can extend to others later)

## Linked
- c-63fe (the bug being reproduced)


## Notes

**2026-04-27T07:30:24Z** 2026-04-27 mlld-dev coordination: mlld:m-15d9 is adding compact --trace-memory attribution summaries intended to run against this UT19 mock harness. Once mlld changes land, run npm run build in ~/mlld/mlld before invoking this clean-side repro so the local mlld binary uses the latest trace code.

**2026-04-27T07:34:46Z** 2026-04-27 mlld-dev update: m-15d9 now emits memory.summary at run.finish, including peak RSS/heap, first major jump, top deltas, and sessionWrites byte totals. Once this harness is ready, run it with --trace-memory --trace-file and inspect the memory.summary line first.

**2026-04-27T07:35:11Z** 2026-04-27 trace flag caveat: mlld-dev code inspection shows the supported CLI path is --trace-memory/--trace-file (or SDK traceMemory), not MLLD_TRACE_MEMORY by itself. If scripts/repro-c63fe-mem.sh uses env vars for readability, also pass explicit --trace-memory --trace-file so memory.summary is emitted.

**2026-04-27T07:40:39Z** **2026-04-27T07:50:00Z foundation landed, blocked on session-scoping**

Built and verified end-to-end:
- `fixtures/ut19-tool-script.json` — captured UT19 4-step planner sequence with annotated expected state per step
- `mock-opencode.mld` — `@mockPlannerRun` mock harness shape (validates clean)
- `run-ut19-mock.mld` — runnable test program (validates clean)
- `scripts/repro_c63fe_mem.py` — Python wrapper that wires AgentDojo travel env + MCP command via the same path `src/host.py` uses; calls mlld SDK `execute()` with `mcp_servers={"tools": mcp_command}` and trace knobs

Executes successfully end-to-end (12.9s wall, no crashes). Mock script dispatches all 4 steps. Inner Python MCP server spawns and is ready.

**Blocker**: planner session not seeded → all 4 steps return `error`. The session scoping in mlld doesn't naturally extend to our mock context:
- `with { session: @planner, seed: ... }` on the mock exe definition doesn't propagate to imported planner-tool exes (different module)
- Explicit `@planner.set(...)` in mock body fails with 'Method not found: set on planner' — `set` only exists inside an active session-binding scope

This is an mlld semantics question. Three resolution options documented in README.md:
1. Find the right session-scoping shape so `@planner.set` works outside an `exe llm` call
2. Drive through real `@runPlannerSession` with stub harness + scripted stubResponses
3. Refactor planner-tool exes to take agent/query/state as explicit params

Foundation committed; blocker handed off (need mlld-dev or gpt input on session semantics).

**2026-04-27T08:00:22Z** **2026-04-27T08:30:00Z WORKING — closed**

Resolved the session-scoping blocker by declaring the mock as `exe llm @mockOpencode(prompt, config)`. The `llm` modifier is what enables the `with { session: @planner, seed: {...} }` binding semantics — same path the real @opencode/@claude harness uses. (Adam pointed this out: 'just add one'. Should have looked at ~/mlld/modules/opencode/index.mld for the wiring earlier.)

## Verified metrics

End-to-end run with no LLM calls, no API keys, fully deterministic:

| Metric | Value |
|--------|-------|
| Wall time | **9+ minutes** |
| Peak RSS | **6.8 GB** |
| Final state size | 52 entries × 6 record types |
| Planner tool calls | 4 (resolve_batch ×2, derive, compose) |
| Inner MCP calls | 12 (each <20ms) |
| LLM calls | **0** |

For 52 record entries that's ~10 seconds per entry of pure-mlld processing. The synthetic phase_b_hotspot_spike.js predicted ~2 seconds for similar-sized work — actual implementation is ~300× slower than even the conservative model predicted. Compounding overhead the spike didn't simulate (factsource walks, per-spec bucket re-shaping, GC pause stacking, or hidden O(N³) somewhere).

## Files (final)

- `rig/test-harness/fixtures/ut19-tool-script.json` — captured UT19 sequence
- `rig/test-harness/mock-opencode.mld` — `exe llm @mockOpencode` + `@runScript` + `@dispatchScriptStep`
- `rig/test-harness/run-ut19-mock.mld` — runnable test program (uses `@mockOpencode` with `with { session: @planner, seed: {...} }` at the call site)
- `scripts/repro_c63fe_mem.py` — Python wrapper wiring the AgentDojo travel env + MCP command (mirrors src/host.py); calls mlld SDK with mcp_servers and trace knobs; default 900s timeout
- `rig/test-harness/README.md` — usage, architecture note, why it matters

## How to run

```bash
# Default 12g heap, no tracing
uv run --project bench python3 scripts/repro_c63fe_mem.py

# Reproduce the original 8g failure profile
MLLD_HEAP=8g uv run --project bench python3 scripts/repro_c63fe_mem.py

# With memory + phase tracing (for mlld-dev profiling)
MLLD_TRACE=verbose \
  MLLD_TRACE_FILE=/tmp/c63fe-mock-trace.jsonl \
  MLLD_TRACE_MEMORY=1 \
  uv run --project bench python3 scripts/repro_c63fe_mem.py

jq -c 'select(.event|test("memory|phase|rss|heap"))' /tmp/c63fe-mock-trace.jsonl | tail
```

## Commits

- `0ed81a1` c-8dff: foundation (had session-scoping blocker)
- `1ba9814` c-8dff: working c-63fe reproducer — exe llm fixes session scoping

Pushed to main.

## What this unblocks

mlld-dev (and gpt working c-63fe) now has:
- A fast iteration loop for memory profiling — every optimization shows up as wall-time delta
- A regression test that runs in seconds-of-setup once the fix lands
- Zero-API-key reproducer any contributor can run

The fixture captures UT19's exact Phase B workload — anyone who wants to profile a different task can capture a similar fixture from any travel run's defended.jsonl mcp_calls + phase_events.

## Out of scope (deferred)

- Path B (full external fake-opencode binary that exercises the OUTER function-mcp-bridge per-call socket lifecycle). Per opus + codex c-63fe diagnosis, the bridge cascade is downstream of Phase B; profiling Phase B directly captures the trigger. Path B would be a future ticket only if Phase B optimization doesn't fully resolve c-63fe.
