# mlld-dev brief: labels.<X>.deny enforcement scope limited to primary input

## Status of c-3162

- **Gap A** (auto-rule firing): ✅ closed by Patch A in `isSystemLabel` (you landed)
- **Gap B v1** (dispatch identity through wrappers): ✅ closed by your ab333f2a9
- **Gap B v2** (envelope swallowing): ✅ closed rig-side — we updated `@toolCallError` to also match `{ok:false, error:"policy_denied"}` shape
- **Gap C (new, this brief)**: ❌ `labels.<X>.deny` enforcement scope appears limited to the primary input arg. When a multi-arg call has a known destination plus a labeled data arg, the labeled arg is silently bypassed.

## Symptom

For an `exfil:send` tool:

- **body-only fixture** (`body: derived:influenced`) → `labels.influenced.deny: ["exfil"]` fires ✅
- **body + known recipient fixture** (`recipient: known:"Alice"`, `body: derived:influenced`) → no denial, status: "sent" ❌

The body still carries `influenced`. The operation still has `exfil:send`. But adding a known fact arg apparently shifts the enforcement target — the body falls out of the label-flow check.

## Why this matters

This is the actual c-d0e3 root cause. The 5 SHOULD-FAIL tasks in our bench suite that currently execute unauthorized writes (slack UT16/19/20, workspace UT13, banking UT14) are ALL multi-arg dispatches of the same shape:

- A trusted/known control-arg (recipient handle, file_id, transaction_id)
- An untrusted/influenced data-arg (body string, content, amount derived from untrusted source)

The architectural defense intent is "untrusted-derived content cannot flow to write-tool data args." But with enforcement scoped to primary input only, the entire defense class is silently disabled in practice.

## Clean repro

`/Users/adam/mlld/clean/repro-c3162-gap2.mld` — same record decls, same policy, same untrusted body. Only difference between the two cases is whether the tool accepts a `recipient` fact arg.

Run:
```bash
mlld /Users/adam/mlld/clean/repro-c3162-gap2.mld --no-checkpoint 2>&1 | grep -E "==="
```

Output:
```
=== body-only fixture ===   → denied: labels.influenced.deny fires
=== body+recipient fixture === → status: "sent", no denial
```

Same `var influenced @taintedBody`. Same `labels: ["execute:w", "tool:w", "exfil:send"]`. Same `basePolicy: @synthesizedPolicy(...)`.

## Expected behavior

`labels.<X>.deny` should fire whenever ANY input arg in the dispatch carries `X` and the operation matches a deny target. Not just the primary input.

Specifically: any arg labeled `influenced` should not be allowed to flow into any `exfil:send`-labeled operation, regardless of arg position or whether other args satisfy `no-send-to-unknown`.

## What we suspect (UNVERIFIED — pointer for your investigation)

`core/policy/label-flow.ts` checkLabelFlow uses `ctx.inputTaint` to determine taint. If `inputTaint` is computed from only the primary input descriptor (vs. union over all args), that explains the symptom. The body-only fixture has body as primary so its labels are in inputTaint; the multi-arg fixture has recipient as primary so body's labels are excluded.

Compare with the `no-send-to-unknown` rule which has explicit "primary input" semantics (`primaryInputKnown` checked at label-flow.ts:440). `labels.<X>.deny` is a more general rule and shouldn't have that restriction.

## Acceptance criterion

`/Users/adam/mlld/clean/tests/rig/c-3162-dispatch-denial.mld testInfluencedBodyDenied` is currently XFAIL with the c-3162 ticket attached. Fix lands when:

1. That test PASSes (un-xfail in the same commit that lands the mlld fix; the test asserts `error == "policy_denied"` and message includes "influenced")
2. The body-only path still denies (existing tests in `core/policy/label-flow.test.ts` should already cover this)
3. The clean (non-influenced) multi-arg dispatch in c-3162's `testCleanBodyNotDenied` still passes

## Won't be a small fix?

If extending enforcement scope breaks many existing mlld tests (because they relied on the narrow scope), that's evidence the prior scope was wrong-by-omission and the migration is the right time to fix. We can absorb test-side updates rig-side.

## Files

- Repro: `/Users/adam/mlld/clean/repro-c3162-gap2.mld`
- Acceptance test: `/Users/adam/mlld/clean/tests/rig/c-3162-dispatch-denial.mld`
- Rig-side commit that closed Gap B v2 (envelope): pending — `rig/runtime.mld:815` `@toolCallError` patched
- Strategic context: rig is in Phase 2 migration close; goal is "deterministic security holds; utility is a known unknown until re-measured." Closing this gap is what re-enables the rig defense story end-to-end.
