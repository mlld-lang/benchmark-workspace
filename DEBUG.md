# AGENT_DEBUGGING_GUIDE.md

Guide for agents investigating utility, security, or runtime regressions in this benchmark repo.

This document is intentionally operational. It is not a design manifesto. It tells you how to debug the current rig-based system without wasting cycles on the wrong frontier.

## Cardinal Rules (Read Before Every Session)

**A. No benchmark cheating, reading, or overfitting.** Never look at AgentDojo checker code to reverse-engineer expected answers. Never add task-id-specific logic. Never shape prompts around what you know the evaluator expects. If a prompt fix only helps one task, it doesn't ship.

**B. Proper separation of concerns.** Rig is a framework; bench is a consumer. Rig must not know about workspace calendars, slack channels, banking transactions, or travel hotels. Suite-specific knowledge goes in tool `instructions:` fields or suite-level prompt addendums — never in `rig/prompts/planner.att`. When you find task-shaped rules in rig, extract them.

**C. Never over-eagerly blame model capability.** GLM 5.1 outperforms Sonnet 4.6. The same underlying model has hit 80%+ utility on these suites in prior architectures. When current results are worse, the problem is prompts, attestation shapes, error messages, or framework bugs — not "the model is weak." Prompt education is the variable; model capability is the constant.

**D. Never underestimate the value of clear, educational error messages, clear tool instructions, and clear prompts.** Don't overindex on the orchestrator code. Always double-check the prompts. Just make sure to avoid overfitting and keep proper separation of concerns: no benchmark domain related stuff in rig. No overfitting to the benchmarks anywhere. 

## Core Position

Do not blame the base model.

The same underlying model has hit substantially better utility on these suites in prior architectures. When current results are much worse, assume the regression is in:

- benchmark orchestration (Python host bridge in `src/`)
- rig framework dispatch (planner / resolve / extract / execute / compose phases)
- runtime contract (mlld value boundaries, structured-value wrappers, label propagation)
- tool exposure (input records, `var tools` catalog metadata, display projections)
- per-step authorization (`@policy.build` output and the with-clause threading)
- shelf state propagation (slot refs, cross-phase identity)
- planner prompt or tool contracts (planner tool-call args, wrapper attestation shapes)
- record coercion (=> record output, factsources, display projections)

Treat this as a rig + runtime regression hunt, not a "the model is weak" story.

The cardinal debugging rule from CLAUDE.md still applies: **before blaming model quality, check tool/runtime shape drift, handle/display projection loss, authorization control-arg mismatches, planner structured-output failures, compose/closeout formatting mismatches, shelf slot grounding or access-control gaps, and stale cached tool specs.**

## Spike First. Sweep Last. (Read this twice.)

**The single most expensive mistake an agent can make in this repo is using a sonnet 4 sweep to discover a question a $0 spike could have answered in five minutes.**

A sonnet 4 sweep is an integration test. It is NOT a diagnostic tool. It will tell you "something is wrong" but it will not tell you what is wrong, and it will charge you several dollars and twenty minutes to do it. Then you will read transcripts, hypothesize, run another sweep, and discover a different thing is wrong. This is the failure pattern that consumed entire prior sessions.

Spikes are a diagnostic tool. They cost zero LLM dollars when written against synthetic data. They run in seconds. They produce a deterministic matrix that decisively answers ONE question.

The discipline:

1. **Before any sonnet 4 run**, ask: "what specific question am I trying to answer, and could a synthetic probe answer it?" If yes, write the probe. Sonnet 4 is for verification AFTER the framework path is clean, not for discovering gaps in the framework path.

2. **When a sweep produces a failure**, the next move is NOT "run the sweep again with logging." The next move is "what design question does this failure expose, and can I extract that question into a probe?" If the answer is yes, the probe is the next thing you write — not another sweep, not a hypothesis-driven prompt edit.

3. **When you find yourself reading the third transcript trying to understand what the planner emitted**, stop. Build a probe that synthesizes the planner's intent and runs `@policy.build` directly. The transcripts are giving you symptoms; the probe gives you the contract.

4. **A probe earns its keep by being decisive.** Bad probes confirm what you already suspected. Good probes return a matrix where the result rules out at least one hypothesis no matter how it lands. If your probe can only return "looks fine" or "still broken," you haven't actually formulated the question.

### Canonical worked example: b-6ea2 (cross-phase shelf-derived bucket flow)

Read this. It is the pattern.

- **Symptom**: workspace UT13/14/25 = 0/3 on a sonnet 4 verification run that cost real money. Failure modes were inconsistent across the three tasks (one fabricated handle string, one looped on reads, one wrote bare literal in `resolved`).
- **Initial hypothesis**: some structural cross-phase identity bug, possibly architectural.
- **Push-back from prior session**: "before you call it architectural, write a probe."
- **The probe** (`tmp/probe-cross-phase-bucket/probe.mld`): synthetic record with a fact field, fake search exe with `=> record` coercion, JSON-parse roundtrip to mimic what the planner emits, then `@policy.build` called with seven different `(bucket, value-origin, task-config)` combinations. Outputs a 7-row matrix.
- **Result**: matrix decisively showed `known` accepts shelf-derived values without task-text validation. The fix turned out to be a ~5-line planner.att prompt change. No runtime change. No dispatcher change. No architectural redesign.
- **Cost**: probe wrote in 10 minutes, ran in seconds, no LLM. The sweep that discovered the symptom cost ~$0.30 and 12 minutes. The probe was 50× cheaper to run and 100× more diagnostic.
- **What the probe could rule out**: every conceivable wrong fix path. If it had landed differently, the fix could have been a runtime relaxation, a new bucket type, a dispatcher rewrite, or a display-projection re-architecture. Instead the matrix collapsed all of those to "change five lines of prompt."

The spike's `SCIENCE.md` is a model for what spike documentation should look like: question, method, results table, conclusions, fix, what-this-does-NOT-fix. Steal that template.

### When a spike is the right move (almost always)

| Situation | Spike or sweep? |
|---|---|
| "The planner emits X but the dispatcher expects Y" | **Spike.** Synthesize X, call the dispatcher, read the error. |
| "I think this value is losing factsources at the boundary" | **Spike.** Print `.mx.factsources` before and after. |
| "Does `@policy.build` accept this shape?" | **Spike.** Call it directly with synthetic intent. |
| "Will the auto-upgrade fire when no `task` config is passed?" | **Spike.** That's literally b-6ea2. |
| "Does this guard fire on this op label?" | **Spike.** Synthetic exe + the guard, no LLM needed. |
| "I changed the planner prompt — does the model emit the right shape now?" | **Sweep.** Single task. Can't synthesize this. |
| "The framework path is clean; how does utility look on the full suite?" | **Sweep.** This is what sweeps are for. |
| "I want to know if a class of failures has been resolved" | **Sweep**, but a small one (3-5 tasks), AFTER the spike-driven fix landed. |

If the question is "what does the runtime do given this input?", the answer is always a spike. If the question is "what does the model produce given this prompt?", the answer is a small targeted run with verification. Sonnet 4 sweeps are reserved for "the framework path is clean; measure utility."

### Check the agent transcript before writing anything

When a benchmark run fails and the JSONL just says `blocked` or `utility: false`, the **agent transcript** has the full story — every planner tool call, every worker dispatch, every policy denial with the actual reason string. The transcript is the highest-signal diagnostic surface in this repo. Check it before hypothesizing.

**Where transcripts live depends on the harness:**

#### Opencode transcripts (primary harness for bench runs)

Use the Opencode surfaces in this order:

**1. Session database** (`~/.local/share/opencode/opencode.db`): best live surface while the run is still active. The `part` rows show tool calls, reasoning, step boundaries, and tool outputs as they land. This is the first place to look when you want to know what the planner is doing *right now*.

**2. Session part storage** (`~/.local/share/opencode/storage/part/`): best raw surface after the run finishes. The per-part JSON files are still valuable, but they are less convenient than the DB when you are following a live session.

**3. Operational logs** (`~/.local/share/opencode/log/`): coarse process/session tracing only. These are useful for continuity questions ("did the outer session ID stay stable?", "did the provider request finish?"), not for tool-call semantics.

Use the helper in `clean/src/opencode_debug.py` instead of ad hoc sqlite one-offs:

```bash
# List recent sessions
python3 clean/src/opencode_debug.py sessions

# Show recent parts for the latest session
python3 clean/src/opencode_debug.py parts --session latest --limit 20

# Follow a live session as new parts arrive
python3 clean/src/opencode_debug.py follow --session latest

# Show coarse opencode log lines for one session
python3 clean/src/opencode_debug.py logs --session lucky-knight
```

If you need the raw files after completion:

```bash
ls -lt ~/.local/share/opencode/storage/part/ | head -20
cat ~/.local/share/opencode/storage/part/<msg_id>/<part_file>.json | jq .
```

**Finding the session ID:** The bench result JSONL includes the session ID. Also check the rig execution log and audit trail:

```bash
# From the audit trail
jq -c 'select(.event | contains("session"))' clean/bench/.llm/sec/audit.jsonl | tail -5

# From the result row
jq -r '.session_id // .metrics.planner_session_id // empty' results/.../defended.jsonl | tail -1
```

If the run is still active and no result row exists yet, use `python3 clean/src/opencode_debug.py sessions` and pick the most recently updated session with the matching task title.

Two rules that matter here:

- A null inner worker session ID is not planner thread loss. The continuity question is whether the **outer planner** session ID stays stable across assistant turns.
- If the bench debug `llm_call_log_*.jsonl` exists, read `call_kind`, `outer_planner_session_id`, and `inner_worker_session_id` before concluding anything about resume or thread loss.

#### Claude Code transcripts

If the harness is `@claude` (native mlld Claude module), transcripts live at `~/.claude/projects/`. Use `spy` to look them up:

```bash
spy <session-id>
spy <session-id> tail -50
spy ls  # list recent sessions, correlate by timestamp
```

#### What to look for in any transcript

- **Tool call sequence**: which rig tools did the planner call, in what order, with what args?
- **Tool results**: what attestations came back? Were they clean (handles + status) or did tainted content leak?
- **Policy denials**: rule name, matched label, which arg failed proof
- **Planner reasoning**: did the planner understand the task? Did it ground contacts before trying to send? Did it attempt resolve before extract?
- **Error budget exhaustion**: did the planner burn its invalid-tool-call budget? On what failure?
- **Terminal behavior**: did compose/blocked fire correctly? Did the planner emit a final text turn after the terminal tool result?
- **Missing tool calls**: did the planner skip an obvious resolve step? Did it try to derive what it should have resolved?

Five seconds of transcript reading often resolves what would otherwise require a spike. The guidance above still applies — if the transcript shows a runtime/framework question, write a spike. But don't skip the transcript and go straight to probes. The transcript is the cheapest diagnostic surface you have.

### The cost arithmetic

A typical sonnet 4 workspace task: 30-90 seconds, ~$0.10. A 3-task verification: ~$0.30 + 5 minutes. A full workspace sweep: ~$2-3 + 20 minutes. A failed sweep cycle (sweep → read transcripts → hypothesize → fix → re-sweep) burns 30+ minutes and a few dollars per iteration.

A typical synthetic probe: 0 seconds of LLM time, $0, 10-15 minutes to write the first version, seconds to run, re-runnable forever as a regression guard.

Per session, the difference between spike-first and sweep-first discipline is the difference between four iteration cycles and twenty.

### Runtime fixes need a smoke check

m-6d5e and m-1e85 landed in the mlld runtime without any rig integration verification. Workspace UT14 went from `4 calls/PASS` to `17 calls/FAIL` between sessions because of it. **Runtime PRs that touch policy, shelf, handles, substrate exemption, tool dispatch, or factsources should not merge until they pass the rig smoke harness** (b-fefe). This is the third leg of the discipline alongside "spike before sweep" — without it, fixes cause regressions and no one notices until the next sweep.

The smoke lives at `~/mlld/rig/spike/34-integration-smoke/`. Run it with:

```bash
mlld ~/mlld/rig/spike/34-integration-smoke/smoke.mld
```

It runs in under 1 second. Zero LLM API calls. 14 named assertions cover the m-* runtime regression classes (m-5b1c, m-d57b, m-9491, m-ef86, m-071b, m-e4ca, m-11d3, m-1e85), the thin-arrow strict-mode contract, and the stub-driven dispatch sequence. Each assertion is named after the originating ticket, so a failure points directly at the contract that regressed.

**First action of any rig framework session: run the smoke. If it's red, fix that before touching anything else.** It is the cheapest signal in the repo.

## Primary Rule

If utility is bad even in `undefended` mode, the main blocker is not defended security policy.

But: in the rig architecture there is currently no clean undefended mode (b-6e5d tracks adding one). Use the same principle differently:

- If a single task fails on **any** model: investigate the rig dispatch path first
- If a single task fails on the **default dev model** but progresses further on a comparison model: inspect the prompt, harness, and trace before assuming a model-quality problem
- If a single task fails consistently across models: probably orchestration, prompts, or tool metadata

## Anti-Goals

Avoid these traps:

- **Do not run sonnet 4 sweeps to discover design gaps.** Sweeps are integration tests, not diagnostic tools. If your sweep produces a failure that exposes a design question, the next move is a probe, not another sweep. See "Spike First. Sweep Last." above.
- **Do not pipe shelf state through `| @pretty` (or any JSON serialization) into a prompt.** Serialization strips display projection, factsources, labels, and handles. The planner/worker downstream sees no proof. See "Serialization is a one-way trip" below.
- **Do not use `@parse` output (or any JSON-parsed value) as if it carries proof.** JSON parse strips everything. Cross-phase identity must flow through value-keyed registry lookup (`known` bucket auto-upgrade), not through trusting parsed strings.
- Do not add task-shaped prompt examples just because a single benchmark task is failing.
- Do not "mind-read the checker" by adding exact instructions for one task id.
- Do not assume a runtime bug until you have ruled out rig framework misuse and prompt/orchestration causes.
- Do not trust the attack JSONL `security` field as the ASR verdict. Use the console attack summary first.
- Do not assume dates. Read [README.md](/Users/adam/mlld/benchmarks/README.md) and [src/date_shift.py](/Users/adam/mlld/benchmarks/src/date_shift.py) before reasoning about temporal behavior.
- Do not hand-roll authorization semantics in benchmark JS. Use `@policy.build(...)` and `@policy.validate(...)`.
- Do not work around runtime bugs in rig/benchmark code without filing a runtime ticket. Workarounds accumulate into the exact compatibility layer mlld exists to replace.
- Do not batch-edit tool wrappers, records, contracts, or shelves without re-running smoke tests after each change.
- **Do not skip the rig smoke harness check on runtime fixes.** When a `m-*` ticket lands in `~/mlld/mlld`, run the b-fefe smoke harness (when it exists) before the next sweep. Untested runtime fixes cause regressions that look like model failures but aren't.

## What Good Work Looks Like

Good changes are:

- generalizable across suites
- structural rather than checker-shaped
- deterministic when possible
- validated by targeted reruns before full checkpoints
- documented in tickets when they reveal a runtime gap

Examples of good change classes:

- runtime-side fixes that close a structuredvalue boundary gap (filed against `~/mlld/mlld/.tickets/`)
- rig framework refinements that propagate substrate marking, tool context, or shelf identity through more code paths
- structural planner schema constraints (b-d394 pattern: schema-level validators that catch over-cautious blocking before it costs an LLM call)
- record-level display mode improvements (planner sees less; worker sees content with masked facts)
- contract pinning for write workers (extract phase only emits the contract's declared fields)
- shelf access scope tightening per box (workers receive typed inputs, not state)

## Debugging Order

Always debug in this order:

1. Reproduce one failing task locally with a single deterministic command.
2. Decide whether the failure is in `defended` mode (the only mode currently supported in rig).
3. Inspect the JSONL log AND the verbose trace to determine whether the failure is:
   - runtime bug (boundary, label propagation, substrate exemption)
   - rig framework bug (dispatcher contract, schema validation, prompt shape)
   - planner-quality (model's reasoning failure visible in trace)
   - LLM-side execution failure (the model called a tool but with wrong args)
   - host parsing failure (the model emitted text the host couldn't parse)
4. Make the narrowest generalizable change.
5. Rerun only the affected task or attack slice.
6. Only then spend a full-suite checkpoint.

## First Triage Split

### A. Runtime / boundary failure

Symptoms:
- Task dies with `Operation denied / Rule: <something>` on `/exe "claude"` or a `cmd:*` allow rule
- The error fires before the LLM has a chance to do anything substantive
- The same failure reproduces deterministically

This is usually:
- A structuredvalue boundary gap (a value's wrapper shape isn't recognized by a runtime consumer)
- A substrate exemption gap (some guard family doesn't honor the substrate marking)
- A taint propagation issue (a label propagating where it shouldn't, or stripping where it should preserve)
- A field access losing identity / metadata across parameter binding

Debugging path: see `Minimal Repro Method` below.

### B. Rig framework / wrapper bug

Symptoms:
- Planner calls a rig tool (resolve, extract, execute, etc.) correctly
- The wrapper fails internally — shelf state shape mismatch, missing field, when-arm fall-through, wrong object passed to worker
- The error references a line in `rig/workers/planner.mld`, `rig/orchestration.mld`, or `rig/runtime.mld`

This is usually:
- The wrapper assumed something about the planner's tool-call args that the planner didn't provide
- A let-binding intermediate dropping wrapper metadata (the StructuredValue stripping family)
- State not being passed correctly between wrapper invocations (wrong object aliasing — see m-5683 family)
- The wrapper returning tainted content to the planner instead of clean attestation

Debugging path: check the opencode transcript for the exact tool-call args the planner sent, compare to what the wrapper expected, fix the contract. If state is the issue, add `show` diagnostics inside the wrapper to verify what `state` and `query` actually are on each invocation.

### C. Planner-quality failure

Symptoms:
- Planner calls `blocked` prematurely without attempting resolve
- Planner calls `execute` with values it derived/inferred instead of grounding via `resolve` first
- Planner calls `compose` without performing the expected writes
- Planner burns its error budget by repeatedly calling tools with bad args
- The transcript shows real tool calls happening (not just immediate denials)

This is usually:
- The planner not understanding the resolve-before-execute discipline
- The planner inferring values from tainted content instead of grounding contacts/entities via resolve tools
- The planner over-reading defense rule names in the prompt and pre-emptively blocking
- Insufficient context in the planner prompt about source-class rules (resolved vs known vs derived)

Typical fixes:
- Tool-wrapper validation returning a structured error that guides the planner to the correct approach
- Planner prompt clarification (general behavioral rule, not task-specific examples)
- Move the constraint from prompt to code (wrapper enforces it, planner sees the error as a tool result)

Avoid: task-id-specific prompt examples. The planner should learn from tool errors in-session, not from pre-loaded examples.

### D. LLM-side execution failure

Symptoms:
- Planner correctly classifies the task
- Resolve / extract dispatchers fire correctly
- Execute dispatcher reaches @claude with valid auth
- But the worker LLM calls the tool with wrong args (wrong recipient, wrong amount, wrong shape)

This is usually:
- Model arithmetic miss or hallucination
- Worker LLM not recognizing handles in the input as references to use verbatim
- Worker LLM being told to be helpful and overriding the structured-input contract

Typical fixes:
- Tighter contract enforcement at the extract phase
- Clearer worker prompt about handle pass-through
- Move from "worker reasons about state" to "worker dispatches one call with provided typed inputs"
- Planner schema retry on detected shape errors (auth.valid check pattern)

### E. Host / final-answer parsing failure

Symptoms:
- Tool calls happened correctly
- Compose phase produced text
- But `final_output` is the literal string `"Task completed."` (the host's fallback)
- Or the host reports `outcome: unparseable`

This is usually:
- The compose phase emitted text that doesn't match the `{ "content": "..." }` shape the host expects
- A non-JSON-wrapped string at the top of the agent's output
- An exception in the agent's final return clause

Typical fixes:
- Compose phase should always wrap output as `=> { content: @result.final.text }`
- Ensure no `show` / `output` directives in the agent file produce stdout that competes with the JSON return

## Troubleshooting parallel runs

How to run benchmarks (local + remote) lives in **CLAUDE.md "Running benchmarks"**. This section captures the specific failure modes you'll see when remote sweeps misbehave and the empirical findings behind the per-suite shape choices in `scripts/bench.sh`.

### When a run fails with exit code 137 (SIGKILL)

That's the kernel OOM-killer. The container exhausted memory under the requested parallelism. Each bench task carries the AgentDojo TaskEnvironment + an mlld + MCP server in RAM (~1.5-2 GB at peak), so fan-out memory scales linearly with `-p`.

History (Team plan, 8x16/16x32/32x64 shapes):

| Suite | Shape | Parallelism | Result | Run ID |
|---|---|---|---|---|
| workspace-a | 8x16 | 18 (task-count cap) | OOM exit 137 | 24922643802 |
| workspace-b | 8x16 | 18 | OOM exit 137 | 24922644218 |
| travel | 8x16 | 20 | OOM exit 137 | 24922900959 |
| travel | 16x32 | 20 | OOM exit 137 | 24923046920 |
| banking | 8x16 | 15 | success | 24922644697 |
| slack | 8x16 | 14 | success | 24922900581 |

That's where `bench.sh`'s shape table comes from. If you bump parallelism or change a suite's task surface, expect to recalibrate.

To diagnose a fresh OOM: check `gh run view <id> --log 2>&1 | grep -E "exit code|137|Killed"`. If exit 137, drop `-p` by half or bump shape one tier.

### When a run "succeeds" but utility is suspiciously low (c-63fe)

Travel's MCP server destabilizes under load. Symptoms in the result jsonl / transcripts:

- `Not connected` errors on tool calls
- `Request timed out` errors
- `Connection closed` errors
- Planner appears stuck in resolve loops (Pattern C symptom) but the cause is infrastructure, not planning

Real example: travel run on 32x64 `-p 20`: 2/20 utility, 102 MCP infrastructure errors (71 Not connected, 19 timeouts, 12 Connection closed). Utility number is **not measurable** while c-63fe is open.

Workarounds:
- `scripts/bench.sh travel` solo uses 32x64 + `-p 20` (max memory headroom; some MCP errors still expected)
- For travel utility debugging right now, run **locally** instead — the local MCP environment doesn't hit c-63fe. On a 48 GB Mac: `uv run --project bench python3 src/run.py -s travel -d defended -p 20` (full parallelism). On smaller machines drop `-p` to fit.
- The hybrid pattern (travel local while other suites run remote) is documented in CLAUDE.md.

When you see "Not connected" in transcripts: it's c-63fe, not a planning failure. Don't chase it as a planner bug.

### When the freshness gate fails

If `bench-run.yml`'s "Check image freshness" step errors, common causes:
- `gh` CLI in the workflow can't determine repo without `GH_REPO` env (already fixed; if you see `failed to determine base repo`, that env got dropped somewhere)
- The mlld branch label is missing from the image (older images pre-dating the labels — auto-rebuild handles it, watch for "image lacks mlld labels — rebuilding to be safe" notice)
- `MLLD_LANG_REPO_TOKEN` secret missing → cross-repo PAT unavailable for the private agentdojo fork (the workflow falls back to GITHUB_TOKEN which can't read the private repo)

### When to use remote vs local

| Situation | Where |
|---|---|
| Single-task debugging with `MLLD_TRACE` or `--debug` | Local |
| 1-3 task verification of a fix | Local |
| Reading a live opencode session as it runs | Local (remote opencode DB isn't reachable until the run finishes) |
| Travel utility measurement (until c-63fe is fixed) | Local |
| Full suite sweep | **Remote** |
| Comparing all 4 suites before/after a fix | **Remote** fan-out (`scripts/bench.sh`) |
| Iterating on a prompt change | Remote single-suite during iteration; remote fan-out for the final measurement |

## Commands You Should Use

### Validate the framework + benchmark

```bash
mlld validate bench/agents/workspace.mld
mlld validate rig
```

### Run the rig test gate

```bash
mlld --new rig/tests/index.mld
```

### Run one benign task (defended mode, default GLM 5.1)

```bash
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_0
```

### Run multiple tasks in parallel

```bash
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_0 user_task_1 user_task_6 -p 3
```

### Run with sonnet 4 (the comparison target)

```bash
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_0 --model claude-sonnet-4-20250514
```

### **Do NOT pass `--debug` on bench runs.** It enables in-memory retention of every SDK event and reliably triggers Node V8 OOM on any non-trivial task. Prefer `MLLD_TRACE` (file-based, richer signal, no memory pressure) for diagnostic depth.

### Run with runtime tracing

Tracing emits structured events for LLM calls, sessions, guards, policy, handles, display projection, and record coercion. `effects` is the default — it redacts sensitive content and covers 95% of debugging. `verbose` shows unredacted content plus additional read/import/handle detail; opt in only for specific deep dives, not on runs carrying real credentials or tainted content.

The bench host (`clean/src/host.py`) already forwards `MLLD_TRACE` and `MLLD_TRACE_FILE` env vars through to the SDK — no host changes needed.

```bash
# Default — effects level, NDJSON file sink
MLLD_TRACE=effects MLLD_TRACE_FILE=tmp/workspace-ut0-trace.jsonl \
  uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_0

# Deep dive — unredacted content, full read/import/handle detail
MLLD_TRACE=verbose MLLD_TRACE_FILE=tmp/workspace-ut0-trace.jsonl \
  uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_0
```

### Dispatch boundary diagnostics

`rig/diagnostics.mld` provides hook-based inspection of every dispatch boundary in the rig framework. It is imported by `rig/workers/planner.mld` and is on by default. The hooks observe `@input` and `@output` on named exe functions and log shape summaries to stderr with a `[rig:diag:*]` prefix. They do not modify any values or affect dispatch behavior.

To disable: remove `import "../diagnostics.mld"` from `rig/workers/planner.mld`.

#### What each hook logs

The four crash-prone boundaries (`dispatchResolve`, `dispatchExtract`, `dispatchExecute`, `callToolWithOptionalPolicy`) also have `hook before` variants that log an ENTER line with the key input args. These fire even when the exe crashes, so you always see what was attempted.

| Hook | Fires after | What it shows |
|---|---|---|
| `dispatchResolve` | resolve worker returns | record_type, count, handles; or error + summary |
| `dispatchExtract` | extract worker returns | name, schema_name, provenance, preview_fields; or error |
| `dispatchExecute` | execute worker returns | tool, status, result_handles; or error + per-issue detail |
| `compileExecuteIntent` | intent compilation for execute | per-arg: role, source_class, auth_bucket, attestation count, backing ref count; policy_intent keys with constraint types (has_eq, has_attestations) |
| `compileToolArgs` | arg compilation for resolve/extract | per-arg: role, source_class, auth_bucket |
| `callToolWithOptionalPolicy` | every tool dispatch | tool name, result type, has_error, has_policy |
| `normalizeResolvedValues` | raw output → rig state entries | record_type, entry count, per-entry handle/key/identity_field/identity_value |
| `validateToolCallArgs` | tool arg shape check | only on failure: missing args, extra args |
| `resolveRefValue` | each ref resolution | source, record, handle, value_type; or error + detail |

#### Filtering diagnostic output

Diagnostic lines go to stderr. During bench runs the host captures stderr, so use `grep` on the task's stderr output or redirect explicitly:

```bash
# Single task, capture diagnostics to a file
uv run --project bench python3 src/run.py -s workspace -d defended -t user_task_11 2>tmp/diag-ut11.log

# Filter just the diagnostic lines
grep '\[rig:diag' tmp/diag-ut11.log

# Filter one boundary
grep '\[rig:diag:compileExecuteIntent\]' tmp/diag-ut11.log

# Show only errors across all boundaries
grep '\[rig:diag.*ERROR\|FAILED' tmp/diag-ut11.log
```

#### When to use diagnostics vs other tools

| Question | Tool |
|---|---|
| "What value crossed the compile→policy→dispatch boundary?" | Diagnostics — `compileExecuteIntent` + `callTool` hooks show the full chain |
| "Why did `@policy.build` reject this intent?" | Runtime trace (`MLLD_TRACE=effects`) — trace shows `policy.compile_drop` events with reasons |
| "What did the planner actually call?" | Opencode transcript — shows the raw tool-call JSON the planner emitted |
| "Did the tool bridge return the right shape?" | Diagnostics — `callTool` hook shows result type; `normalizeResolvedValues` shows how it was coerced |
| "Is the ref pointing at a real resolved entry?" | Diagnostics — `resolveRefValue` hook shows resolution success/failure per ref |
| "Multiple bugs are stacked across layers and each fix reveals the next" | Diagnostics — this is what it was built for. Read the full boundary chain to see which layer dropped or transformed a value |

### Inspect latest result rows

```bash
ls -lt bench/results/openrouter/z-ai/glm-5.1/workspace | sed -n '1,12p'
jq -c '. | {task: .task_id, util: .utility, err: ((.execute_error // "") | .[0:200])}' \
  bench/results/openrouter/z-ai/glm-5.1/workspace/defended.jsonl
```

### Inspect opencode agent transcripts

```bash
# Recent sessions
python3 clean/src/opencode_debug.py sessions

# Follow the latest live session
python3 clean/src/opencode_debug.py follow --session latest

# Dump the most recent parts from a specific session
python3 clean/src/opencode_debug.py parts --session ses_...

# Coarse continuity/process tracing for that session
python3 clean/src/opencode_debug.py logs --session ses_...
```

### Filter trace events

```bash
jq -c 'select(.event == "guard.deny" or (.event == "guard.evaluate" and .data.decision == "deny")) | {ts, exe: .scope.exe, guard: .data.guard, reason: .data.reason}' \
  tmp/banking-ut3-trace.jsonl

jq -c 'select(.event == "policy.compile_drop")' tmp/banking-ut3-trace.jsonl

jq -c 'select(.event == "llm.call" and .data.phase == "finish") | {ok: .data.ok, dur: .data.durationMs}' \
  tmp/banking-ut3-trace.jsonl
```

Remember:
- Starting a new run for the same suite/defense rotates the old log
- Inspect the newest `*.jsonl` symlink target or the latest numbered file
- Verbose traces can be 10MB+ for multi-iteration runs — use `jq | head` and `jq -c` aggressively

## Where to Look in Logs

For each failing row in `results/<model>/<suite>/defended.jsonl`, inspect:

- `query`
- `final_output`
- `execute_error` (if mlld crashed)
- `mcp_calls` — what the agent actually called
- `policy_denials`
- `metrics.planner_iterations`
- `metrics.phase_counts`
- `metrics.mcp_calls_by_phase`
- `outcome` (response, unparseable, infrastructure-error)

## Verbose Trace Events

The `MLLD_TRACE=verbose` trace file is the most powerful debugging tool in this repo. Key event categories:

- `category: "guard"` — guard chain decisions on every dispatched operation. Look for `guard.deny` events.
- `category: "auth"` — authorization checks. Note: `auth.deny` events are sometimes cosmetic when followed by `guard.allow`. The real signal is the `guard.evaluate decision: "deny"` from a specific named guard.
- `category: "policy"` — `policy.build`, `policy.compile_drop` (when entries are silently dropped from the bucketed intent), `policy.compile_repair`
- `category: "shelf"` — shelf reads, writes, stale_read events
- `category: "handle"` — handle.issued, handle.resolved, handle.released, handle.resolve_failed
- `category: "llm"` — llm.call (start, finish, ok/error, duration), llm.tool_call, llm.tool_result

Filtering tips:
- Find all real denies: `jq -c 'select(.event == "guard.deny")'`
- Find which guard fired the deny: filter by `.data.guard`
- Find the surrounding scope: `.scope.exe` or `.scope.operation`
- Find policy compilation issues: `jq -c 'select(.event == "policy.compile_drop")'`

## Failure Classification Heuristics

### Runtime Bug (rare, escalate to mlld)

Suspect runtime when:
- The trace shows a guard denying an operation that should be exempt (substrate operations like @claude / claudeResume / cmd:env in pipelines)
- A value's wrapper shape isn't recognized by a runtime consumer (basePolicy resolver, shelf.read, policy.build) — the same data works in some contexts and not others
- Field access through parameter binding produces a different shape than direct access
- The error message includes "BoundaryViolation" or "must be a shelf slot reference" or "must be a tool collection"

When you suspect runtime:
1. Build a minimal reproduction outside the benchmark (see Minimal Repro Method below)
2. Use mlld-native value inspection (`.mx.labels`, `.mx.type`, `.mx.factsources`) — NEVER use JS to inspect mlld values, JS auto-unwraps and strips wrapper metadata. `| @pretty` is fine for visual inspection but remember it produces a STRING with no `.mx` accessor — see "Serialization is a one-way trip" below
3. File a focused ticket in `/Users/adam/mlld/mlld/.tickets/` with:
   - Exact repro command
   - Exact observed output
   - Expected behavior
   - Trace event sequence showing where it diverges
4. Tag P0 if it blocks rig integration; P1 if it's an API improvement

### Rig Framework Bug

Suspect rig framework when:
- The error references a line in `~/mlld/rig/orchestration.mld` or another rig file
- The dispatcher's contract with the planner is mismatched (planner emits one shape, dispatcher expects another)
- A let-binding or parameter pass loses metadata
- Shelf access works in one dispatcher context but not another

Typical fixes:
- Update the dispatcher to handle the actual planner output shape
- Add a guard or schema validator that catches the malformed input
- File a ticket in `~/mlld/benchmarks/.tickets/` with `phase-d1` tag

### Planning Failure (LLM-quality)

Suspect planning when:
- The task clearly needs read tools that never appear in the trace
- The planner chooses the wrong write path
- The planner widens into unrelated tools
- The planner omits an obvious follow-up step
- The planner returns `worker: "blocked"` after attempting a resolve, with reasoning that misclassifies a defended rule

Typical fixes:
- Schema-level constraint in `~/mlld/rig/guards.mld` (b-d394 pattern)
- Planner prompt clarification — general behavioral rule, NOT task-shaped examples
- Compare the same task on a second model only after the trace suggests the planner is the live variable
- Consider whether the constraint should be moved into deterministic code instead of prompt discipline

Avoid:
- Task-id-specific prompt examples
- "If task contains X, do Y" rules

### State Persistence Failure Across Tool Calls

Suspect state not surviving between planner tool invocations when:
- Resolve succeeded (tool result shows handles), but the next extract/execute can't find the resolved handle
- Budget counters appear to reset between tool calls
- The wrapper receives the wrong object for `state` or `query` (aliased to `agent` or null)

This is the single-planner equivalent of the old "context handoff" failure. In the persistent model, state is mutated inside each tool wrapper and must be visible to the next wrapper in the same session.

Typical fixes:
- Verify the shelf/state write was actually applied (check audit trail for successful write events)
- Verify the next wrapper reads from the rig state object, not from the agent config object (the m-5683 aliasing bug family)
- Check whether the MCP tool callback path is re-materializing captured variables incorrectly between invocations
- If state is fine but the planner is referencing a handle that doesn't exist, check whether the resolve wrapper returned the handle in its attestation — the planner can only reference handles it saw in tool results

### Execution Failure

Suspect execution failure when:
- Planner authorized the right tool
- @policy.build returned valid:true
- But the worker called the tool with wrong args (wrong recipient, wrong amount, wrong shape)

Typical fixes:
- Tighter contract pinning at extract phase
- Worker prompt clarification about handle pass-through
- Check whether the worker is paraphrasing values instead of using literals from input

### Final Answer / Host Parsing Failure

Suspect response-shape issues when:
- The write succeeded
- But utility is false because the answer is malformed, noisy, or `unparseable`
- Or the host reports `outcome: unparseable`

Typical fixes:
- Verify the agent file's final return clause is `=> { content: @result.final.text }`
- Check that no `show` / `output` directives compete with the JSON return
- Verify compose phase is actually running (not falling through to a generic fallback)

## Minimal Repro Method

This is one of the highest-leverage debugging techniques in this repo.

When a failure might involve a lossy boundary, do not keep guessing inside full benchmark runs. Build a small reproduction in `~/mlld/benchmarks/tmp/` (or `~/mlld/rig/spike/NN-<topic>/` for permanent regression guards) that mirrors only the relevant chain and prints the value at each boundary.

The goal is to answer a concrete question like:

- did the planner emit a valid bucketed intent?
- did `@policy.build` produce a valid policy fragment?
- did the runtime preserve the basePolicy rules through the merge?
- did `@shelf.read` recognize the slot ref shape?
- did substrate exemption fire on the guard for this operation?

Build the repro incrementally:

1. Start with local synthetic exes / fake fetch tools, not the full benchmark harness
2. Mirror the exact display shape that matters
3. Mirror the exact helper / wrapper chain that matters
4. Print every intermediate object using mlld-native `.mx` accessors. `| @pretty` is OK for visual inspection but it strips metadata — never use it as part of the chain you're testing, only as a debug print at the boundaries
5. NEVER use JS to inspect mlld values — JS auto-unwraps and strips wrapper metadata that runtime consumers actually check
6. Only after that works, add one more layer of realism

A useful pattern from this repo's history: `~/mlld/benchmarks/tmp/probe-d57b/` contains 10+ variants of @rigBuild + @dispatch shapes used to isolate the m-d57b boundary bug. The probe runs in <2 seconds with no real LLM calls. It became the canonical repro that GPT used to land the runtime fix.

What good repros look like:
- They isolate one boundary class
- They use the smallest possible tool surface
- They print intermediate state via mlld-native accessors
- They avoid benchmark-only MCP dependencies when possible
- They compare working vs failing variants side by side
- They run in <10 seconds with no real LLM cost

What to avoid:
- Writing a "minimal repro" that still depends on the full benchmark harness
- Using JS blocks to inspect mlld value shapes (`exe @inspect(v) = js {...}` strips the wrapper metadata you actually need)
- Changing prompts first and only then trying to understand the boundary
- Filing a runtime bug without a concrete local reproduction

If the minimal repro passes but the benchmark still fails, that is valuable information. It means the remaining problem is in whatever extra layer the repro did not yet include.

## Policy / Intent Boundary Probes

Policy failures need a boundary-by-boundary probe, not just one isolated `@policy.build` call. The same printed JSON can behave differently after a rebind, merge, or role change because wrapper/proof metadata can be lost while the visible data stays identical.

When debugging execute authorization, print this matrix before changing runtime code:

- `@compiled.compiled_args`
- `@compiled.policy_intent`
- per `@compiled.compiled_entries`: `arg`, `role`, `source_class`, `auth_bucket`, `flat_eq`, `flat_attestations.length`
- tool-derived surfaces: `@toolControlArgs(@compiled.tool)`, `@toolPayloadArgs(@compiled.tool)`, `@toolUpdateArgs(@compiled.tool)`, `@toolExactArgs(@compiled.tool)`
- the exact `@built.issues`, not just `valid`
- `@built.report.strippedArgs`, `repairedArgs`, and `droppedEntries`

Run policy-build probes in the same role/context as dispatch. A top-level `@policy.build(...)` result can be misleading when the live path calls it inside `exe role:planner`. Prefer:

```mlld
exe role:planner @probePolicyBuild() = [
  let @compiled = @compileExecuteIntent(@state, @tools, @decision, @query)
  let @built = @policy.build(@compiled.policy_intent, @tools, {
    task: @query,
    basePolicy: @agent.basePolicy
  })
  => {
    policy_intent: @compiled.policy_intent,
    valid: @built.valid,
    issues: @built.issues,
    report: @built.report
  }
]
```

For `updateArgs` failures, the key question is not "did `compiled_args` contain the update value?" It is "did the intent handed to `@policy.build` contain at least one declared update field?" The runtime checks update-field presence in the raw intent before stripping payload/update args from the final policy. A good result looks like:

- `policy_intent.<tool>.<control_arg>` has an attested constraint
- `policy_intent.<tool>.<update_arg>` has the raw update value
- `@policy.build` returns `valid: true`
- `@built.report.strippedArgs` includes the update arg

If an intermediate helper returns `null` to mean "no constraint", compare with `!= null` before accepting it. In mlld, a local variable whose value is `null` may still satisfy `.isDefined()`, so `@constraint.isDefined()` can accidentally treat "no constraint" as present and drop the fallback value.

## Native mlld value inspection

When you need to know what shape a value has, use mlld-native accessors:

```mlld
show "type:"
show @typeof(@value)
show "wrapper type:"
show @value.mx.type
show "labels:"
show @value.mx.labels
show "factsources:"
show @value.mx.factsources
show "sources:"
show @value.mx.sources
show "pretty (debug-only — see warning below):"
show @value | @pretty
```

The `.mx.*` namespace exposes the StructuredValue wrapper metadata that runtime consumers actually check. JS auto-unwraps everything to plain data — useful for "is the underlying data correct?" questions but useless for "is the wrapper recognizable to consumer X?" questions.

Common diagnostic pattern: compare two shapes side by side.

```mlld
let @direct = @agent.basePolicy
let @spread = { ...@agent.basePolicy }
show "direct labels:"
show @direct.mx.labels
show "spread labels:"
show @spread.mx.labels
```

If they differ, the wrapper preservation is dropping something across the boundary.

## Serialization is a one-way trip — never use `| @pretty` or JSON parse for prompt assembly

`| @pretty` and JSON serialization in general are **debug-inspection accessors only**. They are NOT prompt-assembly tools. The moment a fact-bearing value passes through `| @pretty` (or any other JSON serialization), it becomes a flat JSON string. JSON has no slot for `.mx` wrapper metadata — no labels, no factsources, no taint marks, no display projections, no handles. Everything that the security model uses to ground a value is stripped at this boundary. Once stripped, it cannot be recovered: the resulting string is just text.

The same is true in the other direction. Any value produced by `@parse` (or any JSON-parsing path, including the planner's JSON output reaching `@policy.build`) is a fresh primitive with **zero factsources, zero labels, zero proof**. The parsed value looks identical to the original (`"abc123"` is `"abc123"`) but the runtime treats it as untrusted, proofless, and unlabeled. The proof claims registry can sometimes recover proof for the value via value-keyed lookup (`known` bucket auto-upgrade — see b-6ea2 SCIENCE.md), but only if the same value was previously coerced through a `=> record` somewhere.

This boundary is the most common proof-loss vector after JS interop. Watch for it.

### What this looks like in code

**Wrong** — strips display projection and turns shelf state into raw JSON the planner has to navigate without help:

```mlld
let @shelfStateText = @shelfState | @pretty       >> ✗ destroys handles, masks, omissions
=> @template(@query, ..., @shelfStateText)
```

This is the bug at `~/mlld/rig/workers/planner.mld:73-76` that motivated b-a629. The planner sees a flat JSON dump of shelf state — no `display.planner` projection, no minted handles, no field omission. It then has no choice but to fabricate handle strings or pick wrong fields. The display projection layer is bypassed entirely.

**Right** — interpolate via `@fyi.shelf.<alias>` inside a box scope, where display projection IS applied and handles ARE minted in the calling box's mint table:

```mlld
box @plannerBox with { shelf: { read: [@s.trusted_thing as trusted] } } [
  => @claude(@plannerPrompt, { tools: @plannerTools })
  >> The prompt template uses @fyi.shelf.trusted; projection runs
  >> at template-render time, handles are minted in this box's
  >> bridge mint table, the planner sees real handle-bearing values.
]
```

(b-a629 tracks the rig-side fix.)

### Why this matters for diagnosis

If you're debugging a "the planner can't find a handle" symptom, the first question is: **how does shelf state reach the planner's prompt?** If the answer is "via `| @pretty`," you've found the bug — there are no handles to find because they were never rendered. Don't go looking for runtime gaps in handle minting; the gap is at the prompt-assembly boundary.

**Diagnostic check** in any new probe: print the value before serialization AND after. The before-form has `.mx.factsources`. The after-form is a string with no `.mx` accessor at all. The contrast is the proof-loss point.

```mlld
show "before serialize:"
show @value.mx.factsources              >> [{ kind: "record-field", ... }]
let @serialized = @value | @pretty
show "after serialize (no .mx anymore):"
show @typeof(@serialized)               >> "string"
>> @serialized.mx.factsources           >> would error: cannot access mx on string
```

This is the same lesson the JS interop section makes for `js {}` boundaries. JSON serialization is the OTHER lossy boundary, equally common and easier to miss because it looks like benign formatting.

### The general principle

| Operation | Preserves `.mx`? | Preserves factsources? | Safe for prompt assembly with metadata? |
|---|:---:|:---:|:---:|
| Direct field access (`@x.field`) | ✓ | ✓ | ✓ |
| `let @y = @x` assignment | ✓ | ✓ | ✓ |
| `@fyi.shelf.<alias>` interpolation in template | ✓ | ✓ | ✓ (projection applied at LLM bridge) |
| Tool result returned from `@claude` call | ✓ (display projection applied) | ✓ | ✓ (handles minted in this call's scope) |
| `| @pretty` | ✗ | ✗ | ✗ — debug only |
| `| @parse` (or any `JSON.parse` path) | ✗ | ✗ | ✗ — fresh primitives, no proof |
| `js {}` block params (without `.keep`) | ✗ | ✗ | ✗ — JS auto-unwrap |
| Object spread `{ ...@x }` | ✗ | ✗ | ✗ — materializes plain data |
| Bare value pasted into a `cmd { }` block | becomes a string | ✗ | ✗ — string interpolation |

If you need a value to carry its proof across a boundary, the boundary must be in the left column. If you need to inspect it for debugging, the right column is fine. **Never confuse the two.**

## Architecture Overview

The clean rig runs as a **single persistent planner LLM session** per task. The planner calls rig-owned tools naturally via provider tool-use protocol. There is no outer iteration loop, no per-turn prompt reconstruction, and no planner resume. See `SINGLE-PLANNER.md` for the full design.

### Layers

1. **Python host (`src/host.py`, `src/run.py`, `src/mcp_server.py`)** — minimal. Builds per-task MCP server, calls the mlld agent entrypoint, parses stdout, formats results for AgentDojo.

2. **Per-suite agent file (`bench/agents/<suite>.mld`)** — ~30-50 LOC. Imports rig framework + per-suite domain content, builds the agent via `@rig.build`, runs it via `@rig.run`, returns `{ content: <text> }`.

3. **Per-suite domain content (`bench/domains/<suite>/`)**:
   - `records.mld` — Record types with facts/data/display modes (role:planner / role:worker projections)
   - `tools.mld` — `var tools` catalog with input records, labels, `can_authorize`, `description`, `instructions`
   - `bridge.mld` — MCP bridge helpers (date normalization, string coercion)

4. **Rig framework (`rig/`)** — Single persistent planner with rig-owned tool wrappers:
   - `index.mld` — `@rig.build` entry point, agent handle assembly
   - `orchestration.mld` — Single-session runner: initialize state, invoke one planner call with tools, return terminal result
   - `workers/planner.mld` — Planner prompt builder, planner tool surface builder, one persistent `@llmCall`
   - `workers/resolve.mld`, `extract.mld`, `derive.mld`, `execute.mld`, `compose.mld` — Phase worker implementations (called by planner tool wrappers, not by an outer loop)
   - `runtime.mld` — State helpers, display projection, session management
   - `tooling.mld` — Catalog helpers, policy synthesis
   - `intent.mld` — Authorization intent compilation
   - `prompts/` — `.att` template files

5. **mlld runtime (`~/mlld/mlld/`)** — Owns label propagation, structuredvalue boundaries, policy compilation, factsources, handle resolution, guard chain execution, MCP tool dispatch.

### The planner tool surface

The planner sees exactly six rig-owned tools:

| Tool | Purpose | Return contract |
|---|---|---|
| `resolve` | Ground entities via read tools | `=> record` with `role:planner` projection, or `->` attestation |
| `extract` | Read content from resolved sources | `->` attestation only |
| `derive` | Transform/select from extracted data | `->` attestation only |
| `execute` | One concrete write under compiled auth | `->` attestation only |
| `compose` | Final user-facing answer (terminal) | `->` terminal attestation |
| `blocked` | Terminal failure (terminal) | `->` terminal attestation |

The planner never gets direct access to suite/domain tools. The wrappers ARE the security boundary — guards, policy compilation, display projection, attestation shaping, lifecycle emission, and state mutation all happen inside the wrappers.

When debugging, identify which layer the issue lives in BEFORE making changes. Layer 5 fixes go in `~/mlld/mlld/.tickets/`. Layers 2-4 fixes go in `clean/.tickets/` or are tracked via `tk` in the clean repo.

## Current High-Value Generalizable Frontiers

These are the main classes worth working on now (post-single-planner architecture):

### 1. Planner Tool-Call Discipline

The default dev model is `openrouter/z-ai/glm-5.1`. Treat planner tool-call mistakes as prompt/wrapper issues first, not as model-quality problems.

In the persistent model, the planner learns from tool errors in-session. Wrapper error messages are the primary teaching mechanism:

- Planner calls `execute` without first resolving the target → wrapper returns structured error guiding it to call `resolve` first
- Planner calls `blocked` prematurely → wrapper returns error with "you haven't attempted resolve yet"
- Planner tries to derive recipient emails from names instead of grounding contacts → intent compiler rejects with `payload_only_source_in_control_arg`
- Planner burns error budget → terminal failure with the accumulated error history

The key discipline: wrapper error messages should be actionable instructions, not generic "invalid input" strings. The planner's only teacher is the tool results it receives.

### 2. Attestation Shape Tuning

Each wrapper's `->` return shapes what the planner knows after each tool call. Too little information and the planner can't make good next-step decisions. Too much and the planner sees content it shouldn't.

The right balance per tool:
- `resolve`: handles + record metadata (name, key fields) — enough for the planner to reference results in extract/execute calls
- `extract`: schema name + field list + provenance — enough for the planner to know what was extracted without seeing the content
- `derive`: same shape as extract — what was derived, not the values
- `execute`: status + tool name + result handles — enough to confirm the write happened

### 3. Compose Phase Separation

The compose phase has no tools and emits only natural-language text. The planner must call `compose` as a terminal tool and then emit its final text response. No other tool should produce user-facing output.

### 4. MCP Tool Callback State Integrity

The persistent planner's tool wrappers run as MCP tool callbacks. State must survive correctly across invocations. Known bug families:
- Variable aliasing across callbacks (m-5683: `state` and `query` aliasing to `agent` on second call)
- StructuredValue wrapper stripping through let-bindings (m-2f36 family)
- Environment serialization in debug/audit paths (m-0ea4)

When you find a new state-integrity gap, file it as a focused ticket in `~/mlld/mlld/.tickets/`. Do not add rig-side workarounds.

## Guidance on Prompt Editing

Prompt edits are allowed, but follow these rules:

- Prefer general behavioral rules over benchmark examples
- Prefer one good structural rule over three task-shaped reminders
- If a prompt fix only helps one task and cannot be defended as a general agent rule, do not land it
- If a prompt fix is compensating for something code should decide deterministically, move it into code instead

Good prompt rule:
- "If a task references an existing scheduled payment but no concrete change is grounded, inspect and report rather than modify."

Bad prompt rule:
- "For task phrased like X, choose transaction id 7."

Good schema constraint:
- A wrapper error message that catches the failure pattern and returns actionable structured guidance in the tool result.

## Guidance on Security Work

When investigating security:
- Keep the planner clean — it should run on uninfluenced user task text only, never on tainted tool results
- Keep untrusted content out of planner authorization intent
- Let the runtime own proof, handles, and authorizations via `@policy.build` and `@policy.validate`
- Use bucketed intent (`resolved` / `known` / `allow`) — never hand-roll constraints
- Verify defenses by integration test, not by inspection

Do not hand-roll authorization semantics in benchmark JS unless you have no runtime alternative.

## Guidance on Writing Up Runtime Gaps

When you find a likely mlld runtime gap:

1. Confirm it is not just rig framework misuse or benchmark misuse
2. Build a minimal local reproduction in `~/mlld/benchmarks/tmp/probe-<topic>/`
3. Use mlld-native value inspection (NOT JS) to identify the wrapper shape that diverges
4. Write a focused ticket in `~/mlld/mlld/.tickets/` via `cd ~/mlld/mlld && tk create ...`
5. Keep the report concrete:
   - Exact input shape
   - Exact observed output (with trace events)
   - Expected behavior
   - Reference paths in the runtime source code if you can locate the relevant function
   - Suggested fix direction (one or two options, not exhaustive)
6. Tag P0 if it blocks rig integration; P1 for API improvements; P2 for nice-to-haves

Do not send vague "policy builder seems broken" reports.

## Recommended Working Loop

Use this loop:

1. Pick one failing task with a representative failure class
2. Reproduce it locally with `MLLD_TRACE=verbose MLLD_TRACE_FILE=tmp/<task>.jsonl` (do NOT use `--debug` — see warning above)
3. Read the JSONL row carefully — `mcp_calls`, `final_output`, `execute_error`, `metrics`
4. Filter the trace for `guard.deny`, `policy.compile_drop`, and `llm.call ok:false`
5. Decide whether it is:
   - runtime / boundary
   - rig framework dispatcher
   - planner-quality
   - LLM-side execution
   - host parsing
6. **Ask: "what specific design or contract question does this failure expose?"** If the answer can be tested with synthetic data, write a probe in `tmp/probe-<topic>/` BEFORE making any code change. Use `tmp/probe-cross-phase-bucket/` as the template — it answered a structural-looking question with a 7-row matrix in seconds, no LLM cost.
7. Make ONE generalizable change informed by the probe's matrix (new schema constraint, dispatcher fix, runtime ticket, planner prompt clarification)
8. Re-run the SAME task
9. If fixed, re-run one nearby task in the same class (3-task max)
10. Only after a small class improves, run a larger checkpoint
11. If a runtime fix from `~/mlld/mlld` landed since your last sweep, run the b-fefe smoke harness (when it exists) BEFORE the sweep — untested runtime fixes cause regressions that look like model failures.

## Cost Discipline

Per CLAUDE.md: **Default model is `openrouter/z-ai/glm-5.1`** for per-port iteration. Use a comparison model only after the default path is behaving cleanly.

LLM calls are expensive. Full-suite runs should come after exhausting clear local fixes.

Use:
- Single-task runs during iteration
- Parallel runs (`-p N`) when you need multiple tasks for a class verification
- Spike-based regression guards (no real LLM) for framework correctness checks
- `mlld validate` for syntax / contract changes (no LLM cost)

## Current Working Conclusion

The main risk right now is not "the model can't do it."

The main risk is that agents debugging this repo will:

- **use sonnet 4 sweeps to ask spike-shaped questions** (the most expensive failure mode in this repo)
- **pipe shelf state through `| @pretty` into prompts** and wonder why handles are missing
- **trust JSON-parsed values as if they carry proof** (they don't — JSON parse strips everything)
- overfit prompts to the benchmark
- misclassify rig framework or runtime bugs as model weakness
- chase prompt fixes when the constraint should be in code
- skip the minimal-repro discipline and burn cycles on hypothesis-driven debugging
- try to inspect mlld values via JS instead of mlld-native accessors
- skip the rig smoke check on runtime patches and discover the regression by accident in the next sweep

Do not do that.

Prioritize structural rig framework + runtime correctness first. **Spike before sweep, every time.** Once the framework path is clean, planner prompt iteration and model selection become measurable concerns, not confounders.

## Lessons from the prompt/error audit (session 3)

These are hard-won lessons from the c-pe00 through c-pe08 prompt audit work. They apply to all suites.

### Worker test infrastructure catches real gaps

`rig/tests/workers/` contains 17 isolated LLM tests for extract/derive/compose workers. Each test calls one worker prompt directly with synthetic data — no planner, no MCP, no bench host. Runs in ~50s total. Use these BEFORE and AFTER any prompt change to catch regressions and measure improvement.

```bash
mlld rig/tests/workers/run.mld --no-checkpoint
mlld rig/tests/workers/run.mld --no-checkpoint --model claude-haiku-4-5-20251001
```

Results append to `rig/tests/workers/scoreboard.jsonl`. When the tests pass too easily, the assertions are too weak — the session 3 audit found 17/17 passing on the initial run because the test inputs were short and unambiguous. Hardened tests with realistic multi-paragraph sources and edge cases brought the baseline to 14/17, giving the prompt changes something to actually fix.

### Never use `show` inside exe functions during bench runs

`show` writes to stdout. The bench host reads stdout for the JSON result. `show` inside any exe that runs during a task corrupts the host's output parsing. The task "fails" even though the agent did the right work.

Use `log` instead — it goes to stderr. Or use `MLLD_TRACE` with a trace file. `show` is safe in standalone spike scripts and test files but never in bench-adjacent code.

### Field renaming across the MCP boundary destroys metadata

The c-ac6f attempt to rename `id_` → `file_id` in the file_entry record broke all file tasks (8 regressions). Both JS-based and mlld-native field remapping approaches failed because building a new object from field accesses strips StructuredValue metadata. The original `id_` field name works correctly — the intent compiler maps the planner's arg key (`file_id`) to the resolved value (from the `id_` field) without needing the names to match.

The lesson: do not rename record fields to match MCP parameter names. The intent compiler handles the mapping. If the planner is confused about which field name to use, fix the error messages or tool descriptions, not the record schema.

### The planner doesn't understand that compose reads state

The planner sees `preview_fields: ["appointment_count", "summary"]` after a successful derive but cannot see the actual values. Without explicit guidance, it re-derives repeatedly trying to "see" the values. The fix was one sentence in planner.att:

> After extract or derive succeeds, the results are stored in state. You will see field names (preview_fields) but not the actual values — that is expected. Call compose to render the final answer; the compose worker reads the full state including all extracted and derived values. Do not re-derive trying to "see" the values.

This fixed UT1 (previously a consistent regression). When investigating an over-derive loop, check whether this guidance is reaching the planner before looking for deeper issues.

### Suite addendums are the right place for domain workflow patterns

Travel's Pattern C (resolve loop) was the dominant failure mode. Adding a suite addendum that documents the family→metadata→derive workflow is the correct fix — not adding travel-specific rules to the rig planner prompt. The rule from CLAUDE.md: "Would this be true in a completely different domain?" If yes → rig. If no → suite addendum.

## See Also

- `CLAUDE.md` for the cardinal rules and project layout
- `SINGLE-PLANNER.md` for the persistent planner architecture and remaining work
- `STATUS.md` for current project status and what's verified green
- `~/mlld/benchmarks/labels-policies-guards.md` for the security model narrative
- `~/mlld/mlld/spec-input-records-and-tool-catalog.md` for the input-record / tool-catalog spec
- `~/mlld/mlld/docs/dev/DATA.md` for the structured-value boundary helpers and serialization rules
- `~/mlld/mlld/.tickets/` for active and recent mlld runtime tickets via `tk` CLI
- `~/.local/share/opencode/` for opencode session data, logs, and per-tool-call part storage
