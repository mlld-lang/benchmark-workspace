# Brief for mlld-dev: privileged trust elevation on record fields

## Summary

We need a mechanism for **privileged trust elevation** on specific record fields when a record-level condition holds. The existing `labels: { X: { satisfies: ["fact:*"] } }` grammar is positive-check only — it satisfies fact-bearing positive checks (`no-send-to-unknown`) but does NOT clear sticky `untrusted` taint. AgentDojo bench tasks (BK UT3/4/11) require this distinction to be expressible; today they hit a wall where mlld correctly identifies them as security-blocked.

## Empirical pin

Zero-LLM probe at `clean/tmp/probe-trusted-field/probe-with-untrusted.mld`:

```mlld
record @probe_tx = {
  facts: [id: { type: string, kind: "tx_id" }],
  data: {
    trusted: [amount: number, date: string],
    untrusted: [subject: string]
  },
  ...
}

var untrusted @raw = { id: "tx_1", amount: 10.0, date: "...", subject: "..." }
var @coerced = @raw as record @probe_tx
```

After coercion:
- `@coerced.amount.mx.labels` → `["untrusted", "fact:@probe_tx.id"]` — sticky untrusted survives even though amount is declared `data.trusted`
- `@coerced.subject.mx.labels` → same shape — both fields equally tainted

This is consistent with `mlld-security-fundamentals.md` §1.6:

> `untrusted` is sticky and conservative; `trusted` cannot remove it. Adding `trusted` to already-untrusted data raises a conflict... Removing `untrusted` requires a privileged guard.

So the behavior is **by-design under current semantics**. `data.trusted` field declarations participate in schema validation and positive-check eligibility, but they do not bless a value at coercion time.

## Use case: CaMeL sender=="me" trust elevation

CaMeL (the paper we benchmark against) handles AgentDojo's banking-refund tasks by elevating trust on transactions whose sender is the user's own account. This is documented in their `capabilities/` module. AgentDojo's BK UT3/4/11 and several travel tasks require this trust-elevation primitive to be expressible to pass — otherwise the agent correctly identifies the operation as security-blocked under any conservative model.

`clean/camel-alignment-analysis.md` has the full per-task crosswalk.

## What we tried (migrator-7, ineffective)

In `bench/domains/banking/records.mld`:

```mlld
record @transaction = {
  ...
  refine [
    sender == "me" => labels += ["user_originated"]
  ],
  ...
}
```

In `rig/orchestration.mld`:

```mlld
labels: {
  user_originated: { satisfies: ["fact:*"] },
  trusted_tool_output: { satisfies: ["fact:*"] }
}
```

Bench probe verdict: 0/6 utility recovery on BK UT3/4/6/11 + TR UT3/4 (canonical recovery set per c-7780 / c-4076 estimates).

Why it didn't move the needle: `satisfies` is positive-check grammar (substitutes for `fact:*` proof on `no-send-to-unknown` etc.). It does NOT clear sticky untrusted taint on the value. `send_money_inputs.data.trusted: [amount: number]` requires the input value to NOT carry untrusted, so the validator still rejects.

## The request

We need a privileged trust-elevation mechanism that:

1. Is **intentional** — not automatic side-effect of `data.trusted` field declaration (that would undermine the sticky-untrusted invariant globally).
2. Is **conditional** — only fires when a record-level predicate holds (e.g., `sender == "me"`), so attacker-controlled records can't claim trust.
3. Is **audit-able** — surfaces in `.mx` so policy decisions can be reviewed.
4. Composes with existing refine grammar.

We are explicitly **NOT** asking for:
- `data.trusted` to globally override sticky untrusted (security regression)
- Removing the privileged-guard requirement for `untrusted` removal (security regression)

Candidate shapes — these are speculative; the design call is yours:

- `refine [ sender == "me" => bless [amount, date] ]` — privileged action inside refine that lifts untrusted from named fields, audit-tagged with the refine condition
- `labels: { user_originated: { clears: ["untrusted"] } }` — new label property where `satisfies` is positive-check and `clears` is taint-removal; only effective when applied by privileged guard or refine
- A new primitive entirely

Whichever shape lands, bench-side adoption is a small `records.mld` update.

## Tasks unblocked if the mechanism lands

Banking: UT3 (refund overpayment), UT4 (refund send), UT11 (VAT difference).
Travel: see `camel-alignment-analysis.md` for the analogous set.

Currently mlld correctly identifies these as security-blocked (the planner now produces transcript-grounded reasons after commit `4d2b0c0` un-masked mlld's policy-error envelope — see `clean/rig/workers/planner.mld @buildPhaseErrorLogEntry`). The behavior is correct; we just need a way to express user-delegated trust elevation that distinguishes "user explicitly says use this transaction's value" from "any tainted value can be elevated."

## Filed by

bench session (clean repo). Standing by for shape decision.
