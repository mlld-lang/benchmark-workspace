---
description: Fan out subagents to diagnose failing tasks from a recent bench run, with transcript-grounded citations
argument-hint: <suite> [tasks=all] [source=latest|local|<run-id>] [model=sonnet]
---

# /diagnose — Parallel transcript-grounded failure diagnosis

Args: `$ARGUMENTS`

Positional: `<suite>` (workspace|banking|slack|travel) `[tasks]` (`all` or `user_task_N,user_task_M,...`) `[source]` (`latest` | `local` | `<run-id>`) `[model]` (default `sonnet`).

This command fans out one subagent per failing task to read its opencode transcript, apply the DEBUG.md A–E triage, and return a 100–200 word diagnosis with 3–5 specific citations (part_id or sqlite WHERE-clause + brief excerpt). The main agent collates results into a per-task table and a cluster section grouping shared root causes.

## Step 1 — Resolve source and list failures

Parse `$ARGUMENTS`. Defaults: `tasks=all`, `source=latest`, `model=sonnet`. Refuse to proceed without a suite.

```bash
# Resolve OPENCODE_HOME and JSONL_PATH:
case "$SOURCE" in
  local)
    OPENCODE_HOME="$HOME/.local/share/opencode"
    # local jsonl lives in bench/results/<provider>/<model>/<suite>/defended.jsonl — find newest:
    JSONL_PATH=$(ls -t /Users/adam/mlld/clean/bench/results/*/*/$SUITE/defended.jsonl 2>/dev/null | head -1)
    RUN_LABEL="local"
    ;;
  latest)
    # newest cloud run dir whose manifest.suite matches:
    RUN_ID=$(for m in $(ls -t /Users/adam/mlld/clean/runs/*/manifest.json); do
      jq -re --arg s "$SUITE" 'select(.suite == $s) | .run_id' "$m" && break
    done | head -1)
    [ -z "$RUN_ID" ] && { echo "no run found for suite=$SUITE"; exit 1; }
    OPENCODE_HOME="/Users/adam/mlld/clean/runs/$RUN_ID/opencode"
    JSONL_PATH=$(find /Users/adam/mlld/clean/runs/$RUN_ID/results -name 'defended.jsonl' | head -1)
    RUN_LABEL="$RUN_ID"
    ;;
  *)
    RUN_ID="$SOURCE"
    OPENCODE_HOME="/Users/adam/mlld/clean/runs/$RUN_ID/opencode"
    JSONL_PATH=$(find /Users/adam/mlld/clean/runs/$RUN_ID/results -name 'defended.jsonl' | head -1)
    RUN_LABEL="$RUN_ID"
    ;;
esac
```

Verify `$OPENCODE_HOME/opencode.db` and `$JSONL_PATH` exist. Print the resolved run label + paths so the user can sanity-check.

Then list failures (utility=false), filtered by the task spec:

```bash
# All failures:
jq -c 'select(.utility == false) | {task_id, query, outcome, mcp_calls, policy_denials, execute_error, metrics: {planner_iterations: .metrics.planner_iterations, phase_counts: .metrics.phase_counts, mcp_calls_by_phase: .metrics.mcp_calls_by_phase, mcp_tools_by_phase: .metrics.mcp_tools_by_phase}, final_output}' "$JSONL_PATH"
```

For a specific task list (`user_task_8,user_task_32`): pipe through `jq -c --argjson ids '["user_task_8","user_task_32"]' 'select(.task_id as $t | $ids | index($t))'` after the utility filter.

If zero failures, report that and stop.

## Step 2 — Dispatch one subagent per failure (PARALLEL, single message)

For each failure row, spawn an `Explore` subagent. **Send all subagent calls in a SINGLE assistant message so they run concurrently.** Cap at ~10 in parallel — if there are more failures, do batches of 10.

Each subagent prompt MUST include:

1. **Frame** (verbatim block):

   > You are diagnosing a failed AgentDojo benchmark task. Apply the DEBUG.md triage discipline:
   > - **No model blame.** Same model has hit 80%+ on these suites before; if utility is bad, prompts/framework/runtime are the variables. (Cardinal Rule C/D.)
   > - **Transcript-grounded.** Every claim about *why* the planner did something must cite a specific part_id or sqlite query showing the planner's reasoning text. MCP-call sequences alone are insufficient — they show *what*, not *why*. Mark unverified hypotheses explicitly as `UNVERIFIED`.
   > - **Triage class A–E.** Pick exactly one: A=runtime/boundary, B=rig framework, C=planner-quality (prompt/discipline), D=worker-LLM execution, E=host/parsing. If multiple stacked, pick the *first* one that fired and note the others.

2. **Task context block**: suite, task_id, full query, outcome, execute_error (if any), policy_denials (the full list), mcp_calls (truncate to first 30 if longer), metrics summary (planner_iterations, phase_counts, mcp_calls_by_phase, mcp_tools_by_phase), and the first 800 chars of final_output.

3. **Self-locate the session** instructions:

   ```
   OPENCODE_HOME=<resolved path>
   DB="$OPENCODE_HOME/opencode.db"

   # Pick a distinctive phrase from the task query (>= 12 chars, avoid common words).
   # Example phrase for user_task_8: "channel starting with External"
   # Find sessions whose part data contains the phrase:
   sqlite3 -readonly "$DB" \
     "select distinct session_id from part where data like '%<phrase>%' limit 5"

   # Cross-check by inspecting each candidate's title and step-start count;
   # the right session is the one with planner-style tool calls and ~the metrics.planner_iterations from the result row.
   ```

   If multiple candidates, prefer the one whose part count roughly matches `metrics.planner_iterations × ~6` and whose title is plausibly task-related.

4. **Pull the transcript**:

   ```
   python3 /Users/adam/mlld/clean/src/opencode_debug.py --home "$OPENCODE_HOME" parts --session <SID> --limit 400
   ```

   For deeper reads of specific parts: `sqlite3 -readonly "$DB" "select id, substr(data,1,4000) from part where session_id='<SID>' and time_created between <a> and <b>"`. The transcript has reasoning, tool_use, tool_result, step-start parts interleaved — the `reasoning` parts are the gold for "why".

5. **What to look for** (steal from DEBUG.md):
   - Did the planner attempt resolve before extract/execute? Or did it derive what it should have resolved?
   - Did it call `blocked` prematurely after misreading a defense rule name?
   - Did it loop on resolves without making progress (Pattern C)?
   - Did the worker LLM call the tool with paraphrased values instead of handle pass-through?
   - Did extract emit the wrong contract fields?
   - Did compose wrap the answer correctly as `{ content: ... }`, or did the host fall back to `"Task completed."`?
   - For travel: are there `Not connected` / `Request timed out` errors? That's c-63fe (infrastructure), NOT a planning failure.
   - For "wrong date" suspicions: check `_patch_<suite>_utilities` in `src/date_shift.py` before accusing the planner of arithmetic.

6. **Required output shape** (the subagent returns this verbatim — do not editorialize):

   ```
   ### <task_id> — <triage class A–E>: <one-line failure shape>
   
   **Session:** ses_xxxx (<title>)  
   **Iterations:** <planner_iterations> · **Phases:** <phase_counts as compact one-liner>  
   **Verdict:** <100–200 words. What the planner tried, where it diverged from the right path, and the most likely root cause. Apply Cardinal Rule C — name the prompt/framework/runtime variable, not the model.>
   
   **Citations:**
   - `part:<id>` — <one-sentence excerpt or paraphrase showing the moment of divergence>
   - `denial:<rule>` — <which arg failed, on which tool>
   - `mcp[<n>]` — <tool, key arg, observed result>
   - … (3–5 total, prefer reasoning-part citations over raw tool calls)
   
   **Proposed next move:** <one of: (a) add prompt clarification at <layer> — text proposal, (b) write a $0 spike for <runtime/dispatcher question> per DEBUG.md "Spike First", (c) file ticket against <area> — minimal repro, (d) classify as OOS-EXHAUSTED/CANDIDATE/SHOULD-FAIL — reason. Per CLAUDE.md prompt-approval rule: do NOT propose task-id-shaped prompt edits or evaluator-shaped rules.>
   ```

   Cap response under 250 words. No preamble, no closing summary.

Set `subagent_type: "Explore"` and `description: "Diagnose <task_id> transcript"` for each.

## Step 3 — Collate

After all subagents return, assemble in this order, then stop:

1. **Header**: `## Diagnosis — <suite> · run <run_label> · <N> failing tasks`
2. **Per-task results** in suite order (concatenate the subagent outputs verbatim).
3. **Cluster section** — group tasks that share a root cause. Format:
   ```
   ## Clusters
   
   **<one-line cluster name>** — <task ids>  
   Shared signal: <what's common across their citations>. Suggested next move: <one action that would close the cluster>.
   ```
4. **Open ticket cross-reference** — for each task, `tk ls | grep "$task_id"` and surface the existing ticket id if present, or note "no open ticket — would file as `[<SUITE>-UT<N>] <one-line failure shape from above>`". Do NOT create tickets automatically.

Do NOT write to disk, do NOT update tickets, do NOT propose a sweep. The output is conversational. The user reads it and decides what to ticket / fix / spike.
