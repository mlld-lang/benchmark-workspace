# spec-rehearse — execute preflight (compile + advisory)

**Status:** draft for review (incorporates GPT feedback round 1)
**Owner:** Adam
**Related:** c-3438 (planner can't see structural impossibility), c-0589 (WS-UT8), c-b0a4 (TR-UT8), c-5929 (WS-UT33)

## Scope clarification (per GPT)

This is **execute preflight + advisory validation**, not a general "prevent wrong writes" mechanism.

- For source-class / field-path **compile failures**: the runtime already rejects before MCP dispatch. Rehearse helps these cases by saving planner iterations and giving better corrective feedback.
- For writes that **compile successfully but are semantically risky** (wrong recipient, unresolved template intent, ambiguous handle choice): rehearse only helps if we add advisory checks. Compile-only dry-run gives false confidence here.

The spec's scope is execute only — resolves/extracts/derives don't have the commit-precedes-verification problem because they don't have side effects.

## Problem

The planner has to author tool calls that satisfy the security model — correct source classes for control args, correct ref shapes, correct payload schemas. When it gets one wrong, the runtime rejects, but **the rejection comes after the LLM has already committed to a turn's worth of tokens, and after a write may have already fired.**

Two failure shapes recur from this:

1. **Self-correct-too-late on writes** (TR-UT8: title-template construction). Planner emits an execute, sees the result, recognizes its mistake, retries with a corrected version — but the wrong write already happened. The eval punishes the duplicate.
2. **Source-class fumbling** (WS-UT8: derived for control arg). Planner emits `{source: derived}` for an event_id arg, gets `payload_only_source_in_control_arg`, isn't sure how to fix, retries with another wrong shape, exhausts iteration budget.
3. **Wrong-recipient resolution** (UT33: "client" → wrong contact). Planner picks one of several plausible interpretations, calls the write tool, locks in. By the time it could have reconsidered, the write has happened.

In all three cases the planner is *capable* of getting it right — and often does, on retry. The failure is that **commitment precedes verification**. The planner has no way to test the shape of its plan before paying the side-effect cost.

## Proposal: a `rehearse_execute` tool

Add a new tool the planner can call before commit. Same arg shape as `execute`, no MCP dispatch, returns advisory feedback. The tool sits inside the existing execute phase rather than introducing a new phase (per GPT note: easier mental model than a parallel phase).

```
rehearse_execute(operation, args)
  → on compile success: {
      compiled: true,
      operation,
      normalized_args,                      // resolved refs flattened to concrete values
      proof_summary: { policy_pass, witnesses_attached },
      warnings: [<advisory checks the runtime can run cheaply>],
      rehearsal_token: <fingerprint(op, normalized_args, state_fingerprint)>
    }
  → on compile failure: {
      compiled: false,
      operation,
      issues: [{arg, error_code, message}],
      hints: [<concrete corrective guidance per issue>]
    }
```

**Important: NO `predicted_state_diff`** — that overpromises and is unknowable without the MCP call. We return what the runtime would dispatch (operation + normalized args + policy verdict), not what the world would look like after.

The planner can rehearse zero or more times before committing. Once satisfied, calls `execute`. The runtime guarantees rehearse has no MCP side effects.

### Rehearsal token

On success rehearse returns a `rehearsal_token` = fingerprint of `(operation, normalized_args, relevant_state_fingerprint)`. The planner can pass this to `execute` (optionally), and execute logs the match. This gives us:

- Audit trail of "rehearsed-then-committed" pairs for telemetry
- Detection of "rehearsed call A but committed call B" — divergence flag
- Future option: enforce rehearsal-required for high-risk write operations

Token is informational at first; enforcement is a later choice.

### Budget accounting (per GPT)

- Rehearsals count against planner LLM budget (they cost a turn) but do **not** count against "bad execute attempts" — they're cheaper feedback, intentionally
- Cap rehearsals-per-execute at e.g. 3 (configurable)
- Worker-test discipline: assert rehearse-before-execute on shaped scenarios where it should fire

## Why this is a useful skill, not just a debug surface

Teaching agents to **plan how to navigate security complexity** and **test the shape of their plan** is a generally valuable skill. The benchmark exposes the failure mode; the skill is portable to any agent system with non-trivial validation. Specifically:

- It separates **intent expression** from **commitment**. LLM tokens get spent on shape iteration in a sandboxed phase, not on uncommittable retries.
- It gives the planner an **explicit test surface** rather than asking it to be careful in one shot.
- It pairs with c-3438's "loud refusal" work: rehearse is the surface where richer hints land before the user sees a side-effect.
- It generalizes outside the benchmark: any defended-mode write benefits.

## How it differs from current intent_compile

The runtime already does intent_compile validation when execute is called. Today's behavior:

- `intent_compile` runs, returns ok/error
- on ok: dispatches to MCP, side-effect happens
- on error: surfaces error, no dispatch

`rehearse` separates the validation from the dispatch:

- Same intent_compile, but **always returns** without dispatching
- On success, returns *what* would be dispatched (predicted_state_diff)
- On failure, returns the same error shape but enriched with **hints** built from runtime state (resolved records in scope, candidate ref shapes, expected source classes)

The hint-generation work is c-3438. Rehearse is the **interface**.

## Implementation surface (per GPT)

`dispatchExecute` already separates `@compileExecuteIntent` from the MCP dispatch path in `rig/workers/execute.mld`. The right implementation is:

1. Factor a shared "prepare/compile execute" helper that runs intent_compile + collects normalized_args + proof_summary + advisory warnings
2. `rehearse_execute` calls the helper and returns
3. `execute` calls the same helper, then continues to `@callToolWithPolicy` for actual dispatch

This keeps the surface change small and ensures rehearse and execute see the same compile semantics. No new phase loop wiring needed; rehearse is just a sibling tool inside the execute phase namespace.

## Hint generation (the c-3438 hand-off)

The value of rehearse depends on hints being *useful*. For each error code, list what the runtime knows that would help:

| Error code | Runtime state available | Example hint |
|---|---|---|
| `payload_only_source_in_control_arg` | which arg, expected source classes, resolved records currently in scope | `"event_id requires resolved/known/selection. Resolved candidates: r_calendar_evt_3 (from search_calendar_events 'team meeting')."` |
| `known_value_not_in_task_text` | the value, the task text, similar resolved values | `"'Hawaii vacation' is not in the task text. r_file_entry_7 ('hawaii-itinerary.docx') is a resolved file_entry handle in scope; reference it as {source: resolved, record: file_entry, handle: r_file_entry_7}."` |
| `resolved_field_missing` | the requested field, fields that exist on the record | `"field 'recipient' not on contact record. Available facts: id_, email, name."` |
| `derived_field_missing` | the requested path, the actual derive output shape | `"path 'messages[0].body' not in derived 'messages'. Top-level shape: array of objects with [name, rank, message]. Try '0.message'."` |
| `template_arg_with_raw_field_ref` (new) | the user prompt's template literal, the arg name | `"Title template '{restaurant_name}' detected in user prompt. Construct the full title in a derive step before passing to title arg."` |

The "new" error code is the kind of advisory check rehearse can run cheaply that execute today doesn't bother with.

## Budget cost

| Item | Cost |
|---|---|
| Per rehearse call | one planner LLM round-trip + one intent_compile cycle |
| Compile cycle | ms-scale (no LLM, no MCP) |
| Iteration overhead per execute | typically 1-2 rehearses before commit |
| Per-task overhead | bounded; cap rehearse-per-execute at e.g. 3 |

Sessions today already do 8-10 planner iterations per task; adding 1-2 per execute is small relative to budget. The expected savings come from **fewer wrong-execute retries** (which already cost an iteration each) — this should be net-positive on most tasks.

## Risks

| Risk | Mitigation |
|---|---|
| Planner over-rehearses (5x before committing simple cases) | Cap rehearse-per-execute at 3; planner addendum: "rehearse for tasks with template literals or write tools you've not used in this session, otherwise commit directly" |
| Planner under-rehearses (skips rehearse on cases where it would help) | Worker test that asserts rehearse-before-execute on a TR-UT8-shaped scenario; addendum rule |
| Hint quality is poor | Iterate per error code; treat hint generation as c-3438 follow-on work |
| Rehearse becomes a new attack surface | Same source-class checks as execute; no MCP dispatch means no exfil; injected content still can't promote source class |

## Where compile rehearsal does NOT help (per GPT)

UT33-style **wrong-recipient** failures are not fixed by compile rehearsal alone. The planner's call compiles cleanly; the failure is semantic (chose the wrong contact). For those, rehearse needs **advisory ambiguity warnings**:

- `multiple_candidate_handles_match`: e.g., search_contacts_by_name returned 3 contacts, planner picked one — warn if there's no clear textual disambiguator in the user prompt
- `selected_handle_lacks_grounding`: warn if the chosen control-arg ref doesn't have direct textual grounding in the user task
- `template_arg_with_raw_field_ref`: warn if user prompt has a template literal but the planner is passing a raw field ref to a string arg

These are advisory checks layered on top of compile-only rehearsal. Each check is its own design decision; not all will land in Phase 1.

## Implementation phases

### Phase 0 (per GPT): enrich existing intent_compile hints first

**Before building rehearse**, do the cheaper experiment: enrich today's static `payload_only_source_in_control_arg` hint with `@state.resolved` candidates **at the existing rejection site** in `rig/intent.mld`. This requires no new tool, no new phase — just better error text. Re-run UT8 and see if the planner self-corrects on retry.

If yes: most of the value of rehearse for compile failures is captured without the new tool. Defer rehearse_execute.
If no: planner needs to *call into* validation, not just receive richer error text — proceed to Phase 1.

This is the empirical gate before committing to the new tool. ~1-2 hours of work plus a single live UT8 run.

**Caveats per GPT:**
- "~15 lines" estimate may be optimistic. Tricky parts: reliably mapping a failing control arg to its expected record type; formatting candidates without leaking hidden/untrusted fields. Hint should only show planner-safe handle labels/fields already legitimate in resolved state.
- Phase 0 success doesn't fully eliminate the case for rehearse_execute — better hints help only AFTER a failed execute attempt. Rehearse still matters for avoiding successful-but-wrong writes (TR-UT8 double-create). Phase 0 deferral is conditional, not permanent.

### Phase 1: zero-LLM probe (1-2 hours)

Goal: verify the runtime can dry-run intent_compile cleanly and that hints can be synthesized from existing state.

1. Take a known-bad execute intent (`event_id` with `{source: derived}`, from a real UT8 transcript)
2. Call intent_compile in dry-run mode (currently this means call it without dispatching; see how cleanly it separates)
3. Capture the rejection payload
4. Synthesize the richest hint message we can from runtime state (resolved records in scope, expected source classes, candidate refs)
5. Compare hint against what would have unstuck the actual session

Pass criteria: hint message would have plausibly led the planner to the correct ref shape on next emit.

### Phase 2: rehearse phase implementation (1-2 days)

1. New tool `rehearse_execute` registered alongside `execute`
2. Same intent_compile path, dispatch-suppressed
3. Return predicted_state_diff (use existing state-fingerprint infrastructure if available, or simple before/after diff snippet)
4. Hint generation per error code (start with 2-3 most common)
5. Worker test: assert rehearse output has correct shape on success and failure

### Phase 3: planner adoption (rolling)

1. Workspace + travel + slack planner addendums: rule for when to rehearse
2. Worker tests: assert rehearse-before-execute on shaped scenarios
3. Measure: UT8, TR-UT8, UT33 pass rates over 5 local reruns each
4. Iterate hint phrasing based on what actually unsticks the planner

## Open questions

1. Does the existing `intent.mld` separate intent_compile from MCP dispatch cleanly today? (Phase 1 answers this.)
2. Should rehearse return one hint per issue, or a synthesized "here's what to do next" message?
3. Should rehearse expose the planner to *which security rule* fired, or only *the corrective shape*? Per c-3438's principle: corrective shape only.
4. Is rehearse a single phase, or do we want `rehearse_resolve`, `rehearse_extract`, etc. for symmetry? (My read: only execute needs it; resolves/extracts/derives don't have the commit-precedes-verification problem because they don't have side effects.)

## Success criteria

- Phase 1 spike produces a hint string that would have unstuck a real UT8 session
- Phase 2 worker tests pass with rehearse correctly returning compile-success + compile-failure shapes
- Phase 3 ≥4/5 local UT8 / TR-UT8 reruns PASS
- No regressions on currently-passing tasks
