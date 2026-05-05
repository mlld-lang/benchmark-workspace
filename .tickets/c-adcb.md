---
id: c-adcb
status: closed
deps: []
links: []
created: 2026-05-05T05:53:39Z
type: bug
priority: 2
assignee: Adam
tags: [tests, rig-fixtures, mlld-coordination]
updated: 2026-05-05T06:06:48Z
---
# Rig invariant tests: 3 fixtures broken by mlld strict auto-derive

After mlld commit 0c6558d62 (kind-tagged fact requirements landed in core), policy.build's auto-derivation got stricter. Three rig invariant tests now fail with proofless_control_arg / proofless_resolved_value:

- reschedule-dispatch-succeeds (rig/tests/index.mld)
- collection-dispatch-policy-build (rig/tests/index.mld:2848)
- collection-dispatch-cross-module-m5178 (rig/tests/index.mld:2858)

These tests build a synthetic state with @ut7Resolved / @ut8Resolved that uses 'as record @calendar_evt' for coercion + manual @ut7State / @ut8State construction. The tests pass an intent like:

  resolved: { reschedule_calendar_event: { event_id: @ut7Resolved.id_ } }

Where @ut7Resolved.id_ has factsources for @calendar_evt.id_. With kinds:
- @calendar_evt.id_ tagged kind: 'calendar_event_id' (workspace/records.mld) ✓
- @calendar_reschedule_inputs.event_id tagged kind: 'calendar_event_id' ✓
- kindIndex['calendar_event_id'] correctly includes fact:@calendar_evt.id_ (verified via probe)

But policy.build still rejects with proofless_control_arg/proofless_resolved_value. The probe shows requirements derive correctly. The mismatch is between the requirements list and what hasAcceptedProofLabels sees — likely the test's manual state construction doesn't propagate factsources through to the policy.build check.

## Suspect path

The intent passes @ut7Resolved.id_ as a bare value (not handle-wrapped). policy.build expects either:
- known with task-text validation, OR
- A handle-backed value with factsources visible to the proof check

The test's setup probably worked under the OLD permissive policy.build but doesn't satisfy the new strict one.

## Fix paths

1. Update test fixtures to wrap event_id in a handle-bearing intent shape (e.g. via the resolveControlRefValue path or by passing a properly-projected handle).
2. Verify the old test was relying on a permissive default that's now correctly stricter.
3. If the old behavior was a real bug, update tests to match the new contract.

## Not blocked on

Security suites still pass:
- slack: 11/0/0 (wrong-record bypass closed via kinds)
- banking: 8/0/0
- workspace: 6/0/0

The bench domain runtime works correctly. This is purely about rig test fixture setup matching mlld's stricter contract.

## Reference

- mlld commit 0c6558d62 'Add fact kind tags for record policy requirements'
- SECURITY-RIG-WRONG-RECORD-BYPASS.md (the kind design)
- spec-fact-kind-tags.md (counter-proposal that became the design, in mlld-dev now)

Probe artifacts in /tmp during 2026-05-04 session showed the kindIndex lookup is correct; the issue is value-side proof not making it to hasAcceptedProofLabels in the test setup.

