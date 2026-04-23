# clean/ project

Rig v2 framework + AgentDojo benchmark implementation for mlld.

## First Actions

```bash
mlld clean/rig/tests/index.mld --no-checkpoint   # invariant gate (must be 96/0)
mlld rig/tests/workers/run.mld --no-checkpoint   # worker LLM tests (must be 17/17)
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
    tests/index.mld         Zero-LLM invariant gate (96 assertions)
    tests/workers/          Live LLM worker tests (17 tests, ~50s)
  bench/                  Benchmark (consumes rig, suite-specific)
    ARCHITECTURE.md         How bench consumes rig
    agents/<suite>.mld      Agent entrypoints (~20 lines each)
    domains/<suite>/        Records, tools, bridge per suite
  SCIENCE.md              Working experiment log — task tables, patterns, theories
  DEBUG.md                Investigation methodology
  archive/*.taskdata.txt  Per-suite tool/model/task reference (from AgentDojo, archived)
  *.threatmodel.txt       Per-suite attack trees and defense specs
  labels-policies-guards.md  Security model narrative (symlink to benchmarks/)
  src/                    Python host (minimal — run.py, host.py, mcp_server.py)
```

## Cardinal Rules

**A. No benchmark cheating.** Never read AgentDojo checker code. Never add task-id-specific logic. Never shape prompts around expected answers.

**B. Separation of concerns.** Rig is generic. Bench is specific. Suite knowledge goes in tool `instructions:` or suite addendums — never in `rig/prompts/`.

**C. Don't blame the model.** GLM 5.1 outperforms Sonnet 4.6. Past architectures hit 80%+ on these suites. When utility is low, the problem is prompt education or framework bugs.

**D. SERIOUSLY. DON'T BLAME THE MODEL OR "NONDETERMINISM" OR "FLAKINESS"** Read the agent transcripts. No GUESSES as to WHY tests fail without EVIDENCE. 

## Current Focus

Workspace utility: 31/40 (77.5%), up from 14/40 baseline. Ceiling is 35-36/40 (87-90%). 4 remaining failures have tickets with transcript evidence and fix paths. Next priorities: UT8 handle metadata fix (c-ut8r), execute result handles (c-6c90r), then sweep slack/banking/travel. See SCIENCE.md for full results and HANDOFF.md for session context.

Use `/rig` at the start of each session to load all required context docs.

## Prompt Placement Rules

Three layers of prompt content, each with a clear scope. When writing or reviewing a rule, ask: "Would this be true in a completely different domain?" If yes → rig prompt. If true for any task in this suite → suite addendum. If true for any caller of this tool → tool description/instructions.

### Layer 1: Rig prompt (`rig/prompts/planner.att`)

Framework discipline only. Phase rules, ref grammar, source class rules, terminal discipline, anti-looping, budget awareness. Must be domain-agnostic — no mention of calendars, contacts, emails, hotels, channels, or any suite-specific entity.

**Test:** Would removing this rule cause a wrong tool call shape, a wrong source class, or a protocol violation regardless of domain? If yes, it belongs here.

### Layer 2: Suite addendums (`bench/domains/<suite>/prompts/`)

Domain workflow patterns. How to reason about data in this specific domain — multi-step patterns, availability calculations, cross-record reasoning strategies. Must be true for any task in that suite, not just one task.

**Test:** Would removing this rule cause wrong reasoning for a CLASS of tasks in this suite? If yes, it belongs here. If it only helps one task, it's overfitting.

### Layer 3: Tool descriptions and `instructions:` fields

Per-tool usage guidance in the tool catalog entry. Arg format constraints, scalar-vs-array clarification, when to prefer this tool over similar ones. Must be true for any caller of the tool.

**Test:** Would removing this cause a wrong call to THIS specific tool? If yes, it belongs here. If the guidance is about when to call the tool relative to other tools, it might belong in the suite addendum instead.

### What does NOT belong in any prompt layer

- Task-id-specific logic ("for task X, do Y")
- Evaluator-shaped rules ("the checker expects this exact wording")
- Model-specific workarounds ("GLM sometimes does X, so add Y")
- Redundant restatements of rules already in a higher layer
- Rules that only help one task — if a rule's entire justification is one benchmark result, it's overfitting

## Commands

```bash
# Invariant gate (must be 96/0)
mlld clean/rig/tests/index.mld --no-checkpoint

# Worker LLM tests (must be 17/17, ~50s)
mlld rig/tests/workers/run.mld --no-checkpoint

# Single task
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_11

# Full suite (default -p 20, 5s stagger)
uv run --project bench python3 src/run.py -s workspace -d defended

# Build mlld after runtime changes
cd ~/mlld/mlld && npm run build

# Tickets
tk ready          # what's actionable
tk ls             # all open
tk show <id>      # details
```

## Rules learned the hard way

- **Never use `show` in exe functions during bench runs.** It writes to stdout and corrupts the host's JSON parsing. Use `log` (stderr) or `MLLD_TRACE` instead.
- **Never rename record fields to match MCP parameter names.** The intent compiler maps arg keys to resolved values — the names don't need to match. Field renaming across the MCP boundary destroys StructuredValue metadata.
- **Run worker tests before and after prompt changes.** `mlld rig/tests/workers/run.mld --no-checkpoint` catches regressions in ~50s. If tests pass too easily, the assertions are too weak.

## Deferred: Logging Refactor (ticket c-3edc)

A designed but unstarted refactor of rig's logging stack to lean on the runtime trace subsystem (`--trace effects` via SDK) plus `var session @planner` plus a small curated hook layer. Net effect: `lifecycle.mld` + `runtime.mld @appendLlmCall` + per-wrapper boilerplate shrink; rig gets parent/child LLM-call timing for free; the m-5683 / UT14 bug classes disappear structurally.

Not scheduled. Raise it when any of the following bite: chasing per-worker timing bottlenecks by hand, another lifecycle emission seam getting added manually, shelf-based session state producing an aliasing/null-callback regression, or the bench analyzer wanting a structured call tree. Full plan lives in ticket c-3edc.

## Key Docs

Use `/rig` at session start to load these with instructions to read them all. See `.claude/skills/rig.md` for the full onboarding sequence.

1. `labels-policies-guards.md` — security model narrative
2. `rig/ARCHITECTURE.md` — framework architecture and separation of concerns
3. `bench/ARCHITECTURE.md` — how bench consumes rig
4. `DEBUG.md` — investigation methodology
5. `SCIENCE.md` — experiment log, task tables, failure analysis
6. `HANDOFF.md` — session-to-session context and next steps
