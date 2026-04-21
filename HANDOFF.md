# Session Handoff

Last updated: 2026-04-20

## What This Session Accomplished

### Rig primitive migration (Step 12 items 1, 2, 6)
- Migrated `session.mld` to `var session @planner` (~1000 lines deleted net)
- Extracted `@settlePhaseDispatch` wrapper factory
- Deleted dead `guards.mld` (309 lines)
- Found and fixed: `var tools` session-frame propagation bug (m-87eb)
- Found and fixed: session must attach to provider call, not routing wrapper
- Gate: 92/0, all four suite canaries pass

### Runtime OOM mitigation (m-2241)
- Diagnosed: `sessionWrites` array cloning `previous` values is O(n²)
- Fix: skip cloning `previous` when tracing is off + cap array at 200
- Committed in mlld runtime (`interpreter/session/runtime.ts`, `interpreter/env/Environment.ts`)

### Budget fix
- Lowered `maxIterations` from 40 to 25 (prevents 900s timeout cascade)
- Added `budget_warning` in `@settlePhaseDispatch` (nudges planner to compose when 3 calls remain)

### Full-suite baseline established
- Workspace: ~42%, Banking: ~37-44%, Slack: 24-38%, Travel: 5%
- Framework path is clean — no crashes, no infra errors on the fixed binary
- Failures are planner-quality, not framework

### Root cause analysis for looping failures
- Documented at `tmp/investigation-planner-looping.md`
- Three patterns: resolved-ref confusion, wrong-phase looping, repeated failed executes
- All are prompt/attestation education gaps, not model capability limits

## What Needs to Happen Next

### Immediate: Prompt pattern testing (Step 12b in PLAN.md)

The #1 utility lever. The framework is correct but the planner doesn't exercise it efficiently.

1. **Write isolated pattern tests** at `rig/tests/patterns/*.mld` — each exercises one planner behavior pattern with a minimal agent (1-2 tools). Cost: ~$0.01 per run, ~30s.

2. **Iterate on `rig/prompts/planner.att`** until all 5 patterns pass reliably on GLM 5.1. The patterns to nail:
   - resolve → execute with resolved ref (the #1 failure)
   - resolve → resolve with resolved ref (handle chaining)
   - source-backed extract from resolved state
   - derive → selection ref → execute
   - wrong-phase correction in ≤2 attempts

3. **Execute the prompt split**:
   - `rig/prompts/planner.att` — generic rig discipline only
   - `bench/domains/<suite>/prompts/planner-addendum.att` — suite-specific rules
   - Lines 65-66 of current planner.att are task-shaped workspace rules that must move

4. **Improve error messages** in tool wrappers:
   - `known_value_not_in_task_text` → suggest the correct resolved ref
   - Wrong-phase after 2 errors → auto-route instead of repeating the error
   - `control_ref_requires_specific_instance` → name available handles

### After prompts: remaining Step 12 items

- Items 3-5 (direct:true, optional-fact, tooling.mld) — blocked on runtime primitives
- Items 7-9 (phaseToolDocs deletion, MCP coercion audit) — after prompt work
- Final measurement on Sonnet 4

### Deferred

- Travel suite strategy (recommendation-hijack defense)
- `supply:` adoption
- Rigloop on v2

## Cardinal Rules for the Next Session

### A. No benchmark cheating, reading, or overfitting

Never look at AgentDojo checker code. Never add task-id-specific logic. Never shape prompts around what you know the evaluator expects. If a prompt fix only helps one task, it doesn't ship. Test against a CLASS of tasks, not one task.

### B. Proper separation of concerns

Rig is a framework; bench is a consumer. Rig must not know about workspace calendars, slack channels, banking transactions, or travel hotels. Suite-specific knowledge goes in tool `instructions:` fields or suite-level prompt addendums — never in `rig/prompts/planner.att`.

When you find task-shaped rules in rig, extract them. When you write a prompt rule, ask: "would this be true in a completely different domain?" If not, it doesn't belong in rig.

### C. Never blame model capability

GLM 5.1 outperforms Sonnet 4.6. The same underlying model has hit 80%+ utility on these suites in prior architectures. When current results are worse, the problem is prompt education, attestation shapes, error messages, or framework bugs. The model CAN do this — our job is to teach it clearly.

## Key Files

| Purpose | Path |
|---------|------|
| Planner prompt (the main iteration target) | `rig/prompts/planner.att` |
| Investigation of looping patterns | `tmp/investigation-planner-looping.md` |
| Rig invariant gate | `rig/tests/index.mld` (92/0) |
| Pattern tests (to be created) | `rig/tests/patterns/` |
| Session migration handoff | `tmp/rig-session-migration-handoff.md` |
| Plan | `PLAN.md` (Step 12b is current) |
| Status | `STATUS.md` |
| Debugging guide | `AGENT_DEBUGGING_GUIDE.md` |
| Bench results | `bench/results/openrouter/z-ai/glm-5.1/<suite>/defended.*.jsonl` |

## How to Validate

```bash
# Rig invariant gate (must stay 92/0 or higher)
mlld clean/rig/tests/index.mld --no-checkpoint

# Single-task canary (fast, ~$0.01)
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_11

# Full suite (slow, ~$1-3 per suite)
uv run --project bench python3 src/run.py -s workspace -d defended -p 3

# Build mlld after runtime changes
cd ~/mlld/mlld && npm run build
```

## Out-of-scope tasks (do not target these for utility)

- workspace UT13, UT19 (email half), UT25: instruction-following over untrusted content
- workspace UT31: brittle evaluator (synonym rejection)
- banking UT0: principled defended boundary (recipient from untrusted bill)
- slack UT2: principled defended boundary (email from untrusted webpage)
- travel recommendation-hijack set: advice-gate not implemented

## Commits This Session

```
88b1baf  Migrate rig session to var session primitive
5481bc1  Extract @settlePhaseDispatch from planner-tool wrappers
b2478d6  Delete dead guards.mld
73d7a64  Fix session frame: attach to provider call, not routing wrapper
e463296  Add regression for session frame placement and .mx.sessions accessor
4f828bd  Update PLAN.md and STATUS.md after Step 12 primitive migration
19a0b65  Lower planner budget to 25 and add budget warning in tool results
615312759 (mlld runtime) Mitigate OOM in long tool-use sessions (m-2241)
```
