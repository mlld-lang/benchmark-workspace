# mlld-dev followup: code-path provenance vs data-path provenance

## Context

`mlld-dev-prompt-influenced-rule.md` (filed 2026-05-12) proposed moving `influenced` labeling to LLM exe-exit only, based on dep-tree walking of input arg taint.

Commit `dfa8d5c1b "Narrow influenced cascade to provenance evidence"` did the narrow half: routing-only labels (`src:exe`, `role:worker`, `llm`) no longer trigger the cascade. Provenance labels (`src:*` except `src:exe`, `dir:*`, `fact:*`) still trigger it.

This closed the immediate over-fire symptom for routing-only label sets. But a second over-fire shape remains, and it blocks Tier 2 utility recovery on bench. Sharing the repro + asking for scope clarification.

## The remaining over-fire shape

A clean module-scope value picks up `src:file`/`dir:*` labels after passing through rig's code:

```mlld
>> /tmp/probe-c3162-clean.mld
import { @updateNamedState } from "/Users/adam/mlld/clean/rig/orchestration.mld"
import { @emptyState } from "/Users/adam/mlld/clean/rig/runtime.mld"
import { @resolveRefValue } from "/Users/adam/mlld/clean/rig/intent.mld"

var @plain = "clean string"
/show `plain: labels=@plain.mx.labels taint=@plain.mx.taint`
>> Output: plain: labels=[] taint=[]

var @state = @updateNamedState(@emptyState(), "derived", "clean_summary", {
  provenance: "derived",
  value: { body: @plain },
  selection_refs: []
})

var @agent = { records: {}, plannerShelf: {}, extracted: {}, derived: @state.derived }
var @resolved = @resolveRefValue(@agent, @state, { source: "derived", name: "clean_summary", field: "body" })
/show `resolved value taint: @resolved.value.mx.taint`
```

Output of the last show:
```
resolved value taint: [
  "src:file",
  "dir:/Users/adam/mlld/clean/registry:/@mlld",
  "dir:/Users/adam/mlld/clean/registry:",
  "dir:/Users/adam/mlld/clean",
  "dir:/Users/adam/mlld",
  "dir:/Users/adam",
  "dir:/Users",
  "dir:/Users/adam/mlld/clean/llm/lib/opencode",
  "dir:/Users/adam/mlld/clean/llm/lib",
  "dir:/Users/adam/mlld/clean/llm",
  "dir:/Users/adam/mlld/clean/rig",
  "src:exe",
  "dir:/Users/adam/mlld/clean/rig/workers",
  "src:js"
]
```

The value picked up `src:file` and `dir:*` labels from the **files containing the resolver code** (rig/runtime.mld, rig/intent.mld, rig/workers/*.mld, registry paths), not from where the value's content originated.

Under your tests in `c-3162-probe.test.ts:124-134`: "any single provenance label among routing labels triggers cascade." So this taint shape DOES fire `untrusted-llms-get-influenced` (provenance evidence is present), AND there's no user-trust label, so the cascade fires → output gets `influenced`.

## Why this blocks Tier 2 utility recovery

Bench tasks where the agent does arithmetic on user-trusted inputs hit this. Example (banking UT3, friend repayment):

1. Agent receives user task text with IBAN + amount → values are clean (no untrusted, no influenced)
2. Agent dispatches `derive` worker with these inputs
3. Worker is implemented in `rig/workers/derive.mld` → during dispatch, inputs flow through `@resolveRefValue`, `@compileForDispatch`, etc.
4. By the time the LLM call sees the inputs, taint includes `src:file: rig/workers/derive.mld` plus all the rig/intent/registry paths
5. mlld's cascade: "provenance evidence + no user-trust label" → effective set includes `untrusted` → `shouldAddInfluencedLabel` returns true → derive output gets `influenced`
6. Planner then dispatches `send_money` with `amount: {source: "derived", ...}` 
7. `labels.influenced.deny: ["exfil"]` fires → write denied → utility = false

Same shape for BK UT4/6/11 (refund, recurring subscription, Apple VAT) — all "user-trusted inputs → derive worker → write tool."

c-3162 clean test (`tests/rig/c-3162-dispatch-denial.mld testCleanBodyNotDenied`) still XFAILs for exactly this reason.

## The original brief's framing — distinct from current behavior

The brief proposed dep-tree walking of **input arg taint at LLM exe boundary**:

- If the LLM call's input args have `untrusted` (or trace to untrusted via real data dep tree) → fire `influenced`
- If input args are clean (no untrusted ancestry in data lineage) → don't fire

The key distinction: walk the value's **data dependencies**, not the **code paths it passed through**.

Currently mlld treats `src:file: rig/workers/derive.mld` as evidence the value came from a file. Under the brief's framing, this label is **routing through code, not data origin** — the value's content has no actual file origin, only the code that processed it did.

## Question for scope clarification

Two ways to read this:

**Reading A**: The brief's full proposal is still in scope. mlld should distinguish "value came from a file as data" (real provenance) from "value passed through code in a file as routing" (false-positive provenance). The current tests pin the c-3162 closure but don't address the false-positive case. Implementation: track WHY a `src:file` label got attached — content-origin vs code-touch — and only count content-origin as cascade-triggering provenance.

**Reading B**: This is a rig-side problem. The c-3162 over-fire fix is done; if rig's code path accidentally stamps values with file labels that shouldn't be there, rig needs to strip them before LLM dispatch. mlld's fix is correct — `src:file` IS provenance evidence; the issue is rig is creating that evidence inappropriately.

We can do either, but they have very different scope. Reading B is rig-only work (potentially intrusive across the dispatch path). Reading A keeps the architectural framing of the original brief.

Your call on which reading represents the intended scope. We'll do whichever side the answer points at.

## Acceptance criterion (regardless of which reading)

After whichever fix lands:

1. `tests/rig/c-3162-dispatch-denial.mld testCleanBodyNotDenied` PASSes (un-xfail in the same commit).
2. Banking benign re-run on `bench/domains/banking/records.mld` with c-7780 records refine (transaction sender==me user_originated) applied: BK UT3/UT4/UT6/UT11 recover.
3. Slack atk_direct + atk_important_instructions canaries stay at 0/105 ASR.
4. Zero-LLM gate: 263+/0/X.

## Files

- Brief: `/Users/adam/mlld/clean/mlld-dev-prompt-influenced-rule.md` (original)
- This followup: `/Users/adam/mlld/clean/mlld-dev-prompt-c3162-gap3.md`
- Repro probe: `/tmp/probe-c3162-clean.mld` (transient; full source in §"The remaining over-fire shape" above)
- Test that pins the symptom: `tests/rig/c-3162-dispatch-denial.mld` `testCleanBodyNotDenied` (currently XFAIL'd)
