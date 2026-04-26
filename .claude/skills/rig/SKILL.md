---
name: rig
description: Start a new rig/bench working session. Loads security model, architecture, debug guide, experiment log, and handoff context. Use at the start of every session.
user-invocable: true
---

# Start a rig/bench working session

Use this skill at the start of every session working on the rig framework or AgentDojo benchmarks. It loads the context you need to work effectively without crossing separation-of-concerns boundaries or repeating mistakes from prior sessions.

## What to do

You MUST read all of the following files before doing any work. Do not skim the filenames and assume you know what's in them — each one contains specific vocabulary, constraints, and lessons that will affect every decision you make in this session. Read them now, not "when needed."

### Step 1: Learn mlld syntax

Run this command and read the output:

```bash
mlld qs
```

This gives you the basics of mlld syntax (variables, exes, records, templates, imports). You need this to read and edit any `.mld` or `.att` file in the repo.

### Step 2: Read the security model

Read: `labels-policies-guards.md`

This is the security model narrative. It explains labels, policies, guards, records, facts, handles, display projections, and the planner-worker authorization pattern. The entire rig architecture is built on these primitives. If you don't understand how `resolved` vs `known` vs `extracted` source classes work, or what display projection does, you will make wrong decisions about where to put things.

### Step 3: Read the architecture docs

Read both of these:

- `rig/ARCHITECTURE.md` — why the framework is shaped this way (phase model, clean planner invariant, derive vs extract, separation of concerns)
- `bench/ARCHITECTURE.md` — how the benchmark suites consume rig (directory layout, agent entrypoints, what stays vs what goes)

These two documents define the boundary between rig (generic framework) and bench (suite-specific). Every change you make must respect this boundary. The most common mistake is putting suite-specific knowledge in rig prompts or framework-shaped workarounds in bench code.

### Step 4: Read the debugging guide

Read: `DEBUG.md`

This is the investigation methodology. Key sections:
- "Spike First. Sweep Last." — the single most expensive mistake is using LLM sweeps to answer questions a $0 spike could answer
- "Serialization is a one-way trip" — `| @pretty` and JSON parse strip all metadata
- "Never use `show` in bench-adjacent code" — it corrupts the host's stdout parsing, use `log` instead
- "Never rename record fields to match MCP parameter names" — the intent compiler handles the mapping
- The failure classification heuristics and debugging order

### Step 5: Read the experiment log

Read: `SCIENCE.md`

This has the current task tables, failure patterns, transcript-grounded analysis, and theories. It tells you what's passing, what's failing, and why. Don't start investigating a failure without checking whether it's already been analyzed here.

### Step 6: Check open tickets

```bash
tk ready
```

This shows actionable tickets with dependencies resolved. These are the starting points for work.

## During the session

Reference these documents when making decisions:
- **"Should this rule go in the rig prompt or a suite addendum?"** → Check the prompt placement rules in `CLAUDE.md` and the separation of concerns in `rig/ARCHITECTURE.md`
- **"Is this a runtime bug or a rig bug?"** → Follow the debugging order in `DEBUG.md`
- **"Has this failure been investigated before?"** → Check `SCIENCE.md` task tables
- **"How does this security primitive work?"** → Check `labels-policies-guards.md`

## Validation gates

Always run these before and after changes:

```bash
mlld clean/rig/tests/index.mld --no-checkpoint    # structural gate (100 assertions)
mlld rig/tests/workers/run.mld --no-checkpoint     # worker LLM tests (17 tests, ~14s on Cerebras)
```

## Running benchmarks

Default hybrid config: GLM 5.1 planner + Cerebras gpt-oss-120b workers. OOS/non-gating tasks are auto-skipped.

### Full sweeps → Namespace runner (preferred)

Local CPU caps at ~10 parallel tasks; the Namespace test runner (Team plan, 64 vCPU concurrent cap) fans all 4 suites in parallel and finishes the bench surface in ~10-15 min. Push to main, then:

```bash
scripts/bench.sh                          # all 4 suites in parallel
scripts/bench.sh workspace                # just one suite
scripts/bench.sh banking slack            # subset

gh run list --workflow=bench-run.yml --limit 8
uv run --project bench python3 src/fetch_run.py <run-id>          # → runs/<run-id>/
uv run --project bench python3 src/opencode_debug.py --home runs/<run-id>/opencode sessions
```

Per-suite shape and parallelism are baked into `scripts/bench.sh` (workspace 32x64, travel 16x32 + `-p 5` in fan-out / 32x64 + `-p 20` solo, banking/slack 8x16). Travel always gets `MLLD_HEAP=8g` automatically — without that the mlld Node process pushes ~5 GB heap and OOMs internally before the container does, surfacing as MCP "Not connected" cascades (c-63fe).

The image bakes mlld@2.1.0 + clean@main + agentdojo@mlld-rig. bench-run.yml has a freshness gate: if `mlld-lang/mlld:2.1.0` HEAD has moved since the last image build, the workflow joins the in-flight rebuild (or dispatches one), waits, and re-pulls. So after pushing both clean and mlld, just run `scripts/bench.sh`.

### Travel run-strategy choice

- **Travel solo →** `scripts/bench.sh travel` (Namespace 32x64, `-p 20`, `MLLD_HEAP=8g` set automatically). Recommended.
- **Full sweep with travel →** split runs: travel locally (bigger heap, no shared 64 vCPU cap), others remote.

```bash
# Terminal 1 — remote: the three other suites
scripts/bench.sh workspace banking slack

# Terminal 2 — local: travel at full parallelism with extra heap
MLLD_HEAP=12g uv run --project bench python3 src/run.py -s travel -d defended -p 20
```

A 48 GB Mac handles `-p 20 / MLLD_HEAP=12g` cleanly. Smaller machines: `-p 10 / MLLD_HEAP=8g`.

### Local single-task debugging

```bash
# Single task with trace (default hybrid models)
MLLD_TRACE=effects MLLD_TRACE_FILE=tmp/trace.jsonl \
  uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_11

# Override models
uv run --project bench python3 src/run.py --model cerebras/gpt-oss-120b
uv run --project bench python3 src/run.py --planner togetherai/zai-org/GLM-5.1 --worker cerebras/gpt-oss-120b

# Claude harness (Sonnet 4 for both)
uv run --project bench python3 src/run.py --harness claude -s workspace -d defended
```

Never use `--debug` — it triggers OOM. Use `MLLD_TRACE=effects MLLD_TRACE_FILE=tmp/trace.jsonl` for tracing.

See `CLAUDE.md` "Running benchmarks" for the full operational guide and `DEBUG.md` "Troubleshooting parallel runs" for OOM history, c-63fe details, and freshness-gate failure modes. Model comparison table is in `CLAUDE.md` (12 models tested).
