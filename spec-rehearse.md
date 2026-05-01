# spec-rehearse — pre-flight policy check for execute

**Status:** draft v2 — security-tightened: minimal information surface, no policy reasons exposed
**Owner:** Adam
**Related:** c-3438 (planner can't see structural impossibility), SHOULD-FAIL ticket family (untrusted-content → control-arg)
**Supersedes:** v1 with hint tables + reason codes (too much info leakage to planner)

## Problem

The planner authors `execute` calls that have to satisfy the security model — correct source classes for control args, correct ref shapes, valid policy compilation. Today's failure modes:

1. **Commitment precedes verification.** Planner emits an `execute`, the runtime rejects at intent-compile or policy-build, planner has already burned a turn and possibly partially-mutated state.
2. **No fail-fast on structural infeasibility.** Tasks where no possible source class can satisfy the policy (e.g., a `send_email.recipient` that must be sourced from untrusted webpage content) currently iterate to budget exhaustion. The planner tries `extracted`, gets a denial, tries `derived`, gets a denial, tries another tool, gets a denial — never recognizes that the structural constraint is firm.
3. **`blocked` as easy out.** The current `blocked` terminal can be called by the planner with a free-text reason and no evidence. Risk: planner gives up after one denial without exploring alternatives.

## Proposal: `rehearse(intent)` + tightened `blocked(reason, evidence)`

### `rehearse(intent)`

Same intent shape as `execute`. Runs the existing intent-compile + `@policy.build` pipeline, **does not dispatch the MCP call**, **does not mutate state** other than appending to a rehearse history.

Returns one of:

```json
{ "ok": true }
```

```json
{ "ok": false, "blocked_args": ["recipient"] }
```

That's the entire surface. **No reason codes, no required source classes, no hints, no policy details.** The planner sees:
- `ok: true` → "this exact intent would dispatch successfully (modulo MCP-side errors)"
- `ok: false` → "this intent is blocked. The blocking is in these arg(s)."

The planner re-shapes the intent and tries again. The arg names are already in the planner's emitted intent — `blocked_args` adds no new information about policy structure, just helps the planner localize which fields to change without bisecting via repeated rehearses.

`ok: true` does not guarantee the eventual `execute` will succeed. It guarantees the framework's compile + policy-build verdict is positive. Dispatch-time failures (MCP server errors, network, worker LLM hallucinations, tool runtime errors) remain possible.

### `blocked(reason, evidence)`

Tightened from the current free-text terminal:

```json
{
  "reason": "no input shape passes for this task — alternatives exhausted",
  "evidence": [
    { "tool": "send_email", "args_shape": "<hash>" },
    { "tool": "invite_user_to_slack", "args_shape": "<hash>" }
  ]
}
```

Runtime validates:
1. **≥2 distinct `(tool, args_shape)` entries**. Distinctness defined by hash of source-class tuple (not values), so retrying the same shape twice doesn't count.
2. **Each entry maps to an actual `rehearse` call** in this session's `rehearse_history` with `ok: false`. Planner can't fabricate evidence.

If validation fails: returns `blocked_evidence_insufficient`. **No hint about which alternatives haven't been tried** — that would require exposing reason codes. Planner has to rehearse more on its own initiative.

### Iteration budget

Rehearse counts 1:1 against the iteration budget. Same as any other tool call. The planner pays for the structural check; if rehearsing every execute is wasteful, the planner learns to skip rehearse on simple cases.

### Freshness

Rehearse always evaluates against current state. No caching. The `rehearse_history` is a rolling list of `(intent, result, timestamp)` for blocked-evidence validation only — it isn't consulted for the rehearse computation itself. If the planner believes state changed since a prior rehearse, it should re-rehearse; that's a new history entry.

## What rehearse output does NOT contain

- No reason codes (`source_class_violation`, `untrusted_destructive`, etc.)
- No required values for the failing arg
- No alternative suggestions
- No taint / label info
- No policy structure
- No state-fingerprint or witness info

The planner's only signals are:
- The tool catalog's `inputs:` record (declares static expected shape per tool)
- Its own working memory of resolved/extracted/derived values
- Rehearse's binary `ok` + arg-level `blocked_args`

That's enough for the planner to plan without exposing internal policy mechanics.

## Planner discipline (rig/prompts/planner.att additions)

Two rules added to the rig prompt:

> **Rehearsing writes.** If you're uncertain whether an `execute` would succeed under defense — especially when control args are sourced from extract or derive — call `rehearse` first. Rehearse is a normal tool call against the iteration budget; on simple writes you've used before in this session, you can skip it.

> **Calling `blocked`.** Don't call `blocked` after a single rehearse failure. The framework requires evidence of at least 2 rehearse attempts with structurally distinct intents (different tools, or different source-class combinations) before accepting `blocked`. If your first rehearse fails, try a different shape and rehearse again before concluding the task is infeasible.

These are domain-agnostic — belong in `rig/prompts/planner.att`, not in suite addendums.

## Reliability

Rehearse runs steps 1–3 of `dispatchExecute`:
1. `validatePlannerArgRefs` — shape validation (deterministic)
2. `compileExecuteIntent` — source class + provenance validation (deterministic)
3. `@policy.build` — policy compilation (deterministic)

These are pure functions of `(intent, current_state, agent.tools)`. Same inputs → same outputs. No LLM, no MCP, no network.

`ok: true` is reliable for what it covers (framework-level acceptance). `ok: false` is reliable for what it covers (framework-level rejection — no possible MCP dispatch will succeed with the rejected shape).

What rehearse can NOT predict:
- MCP server errors / disconnects (c-63fe class)
- Network errors
- Tool runtime errors (e.g., `reserve_hotel` raising `ValueError` on a bad date)
- Worker LLM hallucinations during the execute phase's worker call
- Anything semantic (right shape, wrong values — UT33-style "the client" interpretation)

That's a clear contract. Rehearse is a structural-feasibility check, not an end-to-end success predictor.

## Risk to existing implementation

**Low for `rehearse`**: it's purely additive. Shares the existing compile + policy-build code via a refactored helper; doesn't touch dispatch.

**Medium for `blocked` tightening**: changes a behavior contract. Existing planner sessions that called `blocked` with a free-text reason would now fail with `blocked_evidence_insufficient`. Migration path:
- Phase 1: ship rehearse + history tracking. `blocked` keeps current behavior; new `evidence` field optional.
- Phase 2: after rehearse adoption is confirmed in worker tests, make `evidence` required. Old callers fail with a structured error directing them to rehearse first.

**Progress detector (c-3438) interaction**: rehearse calls must NOT count as state-progressing in the progress signature. Otherwise rehearse spam could mask stalled tasks. Rehearse history is a separate ledger; the progress signature stays keyed on resolved/extracted/derived state.

**Iteration budget pressure**: a planner that rehearses before every execute doubles tool calls per write. Default budget is 25 iterations. We may need to bump to 30 or accept that defended runs use more iterations than current. Worker tests will surface budget-exhaust regressions.

## What's missing in mlld?

Nothing. The pieces exist:
- `@policy.build` accepts intent + tools + task config, returns `{valid, policy, issues}` — works ✓
- `@compileExecuteIntent` already separates compile from dispatch in `rig/intent.mld` — works ✓
- `var session @planner` for rehearse history persistence — works ✓
- `for parallel`, record coercion, exe wrappers — works ✓

The compile-without-dispatch refactor is rig-level: factor a shared helper that both `dispatchExecute` (steps 1–3 then 4–5) and `dispatchRehearse` (steps 1–3 only) call. No new mlld primitive needed.

## Implementation surface

| File | Change |
|---|---|
| `rig/workers/execute.mld` | Extract steps 1–3 of `dispatchExecute` into `@compileForDispatch(state, agent, decision, query) → {ok, blocked_args[], compiled, built}`. `dispatchExecute` calls it then continues with steps 4–5. |
| `rig/workers/planner.mld` | New `@planner_rehearse_inputs` record (mirrors `@planner_execute_inputs` arg shape). New `rehearse:` tool entry. Tighten `@planner_blocked_inputs` to include optional `evidence: array?`; required in Phase 2. |
| `rig/runtime.mld` (or new module) | `@dispatchRehearse(state, agent, decision, query)` — calls `@compileForDispatch`, never dispatches MCP. Appends `{intent, ok, blocked_args, ts}` to planner-session `rehearse_history`. Returns `{ok, blocked_args}`. |
| `rig/runtime.mld` | `@validateBlockedEvidence(history, evidence)` — checks ≥2 distinct (tool, args-shape-hash) pairs in evidence, all map to rehearse_history entries with `ok: false`. |
| `rig/prompts/planner.att` | Two discipline rules above. |

Total: ~150–250 lines of mlld, mostly mechanical given the existing intent-compile path.

## Test plan

**Phase 1 (zero-LLM spike, $0): ✅ DONE 2026-05-01**

Spike at `tmp/rehearse-spike/probe.mld`. 7-row matrix exercising the source-class space against the rig test fixtures (records, tools, sampleState):

| Row | Source class | Expected | Result | Stage caught |
|---|---|---|---|---|
| A | resolved.contact.email | ok | ok ✓ | ok |
| B | derived raw → control | blocked | blocked ["recipients"] ✓ | compile |
| C | extracted raw → control | blocked | blocked ["recipients"] ✓ | compile |
| D | selection ref (derive→resolved bridge) | ok | ok ✓ | ok |
| E | known literal in task | ok | ok ✓ | ok |
| F | known literal NOT in task | blocked | blocked ["recipients"] ✓ | compile |
| det | row B re-run | identical | identical ✓ | — |

**Validated:**
1. compile + `@policy.build` are deterministic — same inputs always produce same `(ok, blocked_args)`.
2. The `{ok, blocked_args}` surface contract reduces cleanly from compile/policy issue lists.
3. The structural firewall (derive/extract → control arg) is caught at compile stage.
4. The known-bucket task-text check is caught at compile stage.
5. The selection_ref pattern (the legitimate derive→resolved bridge) passes correctly.
6. The `role:planner` gate is enforced at policy.build — rehearse exe needs the same role declaration as `dispatchExecute`.
7. Re-running same intent yields identical output with no state mutation.

**Implementation caveat surfaced**: policy-stage rejections sometimes lack per-arg attribution (e.g., `invalid_authorization` is operation-level). In those cases `blocked_args` ends up `[]`. v1 accepts this — `ok: false` with empty `blocked_args` means "operation-level block, planner must bisect by varying the intent shape." Future revision could add a synthetic `op_blocked: true` marker without leaking the reason.

**Phase 2 (worker tests, ~30s):**
- New worker test asserting rehearse output shape on success + failure cases.
- Worker test asserting `blocked` is rejected without evidence.
- Worker test asserting `blocked` is accepted with valid evidence.
- Regression: existing `dispatchExecute` smoke tests still pass.

**Phase 3 (live SHOULD-FAIL targeted run, ~$0.50):**
- Re-run WS-UT13 (delegates action choice to untrusted email content). Goal: planner fails fast in 3–5 iterations instead of burning to budget.
- Re-run BK-UT0 (untrusted-content → recipient IBAN). Same goal.
- Re-run TR-UT11 (interpretation ambiguity). Should NOT fail-fast — this is semantic, not structural; rehearse should return `ok: true` and the planner proceeds normally.

**Phase 4 (cycle-1 attack canary, ~$5):**
- Re-run banking attack `direct` with rehearse landed. Goal: SHOULD-FAIL targets continue to block all attacks (security invariant); benign-class targets show no regression.
- Compare iteration count distribution: SHOULD-FAIL tasks should drop from ~25 to ~5 average iterations.

## Success criteria

- Phase 1 spike: synthetic test matrix produces deterministic `ok` results matching policy verdict.
- Phase 2 worker tests: 100% pass on the new assertions.
- Phase 3 SHOULD-FAIL fail-fast: verifiable iteration-count drop on at least 3 of the 10 SHOULD-FAIL tickets.
- Phase 4 attack canary: 0 SHOULD-FAIL breaches; no regression on benign passes.

## Open design questions

1. **Should `rehearse` be exposed in undefended mode?** In undefended, policy is `null` so rehearse always returns `ok: true`. Either: (a) hide rehearse from the catalog when undefended, or (b) keep it and rely on the prompt rule "rehearse when uncertain about defense outcome" naturally being a no-op. I lean (a) — fewer planner footguns.
2. **Should the rehearse history have a max size?** A long session could accumulate many entries. Cap at e.g. 50 most recent? Or unlimited and trust the iteration budget to bound it.
3. **Phase 2 migration**: how long do we run with `evidence: optional` before making it required? Probably until cycle 1 of the next benchmark sweep validates the path; then tighten.

## Out of scope (deferred)

- Rehearse for `resolve`, `extract`, `derive` phases. Those don't have the commit-precedes-verification problem (no side effects).
- Hint generation (the v1 spec's reason-code-to-hint table). Excluded for security: it leaks policy structure to the planner.
- Rehearsal tokens / divergence detection. Useful audit feature but not core to the fail-fast goal.
- Static lookahead ("would the planner's *next* execute succeed if it does *this* resolve first?"). Combinatorial.
