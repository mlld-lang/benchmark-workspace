# clean/ project

Rig v2 framework + AgentDojo benchmark implementation for mlld.

## First Actions

```bash
mlld clean/rig/tests/index.mld --no-checkpoint   # invariant gate (must be 92/0+)
tk ready                                          # active work items
```

## Structure

```
clean/
  rig/                    Framework (the reusable agent framework)
    ARCHITECTURE.md         Why it's structured this way
    SECURITY.md             10 numbered security invariants (load-bearing)
    PHASES.md               Implementation contract for single-planner session
    workers/planner.mld     Planner session + 6 tool wrappers
    session.mld             var session @planner schema
    runtime.mld             State helpers, display projection, tool dispatch
    intent.mld              Authorization intent compilation
    tooling.mld             Catalog helpers, policy synthesis
    prompts/planner.att     THE MAIN ITERATION TARGET for utility work
    tests/index.mld         Zero-LLM invariant gate (92 assertions)
  bench/                  Benchmark (consumes rig, suite-specific)
    ARCHITECTURE.md         How bench consumes rig
    agents/<suite>.mld      Agent entrypoints (~20 lines each)
    domains/<suite>/        Records, tools, bridge per suite
  SCIENCE.md              Working experiment log — task tables, patterns, theories
  AGENT_DEBUGGING_GUIDE.md  Investigation methodology
  *.taskdata.txt          Per-suite tool/model/task reference (from AgentDojo)
  *.threatmodel.txt       Per-suite attack trees and defense specs
  labels-policies-guards.md  Security model narrative (symlink to benchmarks/)
  src/                    Python host (minimal — run.py, host.py, mcp_server.py)
```

## Cardinal Rules

**A. No benchmark cheating.** Never read AgentDojo checker code. Never add task-id-specific logic. Never shape prompts around expected answers.

**B. Separation of concerns.** Rig is generic. Bench is specific. Suite knowledge goes in tool `instructions:` or suite addendums — never in `rig/prompts/`.

**C. Don't blame the model.** GLM 5.1 outperforms Sonnet 4.6. Past architectures hit 80%+ on these suites. When utility is low, the problem is prompt education or framework bugs.

## Current Focus

Prompt education (Step 12b). The framework is correct; the planner doesn't exercise it efficiently. See SCIENCE.md for the failure analysis, pattern classification, and experiment queue.

## Commands

```bash
# Invariant gate
mlld clean/rig/tests/index.mld --no-checkpoint

# Single task
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_11

# Full suite
uv run --project bench python3 src/run.py -s workspace -d defended -p 3

# Build mlld after runtime changes
cd ~/mlld/mlld && npm run build

# Tickets
tk ready          # what's actionable
tk ls             # all open
tk show <id>      # details
```

## Key Docs (read order for new session)

1. `SCIENCE.md` — current state, task tables, failure patterns, theories
2. `AGENT_DEBUGGING_GUIDE.md` — investigation methodology
3. `rig/ARCHITECTURE.md` — why the framework is shaped this way
4. `rig/SECURITY.md` — what must never be weakened
5. `workspace.taskdata.txt` (or relevant suite) — ground truth for task requirements
