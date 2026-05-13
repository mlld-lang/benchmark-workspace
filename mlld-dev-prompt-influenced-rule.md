# mlld-dev brief: `untrusted-llms-get-influenced` rule simplification

## Status of the existing rule

The `untrusted-llms-get-influenced` auto-rule appears to fire at multiple sites in the dispatch path, including at consumer / dispatch arg resolution, based on **source class** (`derived` → influenced). This produces over-labeling: clean values that happen to travel through `derived`-source-class refs pick up `influenced` at dispatch even though their actual lineage contains no untrusted source.

Probe evidence (`/Users/adam/mlld/clean/tests/rig/c-3162-dispatch-denial.mld`, the `cleanBodyNotDenied` test): a plain string literal `"this is a clean task-text-sourced body"` is placed into `state.derived` via `@updateNamedState`. At each inspection point along the rig's prep chain — `@resolveRefValue`, `@compileExecuteIntent`, `@compileForDispatch` — the value carries clean `mx.labels: []`. But at dispatch, the body arg carries `influenced` and the `labels.influenced.deny` rule fires:

```
Operation: /exe "send_message"
Blocked by: Policy policy
Rule: policy.labels.influenced.deny
Reason: Label 'influenced' from argument 'body' cannot flow to 'exfil'
```

The label is added somewhere inside the policy evaluation path, after `@resolveRefValue` returns clean labels.

## Proposed shape

Move `influenced` labeling to **one moment per LLM exe**, at exe-exit, based on input dep-tree walking. No re-labeling at downstream consumer sites.

**Rule fires at**: LLM exe exit (return-value labeling, applied to the value the exe returns).
**Rule condition**: the exe's input dep-tree contains an `untrusted`-class source.
**Rule effect**: attach `influenced` to the return value's metadata exactly once.

**Drop**: any source-class-driven re-labeling at downstream consumers / dispatch. The label is part of the value's identity, attached at exe-exit, traveling with the value through state, refs, and dispatch.

## Why this is the right shape

- **Matches CaMeL's `is_trusted()` semantic** — labels reflect actual data lineage, attached at the moment a value is minted, respected downstream.
- **Avoids "everything is influenced" in LLM-first apps** — clean LLM exes (input deps all trusted) return clean. Label retains signal because it correlates with actual untrusted lineage.
- **Defense intent preserved** — untrusted inputs still produce influenced output. The bug we fixed in c-3162 Gap C (labels.influenced.deny enforcing on multi-arg dispatch) keeps working. The c-d0e3 systemic closure stays closed.
- **Simpler implementation** — one dep-walk per exe call, not repeated walks at every consumer. The label is "stamped" not "computed-on-demand."

## How it composes with rig's planner-worker model

Rig has a clean privileged/quarantined-LLM split (per CaMeL pattern):

- **Workers** (`@dispatchExtract`, `@dispatchDerive`, `@dispatchCompose`, etc.) ARE LLM exes. Input → LLM call → return. Each worker's return gets labeled at its exit based on its inputs.
- **Planner** is a session manager that dispatches workers iteratively. Not a single labelable exe with one final return; it produces side effects (dispatched tool calls) over its session.
- Workers' returns flow into `state.<worker>.<name>` and are referenced at dispatch via source-class refs.

Under the proposed rule:
- Worker A receives only User-trusted inputs → A's return is clean → state entry clean → dispatch ref clean → defense doesn't fire (correct).
- Worker B receives extracted-from-untrusted-email input → B's return is influenced → state entry influenced → dispatch ref influenced → defense fires (correct).
- Worker C receives a mix → influenced if dep-walk finds untrusted somewhere in its inputs.

The planner doesn't need its own "session-end label." Its effect is the dispatches it emits, which carry labels from state (from worker returns).

## Repro for the over-labeling bug

The c-3162 clean test today (XFAIL'd, fixture at `tests/rig/c-3162-dispatch-denial.mld`):
```bash
mlld /Users/adam/mlld/clean/tests/rig/c-3162-dispatch-denial.mld --no-checkpoint
```
Expected after fix:
```
[PASS] influenced-flow-to-exfil-send/influencedBodyDenied
[PASS] clean-flow-allowed/cleanBodyNotDenied
summary: 2 pass / 0 fail (0 xfail, 0 xpass)
```

Currently:
```
[PASS] influencedBodyDenied  (influenced denial fires correctly)
[XFAIL] cleanBodyNotDenied  (clean dispatch over-denied due to source-class-driven influenced)
```

The clean test seeds `state.derived.clean_summary.body = "this is a clean task-text-sourced body"` via plain `var` (no `var influenced @...` modifier, no extracted/untrusted dependency). The test fixture is artificial — it bypasses the worker LLM call path — but it exposes the source-class-driven re-labeling because mlld can't distinguish "this came from a worker LLM call" from "this was synthetically seeded into state.derived."

Minimal probe shape:
```mlld
var @plain = "clean task text"
var @state = @updateNamedState(@emptyState(), "derived", "name", {
  provenance: "derived",
  value: { body: @plain },
  ...
})
var @resolved = @resolveRefValue(@agent, @state, { source: "derived", name: "name", field: "body" })
/show `labels at resolve: @resolved.value.mx.labels`  >> currently: clean

>> But inside @callToolWithPolicy with an exfil:send-labeled tool, the body picks up
>> "influenced" and labels.influenced.deny denies.
```

## Defense intent we want to preserve

After the fix, all of these still hold:

1. **c-d0e3 closure**: untrusted email content → extract worker (LLM call w/ untrusted input) → extract output is influenced → flows into write-tool body → labels.influenced.deny fires → defense correct. (The c-3162 influenced test stays PASS.)
2. **Multi-arg enforcement** (the m-c91d field-level provenance work): labels.influenced.deny continues to enforce on data args even with known control args.
3. **Untrusted-to-trusted record-decl violations**: still denied at dispatch (banking UT13 address-from-file shape still correctly denies).

The change is narrow: stop adding influenced at consumer sites based on source class. Let exe-exit labeling be the canonical source.

## Estimated utility impact (Tier 2 unlock)

For the bench, dependency-driven labeling should unlock ~5-10 tasks:

- BK UT3 (friend repayment): derive worker called with User-trusted IBAN + amount → return inherits User-trust → flows into send_money trusted fields cleanly.
- BK UT4 (refund), BK UT6 (subscription), BK UT11 (Apple VAT): same shape — User-trusted inputs to derive worker, currently over-labeled.
- Compounds with the records refine migration (Tier 1) — e.g., a banking transaction with `sender == "me"` getting `user_originated` label via record refine, then a derive worker using it stays clean, then send_money allows it.

Combined with Tier 1 records refine work, estimated total recovery is **10-18 tasks** from current 53/97 → **63-71/97**.

## Implementation surface (suggested)

- Identify the policy evaluation site where `influenced` gets attached based on source class. Likely in `core/policy/label-flow.ts` or `interpreter/eval/exec-invocation.ts` near the dispatch arg resolution.
- Replace source-class trigger with: at LLM exe completion, dep-walk the input set, attach `influenced` to the return value's metadata if any dep has `untrusted` label.
- Downstream consumers (resolve-ref, dispatch, policy check) read the stored label without re-evaluation.
- The `untrusted-llms-get-influenced` rule itself stays as a default rule, but its firing site is "exe exit" rather than "label-flow evaluation time."

## Acceptance criteria

1. `tests/rig/c-3162-dispatch-denial.mld` PASS on both groups (un-xfail the clean test).
2. Zero-LLM gate: 264+/0/4 (the clean test moves back to PASS).
3. The c-d0e3 atk_direct slack canary stays at 0/105 ASR — defense still fires on real influenced flow.
4. The c-3162 influenced denial test still PASS — multi-arg labels.influenced.deny continues to enforce.
5. Worker live-LLM gate unaffected.

## Out of scope (acknowledged, deferred)

- Cross-session label propagation (planner session "memory" of past untrusted content). Not needed for correctness; each worker call's inputs determine its own output label.
- Conditional declassification primitives ("file-signing / verified-fact / intent attestation"). Separate spec work; this brief is purely about correct in-session labeling.
- Per-exe override mechanisms ("trust this LLM call's output regardless of inputs"). Not needed in v1; CaMeL's `Assistant` source effectively gives this for free via dep-walking.
