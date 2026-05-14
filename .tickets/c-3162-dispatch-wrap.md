---
id: c-3162-dispatch-wrap
status: closed
deps: []
links: []
created: 2026-05-14T20:30:06Z
type: task
priority: 1
assignee: Adam
tags: [rig, migration, c-3162, policy-deny-envelope]
updated: 2026-05-14T22:29:39Z
---
# Wrap @callToolWithPolicy throw in @dispatchExecute structured-return

## Context

c-3162-dispatch-denial.mld test (tests/rig/c-3162-dispatch-denial.mld:77) fails post-v2.x BasePolicy migration because @callToolWithPolicy throws POLICY_LABEL_FLOW_DENIED when the influenced flow rule fires — but @dispatchExecute has no wrapper to catch it. The throw propagates to the module-load `var @c3162DispatchResult = @dispatchExecute(...)` assignment, before the test exe ever runs.

## What's right

The defense IS firing correctly per the new policy:
- Operation: `send_message` dispatch with influenced body
- Rule: `policy.labels.influenced.deny`
- Decision: deny  
- Reason: "Label 'influenced' from argument 'body' cannot flow to 'exfil'"

This is the canonical defense behavior we want for IT0-style attacks across slack/banking/workspace/travel.

## What needs fixing

@dispatchExecute (rig/workers/execute.mld:171-225) should catch the policy throw at @callToolWithPolicy boundary and return the structured envelope (`{ ok: false, stage: "dispatch_policy", failure: { ... } }`) rather than letting it propagate.

The mlld pattern is `when [denied => ...]` inside an exe scope. Either:

1. Wrap @dispatchExecute itself with denied arm:
   ```
   exe role:worker @dispatchExecute(...) = when [
     denied => @buildPolicyDenialResult(...)
     * => [ ... existing body ... ]
   ]
   ```
2. Or route @callToolWithPolicy through an intermediate exe with denied handling.

## Acceptance

- c-3162-dispatch-denial.mld passes — assertion exercises the deny envelope structurally.
- Other suites (slack canary IT0/IT1, banking IT0..IT8) emit `policy_denied` results consistently with the existing Cluster I masking (commit 4d2b0c0) without manual throw-catch each call site.

## Sec-doc impact

This is the structural enforcement that makes [-]/[T] marks under §8 Class 1 (banking) and Class B (slack) regression-locked. The defense holds — it just needs the wrapper for tests/diagnostics to read it.

